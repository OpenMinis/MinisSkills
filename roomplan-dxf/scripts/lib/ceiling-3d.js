'use strict';
/**
 * ceiling-3d.js — turns the ceiling decision (lib/ceiling-reconstruct.js,
 * explicit source ceilings first) into ACTUAL 3D ceiling surfaces in SOURCE
 * WORLD space, plus the height label every consumer needs.
 *
 * Why a separate module: the DXF layer only ever needed a dashed outline and a
 * height range in plan. USDZ (.usdz, AR Quick Look) has no text and no
 * annotation, so the ONLY way a ceiling or a room height can be seen there is
 * real geometry plus customData. Both consumers, and the DXF room label, must
 * agree on the same heights, so the height function lives here once.
 *
 * Height model (never invented):
 *   - flat        every vertex at the measured/typical wall height;
 *   - knee/section the slope angle comes from the reconstruction itself:
 *                 surplus/span = profileLength/span - 1 = sec(theta) - 1, so
 *                 tan(theta) = sqrt((1 + surplus/span)^2 - 1). Heights are then
 *                 linear along the fall direction (fallDirection.u from
 *                 ceiling-reconstruct.js), clamped to the measured
 *                 [kneeHeight, ridgeHeight] range.
 *   - gable       fallDirection.downhill === 'both' (the two profile ends sit at
 *                 the same height, i.e. the ridge is in the middle) -> the
 *                 footprint is cut at the ridge and two planes are returned.
 *   - extrusion / unavailable / anything else: one FLAT plane at the knee
 *                 height, plus warning usdz.ceiling-approximated.
 *   - no footprint polygon: NO ceiling at all, plus usdz.ceiling-no-polygon.
 *
 * Nothing here guesses a height that was not measured: if neither the merged
 * reconstruction heights nor a wall height exist, the room gets no ceiling.
 */
const recon = require('./ceiling-reconstruct');

const finite = (v) => typeof v === 'number' && Number.isFinite(v);

function pointInPolygon(p, poly, tol = 1e-7) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i, i += 1) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi || 1e-12) + xi) inside = !inside;
    if (Math.abs(yi - p[1]) <= tol && Math.abs(xi - p[0]) <= tol) return true;
  }
  return inside;
}

/** Mean source-world Y of the floor polygons that cover this zone. */
function floorElevation(model, zone) {
  const room = zone.room;
  if (room && finite(room.floorHeight)) return { y: room.floorHeight, basis: 'room.floor_height' };
  const surfaces = (model && model.surfaces) || [];
  const story = finite(zone.story) ? zone.story : 0;
  const floors = surfaces.filter((s) => s && s.kind === 'floor' && (finite(s.story) ? s.story : 0) === story);
  let best = null;
  for (const f of floors) {
    const corners = Array.isArray(f.polygonCorners) ? f.polygonCorners : null;
    const t = f.transform;
    if (!corners || corners.length < 3 || !Array.isArray(t) || t.length !== 16) continue;
    const pts = corners
      .filter((p) => p && finite(p.x) && finite(p.y) && finite(p.z))
      .map((p) => [
        t[0] * p.x + t[4] * p.y + t[8] * p.z + t[12],
        t[1] * p.x + t[5] * p.y + t[9] * p.z + t[13],
        t[2] * p.x + t[6] * p.y + t[10] * p.z + t[14],
      ]);
    if (pts.length < 3) continue;
    const plan = pts.map((p) => [p[0], p[2]]);
    const y = pts.reduce((a, p) => a + p[1], 0) / pts.length;
    if (zone.polygon && !pointInPolygon(planCentroid(zone.polygon), plan, 0.02)) continue;
    if (best == null) best = y;
  }
  if (best != null) return { y: best, basis: 'covering floor polygon' };
  // last resort: the lowest point of the zone's own wall polygons (RoomPlan
  // wall outlines start at the floor)
  const ys = [];
  for (const w of zone.walls || []) {
    for (const c of Array.isArray(w.polygonCorners) ? w.polygonCorners : []) {
      if (!c || !finite(c.x) || !finite(c.y) || !finite(c.z) || !Array.isArray(w.transform)) continue;
      const t = w.transform;
      ys.push(t[1] * c.x + t[5] * c.y + t[9] * c.z + t[13]);
    }
  }
  if (ys.length) return { y: Math.min(...ys), basis: 'lowest wall polygon vertex' };
  return { y: 0, basis: 'stage origin (no floor datum measured)' };
}

function planCentroid(poly) {
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < poly.length; i += 1) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    const f = x1 * y2 - x2 * y1;
    a += f;
    cx += (x1 + x2) * f;
    cy += (y1 + y2) * f;
  }
  if (Math.abs(a) < 1e-12) {
    return [poly.reduce((s, p) => s + p[0], 0) / poly.length, poly.reduce((s, p) => s + p[1], 0) / poly.length];
  }
  return [cx / (3 * a), cy / (3 * a)];
}

/** Sutherland-Hodgman clip of a plan polygon against a half-plane along `dir`. */
function clipHalfPlane(poly, dir, keepBelow, offset) {
  const val = (p) => p[0] * dir[0] + p[1] * dir[1] - offset;
  const out = [];
  for (let i = 0; i < poly.length; i += 1) {
    const cur = poly[i];
    const prev = poly[(i + poly.length - 1) % poly.length];
    const vc = val(cur);
    const vp = val(prev);
    const inCur = keepBelow ? vc <= 1e-9 : vc >= -1e-9;
    const inPrev = keepBelow ? vp <= 1e-9 : vp >= -1e-9;
    if (inCur) {
      if (!inPrev) {
        const t = vp / (vp - vc);
        out.push([prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t]);
      }
      out.push(cur);
    } else if (inPrev) {
      const t = vp / (vp - vc);
      out.push([prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t]);
    }
  }
  return out.length >= 3 ? out : null;
}

/** Plan area of a footprint (absolute shoelace). */
function planArea(poly) {
  if (!Array.isArray(poly) || poly.length < 3) return 0;
  let a = 0;
  for (let i = 0; i < poly.length; i += 1) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

/**
 * The straight plan segment where a 2D clip at `offset` cut a polygon: all
 * vertices of `polys` that lie on `fn(p) === offset`, reduced to the farthest
 * pair. This is the ridge / band boundary the DXF must draw, taken from the
 * SAME split the 3D ceiling uses (never a re-derived line).
 */
function boundarySegment(polys, offset, fn) {
  const pts = [];
  for (const poly of polys) {
    if (!Array.isArray(poly) || poly.length < 3) continue;
    for (let i = 0; i < poly.length; i += 1) {
      const a = poly[i];
      const b = poly[(i + 1) % poly.length];
      const va = fn(a) - offset;
      const vb = fn(b) - offset;
      if (Math.abs(va) <= 1e-6) pts.push([a[0], a[1]]);
      if ((va > 1e-6 && vb < -1e-6) || (va < -1e-6 && vb > 1e-6)) {
        const t = va / (va - vb);
        pts.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
      }
    }
  }
  let best = null;
  let bestLen = 0;
  for (let i = 0; i < pts.length; i += 1) {
    for (let j = i + 1; j < pts.length; j += 1) {
      const d = Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]);
      if (d > bestLen) { bestLen = d; best = [pts[i], pts[j]]; }
    }
  }
  return bestLen > 0.05 ? best : null;
}

/**
 * Split a ceiling footprint into its SLOPED band and its FLAT remainder.
 *
 * WHY: a real knee/slope profile rises only over the measured `run` next to
 * the LOW wall and is flat at the ridge everywhere else. Interpolating one
 * plane across the whole footprint produced a single tilted sheet cutting
 * through the room — the failure this function exists to prevent.
 *
 * The footprint never decides the shape; the measured wall-top section does:
 *   - the ceiling leaves the knee height at the low edge, rises with the
 *     measured tangent, and has reached the ridge exactly `run` metres in;
 *   - everything past that line is FLAT at the ridge height;
 *   - nothing is emitted when the profile itself is flat (caller handles it).
 * A gable (`downhill === 'both'`, two slope segments) rises from BOTH low
 * edges to one ridge in the middle, and keeps a flat plateau only when the
 * section itself contains a flat segment.
 *
 * `poly` is 2D in ANY planar frame (source XZ for the USDZ, drawing XY for the
 * DXF) and `u` is the fall direction in that same frame, so both consumers
 * split the SAME footprint the SAME way.
 *
 * @param {Array<[number,number]>} poly footprint
 * @param {[number,number]} u fall direction (downhill side named by `downhill`)
 * @param {string} downhill 'plus' | 'minus' | 'both'
 * @param {object} opts { run, knee, ridge, flatRun }
 * @returns {null|{gable:boolean, run:number, parts:Array, ridgeLines:Array}}
 *   part = { kind:'slope'|'flat', poly, heightMin, heightMax, heightAt }
 */
function splitCeilingPlan(poly, u, downhill, opts) {
  const o = opts || {};
  if (!Array.isArray(poly) || poly.length < 3) return null;
  if (!Array.isArray(u) || !(Math.hypot(u[0], u[1]) > 1e-9)) return null;
  const l = Math.hypot(u[0], u[1]);
  const uh = [u[0] / l, u[1] / l];
  const knee = finite(o.knee) ? o.knee : 0;
  const ridge = finite(o.ridge) ? o.ridge : knee;
  if (!(ridge > knee + 0.005)) return null;
  const gable = downhill === 'both';
  // t increases UPHILL: 0 at the low edge.
  const up = downhill === 'plus' ? [-uh[0], -uh[1]] : uh;
  const at = (p) => p[0] * up[0] + p[1] * up[1];
  const ts = poly.map(at);
  const tmin = Math.min(...ts);
  const tmax = Math.max(...ts);
  const span = tmax - tmin;
  if (!(span > 0.05)) return null;
  const clampH = (h) => Math.min(ridge, Math.max(knee, h));
  const parts = [];
  const ridgeLines = [];

  if (gable) {
    const plateauRun = Math.min(finite(o.flatRun) ? Math.max(0, o.flatRun) : 0, span * 0.6);
    const rampLen = Math.max((span - plateauRun) / 2, 0.01);
    const tan = (ridge - knee) / rampLen;
    const low = (p) => Math.min(at(p) - tmin, tmax - at(p));
    const heightAt = (p) => clampH(knee + tan * Math.max(0, low(p)));
    const lowSide = clipHalfPlane(poly, up, true, tmin + rampLen);
    const highSide = clipHalfPlane(poly, up, false, tmax - rampLen);
    const plateau = plateauRun > 0.05
      ? clipHalfPlane(clipHalfPlane(poly, up, false, tmin + rampLen), up, true, tmax - rampLen)
      : null;
    if (lowSide) parts.push({ kind: 'slope', poly: lowSide, heightMin: knee, heightMax: ridge, heightAt });
    if (plateau) parts.push({ kind: 'flat', poly: plateau, heightMin: ridge, heightMax: ridge, heightAt: () => ridge });
    if (highSide) parts.push({ kind: 'slope', poly: highSide, heightMin: knee, heightMax: ridge, heightAt });
    const a = boundarySegment([lowSide], tmin + rampLen, at);
    const b = boundarySegment([highSide], tmax - rampLen, at);
    if (!plateau) {
      const line = a || b;
      if (line) ridgeLines.push(line);
    } else {
      if (a) ridgeLines.push(a);
      if (b) ridgeLines.push(b);
    }
    return { gable: true, run: rampLen, parts, ridgeLines };
  }

  const run = Math.min(Math.max(finite(o.run) && o.run > 0.01 ? o.run : span, 0.01), span);
  const tan = (ridge - knee) / run;
  const heightAt = (p) => clampH(knee + tan * Math.max(0, at(p) - tmin));
  if (span - run > 0.05) {
    const band = clipHalfPlane(poly, up, true, tmin + run);
    const rest = clipHalfPlane(poly, up, false, tmin + run);
    if (band) parts.push({ kind: 'slope', poly: band, heightMin: knee, heightMax: ridge, heightAt });
    if (rest) parts.push({ kind: 'flat', poly: rest, heightMin: ridge, heightMax: ridge, heightAt: () => ridge });
    const line = boundarySegment([band, rest], tmin + run, at);
    if (line) ridgeLines.push(line);
  }
  if (!parts.length) {
    parts.push({ kind: 'slope', poly, heightMin: knee, heightMax: ridge, heightAt });
  }
  return { gable: false, run, parts, ridgeLines };
}

/** Signed plan area (shoelace), used only to order vertices consistently. */
function signedArea(poly) {
  let a = 0;
  for (let i = 0; i < poly.length; i += 1) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
}

/**
 * Slope of the roof section as a tangent, straight from the reconstruction
 * numbers: surplus/span = sec(theta) - 1.
 */
function slopeTangent(section) {
  if (!section || !finite(section.span) || !(section.span > 1e-6)) return 0;
  const ratio = Math.max(0, (finite(section.surplus) ? section.surplus : 0) / section.span);
  const t = Math.sqrt(Math.max(0, (1 + ratio) * (1 + ratio) - 1));
  return finite(t) ? t : 0;
}

function lift(poly, floorY, hAt) {
  const out = poly.map((p) => [p[0], floorY + hAt(p), p[1]]);
  return out;
}

/**
 * One emitted ceiling surface with the numbers a reader (Quick Look has no
 * text) or a test needs: its own kind, its own height range and its own
 * FOOTPRINT area. Plan area, not the slanted area, so "the sloped strip is
 * run x depth" stays checkable.
 */
function makePart(kind, polygons, floorY, method, extra) {
  const polys = (Array.isArray(polygons[0][0]) ? polygons : [polygons]).map((pl) => pl.map((p) => [p[0], p[1], p[2]]));
  const all = polys.reduce((a, pl) => a.concat(pl), []);
  const ys = all.map((p) => p[1]);
  const min = Math.min(...ys) - floorY;
  const max = Math.max(...ys) - floorY;
  return {
    kind,
    method: method || null,
    geometry: kind === 'slope' ? 'sloped strip' : kind === 'gable' ? 'gable plane' : 'flat plane',
    polygons: polys,
    points: polys[0],
    faces: polys.length,
    heightMin: min,
    heightMax: max,
    heightLabel: heightLabel(min, max),
    area: polys.reduce((a, pl) => a + planArea(pl.map((p) => [p[0], p[2]])), 0),
    ...(extra || {}),
  };
}

/**
 * Ceiling solids for every room/zone of the model.
 *
 * @returns {{ceilings: Array, warnings: Array}}
 *   ceiling = {
 *     key, roomIdentifier, label, story, method, coverage,
 *     polygon,                       // plan footprint [[x,z], ...] or null
 *     surfaces: [{ points, kind }],  // source-world 3D n-gons (flat|slope|gable)
 *     floorY, heightMin, heightMax, heightLabel, area, slopeTangent, ridge
 *   }
 */
function ceilingSolids(model) {
  const warnings = [];
  const ceilings = [];
  let zones;
  try {
    zones = recon.zoneCeilings(model || {});
  } catch (e) {
    warnings.push({ code: 'usdz.ceiling-unavailable', message: `Ceiling reconstruction failed (${e.message}); no ceilings emitted.` });
    return { ceilings, warnings };
  }
  for (const zone of zones) {
    const label = zone.label != null ? String(zone.label) : null;
    const base = {
      key: zone.key,
      roomIdentifier: zone.roomIdentifier != null ? String(zone.roomIdentifier) : null,
      label,
      story: finite(zone.story) ? zone.story : 0,
      method: zone.method || null,
      coverage: zone.coverage || null,
      area: finite(zone.ceilingArea) ? zone.ceilingArea : null,
      polygon: Array.isArray(zone.polygon) && zone.polygon.length >= 3 ? zone.polygon.map((p) => [p[0], p[1]]) : null,
      surfaces: [],
      floorY: null,
      heightMin: null,
      heightMax: null,
      heightLabel: null,
      slopeTangent: null,
      ridge: false,
      floorBasis: null,
      // Every ceiling is emitted as one or more PARTS (a sloped strip plus the
      // flat remainder of a knee profile, two planes plus an optional plateau
      // for a gable, one plane otherwise). Each part is its own mesh prim.
      parts: [],
      ridgeLines: [],
    };

    /* ---- 1. explicit source ceiling: real measured planes --------------- */
    if (zone.source === 'explicit') {
      const geoms = (zone.geometry || []).filter((g) => g && Array.isArray(g.points) && g.points.length >= 3);
      if (!geoms.length) {
        warnings.push({ code: 'usdz.ceiling-no-polygon', message: `Room "${label || base.roomIdentifier || base.key}" has an explicit ceiling array but no usable polygon (USDZ): no ceiling emitted rather than an invented one.` });
        continue;
      }
      const fe = floorElevation(model, zone);
      base.floorY = fe.y;
      base.floorBasis = fe.basis;
      base.method = 'explicit';
      base.coverage = 'source-derived';
      let min = Infinity;
      let max = -Infinity;
      for (const g of geoms) {
        for (const p of g.points) { if (p[1] < min) min = p[1]; if (p[1] > max) max = p[1]; }
        base.surfaces.push({ points: g.points.map((p) => [p[0], p[1], p[2]]), kind: 'flat' });
      }
      base.heightMin = min - fe.y;
      base.heightMax = max - fe.y;
      if (!(base.heightMin > 0.3)) {
        warnings.push({ code: 'usdz.ceiling-height-implausible', message: `Room "${label || base.roomIdentifier}" explicit ceiling sits ${base.heightMin.toFixed(3)} m above the floor datum (${fe.basis}): height reported as measured, not corrected.` });
      }
      base.heightLabel = heightLabel(base.heightMin, base.heightMax);
      // An explicit source ceiling is emitted as ONE prim when the producer's
      // polygons are all at the same elevation (a flat ceiling cut into two
      // plates is still one ceiling, not a split), and one prim per plane when
      // they genuinely differ. Nothing is re-derived from the walls here.
      const ysAll = base.surfaces.reduce((a, sf) => a.concat(sf.points.map((p) => p[1])), []);
      const sameLevel = Math.max(...ysAll) - Math.min(...ysAll) < 0.005;
      base.parts = sameLevel
        ? [makePart('flat', base.surfaces.map((sf) => sf.points), fe.y, 'explicit')]
        : base.surfaces.map((sf) => makePart(sf.kind, sf.points, fe.y, 'explicit'));
      ceilings.push(base);
      continue;
    }

    /* ---- 2. reconstruction: needs a footprint -------------------------- */
    if (!base.polygon) {
      warnings.push({ code: 'usdz.ceiling-no-polygon', message: `Zone ${base.key} (story ${base.story}) has no room/floor polygon: no USDZ ceiling emitted (a ceiling without a footprint would be invented geometry).` });
      continue;
    }
    const fe = floorElevation(model, zone);
    base.floorY = fe.y;
    base.floorBasis = fe.basis;

    const hmin = finite(zone.heightMin) ? zone.heightMin : null;
    const hmax = finite(zone.heightMax) ? zone.heightMax : null;
    const method = zone.method;
    const approximated = !(method === 'flat' || method === 'knee' || method === 'section')
      || hmin == null || hmax == null || !(hmax >= hmin);
    if (approximated) {
      // Determinable fallback ONLY: a flat plane at the knee height. Never a
      // made-up slope direction, and every room says so.
      const knee = finite(zone.kneeHeightM) ? zone.kneeHeightM : (finite(zone.wallHeightM) ? zone.wallHeightM : hmin);
      if (knee == null || !(knee > 0)) {
        warnings.push({ code: 'usdz.ceiling-approximated', message: `Zone ${base.key}: ceiling method "${method || 'unknown'}" has no measured height (knee/ridge unavailable) — no ceiling emitted.` });
        continue;
      }
      base.method = method || 'unavailable';
      base.surfaces = [{ points: lift(base.polygon, fe.y, () => knee), kind: 'flat' }];
      base.parts = [makePart('flat', base.surfaces[0].points, fe.y, base.method)];
      base.heightMin = knee;
      base.heightMax = knee;
      base.heightLabel = heightLabel(knee, knee);
      warnings.push({ code: 'usdz.ceiling-approximated', message: `Zone ${base.key}: ceiling method "${method || 'unknown'}" is not geometrically determinable — emitted as a flat plane at the knee height ${knee.toFixed(2)} m (approximation, not a measured slope).` });
      ceilings.push(base);
      continue;
    }

    base.method = method;
    base.heightMin = hmin;
    base.heightMax = hmax;
    base.heightLabel = heightLabel(hmin, hmax);
    if (method === 'flat' || hmax - hmin < 0.005) {
      // A flat ceiling is ONE prim at the measured wall height: no strip, no
      // split, nothing to interpolate.
      base.surfaces = [{ points: lift(base.polygon, fe.y, () => hmax), kind: 'flat' }];
      base.parts = [makePart('flat', base.surfaces[0].points, fe.y, 'flat')];
      base.heightMin = base.heightMax = hmax;
      ceilings.push(base);
      continue;
    }

    /* ---- 3. sloped: a knee band that reaches the ridge, then FLAT ------ */
    // The old code interpolated ONE plane across the whole footprint, which
    // drew a single tilted sheet cutting through the room. The measured
    // section says otherwise: the slope only spans `run` next to the low wall
    // and everything past it is flat at the ridge.
    const fd = zone.fallDirection;
    const tan = slopeTangent(zone.section);
    base.slopeTangent = tan;
    const section = zone.section || null;
    const segs = section && Array.isArray(section.segments) ? section.segments : [];
    const widest = (list) => list.reduce((a, s) => (a == null || s.run > a.run ? s : a), null);
    const slopeSeg = widest(segs.filter((s) => s.isSlope && finite(s.run) && s.run > 0 && finite(s.rise)));
    const flatSeg = widest(segs.filter((s) => !s.isSlope && finite(s.run)));
    const knee = finite(zone.kneeHeightM) ? zone.kneeHeightM : hmin;
    const ridge = finite(zone.ridgeHeightM) ? zone.ridgeHeightM : hmax;
    // fallDirection.u is a PLAN vector (plan y = -source z) while the footprint
    // is [x, z]: the z component has to flip, or the band lands on the wrong
    // side of the room (the previous interpolation did exactly that).
    const uPlan = fd && Array.isArray(fd.u) && Math.hypot(fd.u[0], fd.u[1]) > 1e-6
      ? [fd.u[0], -fd.u[1]] : null;
    // Which side is the knee? The reconstruction names the section wall; if it
    // is not a wall of this footprint the strip is anchored on the lowest edge
    // along the fall direction instead, and the file says so.
    const sectionWall = section && section.wallId != null && Array.isArray(zone.walls)
      ? zone.walls.find((w) => w && String(w.identifier) === String(section.wallId)) : null;
    const sideFromData = Boolean(uPlan && sectionWall && fd && typeof fd.downhill === 'string');
    if (!(hmax - hmin > 0.005) || !slopeSeg || !(slopeSeg.rise > 0.01)) {
      // No measurable slope in the profile: the whole ceiling is FLAT.
      base.method = 'flat';
      base.surfaces = [{ points: lift(base.polygon, fe.y, () => (finite(ridge) ? ridge : hmax)), kind: 'flat' }];
      base.parts = [makePart('flat', base.surfaces[0].points, fe.y, 'flat')];
      base.heightMin = base.heightMax = finite(ridge) ? ridge : hmax;
      base.heightLabel = heightLabel(base.heightMin, base.heightMax);
      ceilings.push(base);
      continue;
    }
    if (!uPlan) {
      base.surfaces = [{ points: lift(base.polygon, fe.y, () => hmax), kind: 'flat' }];
      base.parts = [makePart('flat', base.surfaces[0].points, fe.y, 'flat')];
      base.heightMin = base.heightMax = hmax;
      base.heightLabel = heightLabel(hmax, hmax);
      warnings.push({ code: 'usdz.ceiling-approximated', message: `Zone ${base.key}: sloped ceiling has no usable fall direction — emitted flat at the ridge height ${hmax.toFixed(2)} m instead of an invented slope.` });
      ceilings.push(base);
      continue;
    }
    const gable = fd.downhill === 'both' && hmax - hmin > 0.05;
    base.ridge = gable;
    const split = splitCeilingPlan(base.polygon, uPlan, fd.downhill, {
      run: slopeSeg.run,
      knee: finite(knee) ? knee : hmin,
      ridge: finite(ridge) ? ridge : hmax,
      flatRun: flatSeg ? flatSeg.run : 0,
    });
    if (!split || !split.parts.length) {
      base.surfaces = [{ points: lift(base.polygon, fe.y, () => hmax), kind: 'flat' }];
      base.parts = [makePart('flat', base.surfaces[0].points, fe.y, 'flat')];
      base.heightMin = base.heightMax = hmax;
      base.heightLabel = heightLabel(hmax, hmax);
      warnings.push({ code: 'usdz.ceiling-approximated', message: `Zone ${base.key}: the roof section could not be laid over the footprint — emitted flat at the ridge height ${hmax.toFixed(2)} m.` });
      ceilings.push(base);
      continue;
    }
    if (!sideFromData) {
      warnings.push({
        code: 'usdz.ceiling-side-assumed',
        message: `Zone ${base.key}: the knee side could not be tied to a wall of this footprint (section wall ${section && section.wallId ? `"${section.wallId}"` : 'unnamed'}); the sloped strip was anchored on the lowest edge along the fall direction instead.`,
      });
    }
    base.parts = split.parts.map((p) => {
      const points = lift(p.poly, fe.y, p.heightAt);
      return makePart(p.kind, points, fe.y, p.kind === 'flat' ? 'flat' : (base.method === 'knee' ? 'knee' : (base.method || 'knee')));
    });
    base.surfaces = base.parts.map((p) => ({ points: p.points, kind: p.kind }));
    base.ridgeLines = split.ridgeLines;
    base.ridgeLine = split.ridgeLines.length ? split.ridgeLines[0] : null;
    // Slope of the BAND as built (rise/run of the strip), not the section-wide
    // average surplus/span: a reader comparing the mesh with this number must
    // get the same answer.
    base.sectionSlopeTangent = tan;
    base.slopeTangent = split.run > 0 && finite(ridge) && finite(knee) ? (ridge - knee) / split.run : tan;
    base.slopeRun = split.run;
    base.bandArea = base.parts.filter((p) => p.kind === 'slope').reduce((a, p) => a + p.area, 0);
    base.flatArea = base.parts.filter((p) => p.kind === 'flat').reduce((a, p) => a + p.area, 0);
    base.heightMin = Math.min(...base.parts.map((p) => p.heightMin));
    base.heightMax = Math.max(...base.parts.map((p) => p.heightMax));
    base.heightLabel = heightLabel(base.heightMin, base.heightMax);
    ceilings.push(base);
  }
  return { ceilings, warnings };
}

/** "2.50" for a flat ceiling, "1.60-2.50" for a sloped one. */
function heightLabel(min, max) {
  if (!finite(min) || !finite(max)) return null;
  const lo = min.toFixed(2);
  const hi = max.toFixed(2);
  return Math.abs(max - min) < 0.005 ? lo : `${lo}-${hi}`;
}

/**
 * Heights for labels: per room key (`room:<identifier>`) and per story.
 * Already in metres above the floor datum, never a ceiling area in disguise.
 */
function ceilingHeights(model) {
  const { ceilings } = ceilingSolids(model);
  const byRoom = new Map();
  const byStory = new Map();
  for (const c of ceilings) {
    if (c.roomIdentifier != null) byRoom.set(String(c.roomIdentifier), c);
    const s = finite(c.story) ? c.story : 0;
    const cur = byStory.get(s);
    if (!cur) byStory.set(s, { min: c.heightMin, max: c.heightMax, heightLabel: c.heightLabel, methods: new Set([c.method]), items: 1, area: c.area || 0 });
    else {
      cur.min = Math.min(cur.min, c.heightMin);
      cur.max = Math.max(cur.max, c.heightMax);
      // the story label must show the widest range the floor actually has
      cur.heightLabel = heightLabel(cur.min, cur.max);
      cur.methods.add(c.method);
      cur.items += 1;
      cur.area += c.area || 0;
    }
  }
  return { byRoom, byStory, ceilings };
}

module.exports = { ceilingSolids, ceilingHeights, heightLabel, splitCeilingPlan, planArea, boundarySegment };
