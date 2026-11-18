'use strict';
/**
 * Ceiling reconstruction from wall-top geometry (port of the ArchiDrawing
 * web engine's ceiling/height core, G1 -> roomplan-dxf).
 *
 * This module is the FALLBACK layer only. Precedence is enforced by the
 * callers (lib/ceilings.js, lib/quantities.js) and reported here as
 * `status`:
 *
 *   supplied            explicit source ceiling polygon (rooms[].ceiling /
 *                       ceiling_curr) — reconstruction must never run
 *   reconstructed       knee-wall method: floor + measured slope surplus
 *                       over the measured knee-wall length
 *   reconstructed-bound section bound: no knee wall matched, slope assumed
 *                       to run over the whole footprint (upper bound)
 *   estimated           extrusion: no floor polygon at all, area from wall
 *                       envelope only — may overestimate, warning required
 *   unavailable         nothing to reconstruct from
 *
 * Ported from .../ArchiDrawing-initial/web/geometry.js (read-only source):
 * topProfile, topEdgeSloped, wallHeightAt, slopeCutTriangles, profileLength,
 * wallSegment, reconstructCeilingForRoom, reconstructCeiling, ceilingByZone,
 * KNEE_MATCH_TOL_M, KNEE_SIDE_TOL_M, SLOPE_PARALLEL_TOL_DEG.
 * UI/report/DOM code and north-bearing code are deliberately NOT ported.
 *
 * Deliberate fixes over the reference engine (documented so they are not
 * "corrected" back):
 *  1. A flat ceiling returns ceilingArea = floorArea INSIDE
 *     reconstructCeilingForRoom. The reference left ceilingArea null and
 *     relied on every caller to patch it; both callers here (DXF and
 *     quantities) would otherwise have to duplicate that step.
 *  2. The extrusion branch always carries a warning that the estimate has no
 *     floor polygon (estimated coverage).
 *  3. Non-parallel slopes produce a warning, not just a diagnostic flag; the
 *     number is still returned because a single-section answer is the most
 *     useful bound available.
 *  4. Walls without polygonCorners are usable evidence: their height is
 *     dimensions.y (RoomPlan only emits corners for irregular walls), so a
 *     knee wall can still be identified on real scans.
 */

// Two sloped walls count as facing the same way (one extrusion direction)
// when their headings agree modulo 180 degrees.
const SLOPE_PARALLEL_TOL_DEG = 15;
// A knee wall's top edge sits at the roof section's knee height, so matching
// wall height against that knee identifies it outright (the reference scan
// measured 1.649 m for both) instead of by heuristic.
const KNEE_MATCH_TOL_M = 0.06;
// Knee walls this close along the section axis are the same side of the roof:
// wide enough to re-join a side split by a doorway, narrow enough not to merge
// the opposite sides of a real room.
const KNEE_SIDE_TOL_M = 0.5;
// Top edge must vary by more than this to count as sloped at all.
const SLOPE_MIN_RISE_M = 0.05;
// Per-segment rise that counts as one sloping run of the roof section.
const SEGMENT_MIN_RISE_M = 0.02;
// A "roof section" lower than this is not a roof: RoomPlan emits partial-height
// walls (under-window walls, half walls) whose polygon top edge looks sloped but
// belongs to a 1.1 m stub, not to the room's ceiling.

const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const { envelopeArea } = require('./polygon-union');

function cornersOf(w) {
  return Array.isArray(w && w.polygonCorners)
    ? w.polygonCorners.filter((p) => p && finite(p.x) && finite(p.y) && finite(p.z))
    : [];
}

function dimsOf(w) {
  const d = (w && w.dimensions) || {};
  // accepts both the source array form and the decoded {x,y,z} form
  if (Array.isArray(d)) return [finite(d[0]) ? d[0] : 0, finite(d[1]) ? d[1] : 0, finite(d[2]) ? d[2] : 0];
  return [finite(d.x) ? d.x : 0, finite(d.y) ? d.y : 0, finite(d.z) ? d.z : 0];
}

/** Upper envelope of the wall polygon: for each local x keep the highest
 * point, so knee points survive even when a slope reaches floor level. */
function topProfile(w) {
  const c = cornersOf(w);
  if (c.length < 3) return { minY: 0, maxY: 0, pts: [], hasProfile: false };
  const ys = c.map((p) => p.y);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const byX = new Map();
  for (const p of c) {
    const k = Math.round(p.x * 100);
    if (!byX.has(k) || p.y > byX.get(k)[1]) byX.set(k, [p.x, p.y]);
  }
  const pts = [...byX.values()].sort((a, b) => a[0] - b[0]);
  return { minY, maxY, pts, hasProfile: pts.length > 0 };
}

/** Slope = the top edge actually varies; a polygon alone is not enough (a wall
 * can be non-rectangular because of an angled side edge with a flat top). */
function topEdgeSloped(w) {
  const { pts } = topProfile(w);
  if (pts.length < 2) return false;
  const hs = pts.map((p) => p[1]);
  return Math.max(...hs) - Math.min(...hs) > SLOPE_MIN_RISE_M;
}

/** Wall height at a local x along its length. Flat walls answer with
 * dimensions.y everywhere; a sloped one reads its top edge off the polygon.
 * Integrating this reproduces the polygon area exactly. */
function wallHeightAt(w, localX) {
  const d = dimsOf(w);
  const { minY, pts } = topProfile(w);
  if (!pts.length) return d[1];
  if (localX <= pts[0][0]) return pts[0][1] - minY;
  const last = pts[pts.length - 1];
  if (localX >= last[0]) return last[1] - minY;
  for (let i = 0; i < pts.length - 1; i++) {
    if (localX <= pts[i + 1][0]) {
      const span = pts[i + 1][0] - pts[i][0];
      const t = span > 0 ? (localX - pts[i][0]) / span : 0;
      return pts[i][1] + t * (pts[i + 1][1] - pts[i][1]) - minY;
    }
  }
  return last[1] - minY;
}

/** The roof cuts one triangle out of the wall rectangle per sloping segment:
 * m2 = W*H - sum(dW*dH/2). Returned so a gross area that is not W*H can be
 * reconciled in the report instead of reading as a mistake. */
function slopeCutTriangles(w) {
  const d = dimsOf(w);
  const c = cornersOf(w);
  if (c.length < 3) return { triangles: [], cutArea: 0, W: d[0], H: d[1], hasProfile: false };
  const { pts, minY, maxY } = topProfile(w);
  const triangles = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const dW = Math.abs(pts[i + 1][0] - pts[i][0]);
    const dH = Math.abs(pts[i + 1][1] - pts[i][1]);
    if (dH > SEGMENT_MIN_RISE_M) triangles.push({ dW, dH, area: (dW * dH) / 2 });
  }
  return {
    triangles,
    cutArea: triangles.reduce((a, t) => a + t.area, 0),
    W: d[0],
    H: maxY - minY, // from the polygon, not dimensions.y — both sides must read the same shape
    hasProfile: true,
  };
}

function profileLength(pts) {
  let len = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    len += Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
  }
  return len;
}

/** Wall centre line in plan (source XZ); transform is column-major. */
function wallSegment(w) {
  const t = Array.isArray(w && w.transform) && w.transform.length === 16 ? w.transform : null;
  const len = dimsOf(w)[0];
  if (!t || ![t[0], t[2], t[12], t[14]].every(finite)) return { p1: [0, 0], p2: [len, 0], len };
  let dx = t[0], dz = t[2];
  const n = Math.hypot(dx, dz) || 1;
  dx /= n; dz /= n;
  const cx = t[12], cz = t[14], h = len / 2;
  return { p1: [cx - dx * h, cz - dz * h], p2: [cx + dx * h, cz + dz * h], len };
}

/** Normalise a decoded wall surface into the shape the core needs. */
function profileWall(s) {
  const d = dimsOf(s);
  const { pts, maxY, minY, hasProfile } = topProfile(s);
  const hasSlope = topEdgeSloped(s);
  const height = hasProfile ? maxY - minY : d[1]; // dimensions.y only when no polygon exists
  return {
    identifier: s && s.identifier != null ? s.identifier : null,
    dimensions: d,
    polygonCorners: cornersOf(s),
    transform: s && s.transform,
    hasSlope,
    hasProfile,
    height,
    length: d[0],
    profileLength: pts.length ? profileLength(pts) : 0,
  };
}

function sectionWallOfWalls(profileWalls, section) {
  return profileWalls.find((w) => w.identifier === section.wallId) || profileWalls[0];
}

function typicalHeight(flatWalls) {
  const hs = flatWalls.map((w) => w.height).filter((h) => finite(h) && h > 0.3).sort((a, b) => a - b);
  if (!hs.length) return null;
  const mid = Math.floor(hs.length / 2);
  return hs.length % 2 ? hs[mid] : (hs[mid - 1] + hs[mid]) / 2;
}

/**
 * Ceiling of ONE room / zone from its own walls.
 *
 * Reference algorithm, unchanged in substance: ceiling = floor + surplus each
 * roof slope adds over its own horizontal projection, where the length the
 * slope runs for is the MEASURED knee-wall length rather than a guessed whole
 * section length. Guarantees: surplus >= 0 (ceiling >= floor) and
 * ceiling <= floor * sectionRatio (a slope covering the entire footprint).
 */
function reconstructCeilingForRoom(rawWalls, floorArea) {
  const walls = (rawWalls || []).map(profileWall);
  const floor = finite(floorArea) && floorArea > 0 ? floorArea : null;
  if (!walls.length) {
    return {
      flat: null, method: null, status: 'unavailable', coverage: 'unavailable',
      ceilingArea: null, floorArea: floor, profiles: [], warnings: [],
      reason: 'no wall surfaces in this room/zone; nothing to reconstruct a ceiling from',
    };
  }

  // Height alone cannot invalidate a measured slope or make it a knee wall.
  const profileWalls = walls.filter((w) => w.hasSlope);
  const flatWalls = walls.filter((w) => !w.hasSlope);

  if (!profileWalls.length) {
    // No sloped top edge on any wall -> flat ceiling = floor footprint.
    // FIX #1: the area is resolved here, never left to the caller.
    const h = typicalHeight(flatWalls);
    return {
      flat: true, method: 'flat', status: floor != null ? 'reconstructed' : 'unavailable',
      coverage: floor != null ? 'computed' : 'unavailable',
      ceilingArea: floor, floorArea: floor,
      wallHeightM: h, heightMin: h, heightMax: h,
      profiles: [], kneeWallIds: [], warnings: [],
      reason: floor != null
        ? 'no wall top edge varies by more than 0.05 m: flat ceiling, ceiling area = measured floor footprint'
        : 'flat ceiling but no floor polygon/room area to size it',
    };
  }

  const profiles = profileWalls.map((w) => {
    const { minY, maxY, pts } = topProfile(w);
    const segments = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const [x1, y1] = pts[i], [x2, y2] = pts[i + 1];
      const run = Math.abs(x2 - x1), rise = Math.abs(y2 - y1);
      const isSlope = rise > SEGMENT_MIN_RISE_M;
      const angleDeg = !isSlope ? 0 : run > 0.001 ? (Math.atan(rise / run) * 180) / Math.PI : 90;
      segments.push({ run, rise, isSlope, angleDeg, length: Math.hypot(run, rise) });
    }
    const heights = pts.map((p) => p[1] - minY);
    const kneeWallHeight = heights.length ? Math.min(...heights) : maxY - minY;
    // Horizontal span and surplus both read off THIS polygon, so the ratio
    // between them stays self-consistent (dimensions.x deliberately unused).
    const span = segments.reduce((a, s) => a + s.run, 0);
    const surplus = segments.reduce((a, s) => a + (s.isSlope ? s.length - s.run : 0), 0);
    return {
      wallId: w.identifier, ridgeHeight: maxY - minY, kneeWallHeight,
      segments, profileLength: profileLength(pts), span, surplus,
    };
  });

  // The widest sloped wall sees most of the room's cross-section; blending it
  // with a narrow stub wall's partial view invents a phantom section.
  const section = profiles.reduce((a, p) => (p.span > a.span ? p : a));
  const sectionRatio = section.span > 0 ? section.profileLength / section.span : 1;
  const upperBound = floor != null ? floor * sectionRatio : null;

  // A roof changing in BOTH directions breaks the single-section assumption;
  // sloped walls facing different ways are the signal.
  const dirs = profileWalls.map((w) => {
    const s = wallSegment(w);
    return ((((Math.atan2(s.p2[1] - s.p1[1], s.p2[0] - s.p1[0]) * 180) / Math.PI) % 180) + 180) % 180;
  });
  const notParallel = dirs.some((a) => dirs.some((b) => {
    const d = Math.abs(a - b) % 180;
    return Math.min(d, 180 - d) > SLOPE_PARALLEL_TOL_DEG;
  }));

  // Fall direction in PLAN coordinates: the section wall runs along the slope
  // (its length spans eave -> ridge), so its direction is the fall line.
  // Plan y is -source z (see lib/transform project()), hence the z sign flip.
  const secSeg = wallSegment(sectionWallOfWalls(profileWalls, section));
  const fdx = secSeg.p2[0] - secSeg.p1[0], fdz = secSeg.p2[1] - secSeg.p1[1];
  const fLen = Math.hypot(fdx, fdz) || 1;
  const p0Height = section.segments.length ? topProfile(profileWalls.find((w) => w.identifier === section.wallId) || profileWalls[0]).pts : null;
  let downhill = 'both';
  if (p0Height && p0Height.length >= 2) {
    const h0 = p0Height[0][1], h1 = p0Height[p0Height.length - 1][1];
    if (Math.abs(h1 - h0) > 0.05) downhill = h1 > h0 ? 'minus' : 'plus'; // +u end is local +x
  }
  const fallDirection = { u: [fdx / fLen, -fdz / fLen], downhill };

  // Length the slope runs for, measured from the knee walls. Knee walls run
  // parallel to the ridge and each side spans the room's full length, so one
  // side's length is the whole answer; group by side, take the longest.
  const kneeWalls = flatWalls.filter((w) =>
    finite(w.height) && w.height > 0.3 &&
    Math.abs(w.height - section.kneeWallHeight) <= KNEE_MATCH_TOL_M &&
    w.height < section.ridgeHeight - KNEE_MATCH_TOL_M);
  const slopeCount = section.segments.filter((s) => s.isSlope).length; // diagnostic only

  const sectionWall = profileWalls.find((w) => w.identifier === section.wallId) || profileWalls[0];
  const sectionSeg = wallSegment(sectionWall);
  const sdx = sectionSeg.p2[0] - sectionSeg.p1[0], sdz = sectionSeg.p2[1] - sectionSeg.p1[1];
  const sLen = Math.hypot(sdx, sdz) || 1;
  const ax = sdx / sLen, az = sdz / sLen;
  const kneeSides = [];
  for (const w of kneeWalls) {
    const c = wallSegment(w);
    const offset = ((c.p1[0] + c.p2[0]) / 2) * ax + ((c.p1[1] + c.p2[1]) / 2) * az;
    let side = kneeSides.find((s) => Math.abs(s.offset - offset) < KNEE_SIDE_TOL_M);
    if (!side) { side = { offset, length: 0, wallIds: [] }; kneeSides.push(side); }
    side.length += dimsOf(w)[0];
    side.wallIds.push(w.identifier);
  }
  const slopeExtent = kneeSides.length ? Math.max(...kneeSides.map((s) => s.length)) : null;

  const base = {
    flat: false, profiles, section, sectionRatio, floorArea: floor,
    slopeSurplus: section.surplus, slopeExtent, slopeCount, kneeSides,
    kneeWallIds: kneeWalls.map((w) => w.identifier),
    ridgeHeightM: section.ridgeHeight, kneeHeightM: section.kneeWallHeight,
    heightMin: section.kneeWallHeight, heightMax: section.ridgeHeight,
    notParallel, fallDirection, profileWallCount: profileWalls.length, wallCount: walls.length,
    ignoredShortSlopedWalls: [], // no height-only exclusion
  };
  const warnings = [];
  let ceilingArea = null, method = null, status = null, coverage = null, reason = null, roomLength = null;

  if (floor != null && slopeExtent != null) {
    // clamped: the slope cannot add more than it would covering the whole floor
    ceilingArea = Math.min(floor + section.surplus * slopeExtent, upperBound);
    method = 'knee'; status = 'reconstructed'; coverage = 'computed';
    reason = `floor ${floor.toFixed(3)} m2 + slope surplus ${section.surplus.toFixed(3)} m2 over measured knee-wall length ${slopeExtent.toFixed(3)} m (clamped to the section bound ${upperBound.toFixed(3)} m2)`;
  } else if (upperBound != null) {
    // no knee wall found — assume the slope runs the full footprint
    ceilingArea = upperBound;
    method = 'section'; status = 'reconstructed-bound'; coverage = 'estimated';
    reason = `no wall height matched the section knee ${section.kneeWallHeight.toFixed(3)} m within ${KNEE_MATCH_TOL_M} m; slope assumed to run over the whole ${floor.toFixed(3)} m2 footprint (upper bound, section ratio ${sectionRatio.toFixed(3)})`;
    warnings.push({
      code: 'roomplan.ceiling-reconstruction-section-bound',
      reason: 'reconstructed-bound: knee wall not identified, ceiling area is floor x section ratio (an upper bound), not a measured knee length',
    });
  } else {
    // no floor polygon for this room at all: last resort, the extrusion
    if (profileWalls.length >= 2) {
      const centers = profileWalls.map((w) => [w.transform ? w.transform[12] : 0, w.transform ? w.transform[14] : 0]);
      for (let i = 0; i < centers.length; i++) {
        for (let j = i + 1; j < centers.length; j++) {
          const d = Math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1]);
          if (roomLength === null || d > roomLength) roomLength = d;
        }
      }
    }
    if (roomLength === null && flatWalls.length) roomLength = Math.max(...flatWalls.map((w) => dimsOf(w)[0]));
    ceilingArea = roomLength ? section.profileLength * roomLength : null;
    method = 'extrusion';
    status = ceilingArea != null ? 'estimated' : 'unavailable';
    coverage = ceilingArea != null ? 'estimated' : 'unavailable';
    reason = ceilingArea != null
      ? `no floor polygon: slope profile length ${section.profileLength.toFixed(3)} m x wall-to-wall extent ${roomLength.toFixed(3)} m; may overestimate`
      : 'no floor polygon and no wall extent: cannot extrude a ceiling';
    // FIX #2: the estimate without a floor polygon must always warn
    warnings.push({
      code: 'roomplan.ceiling-reconstruction-extrusion',
      reason: 'estimated: extrusion from wall geometry only, no floor polygon was available — area is not a measured footprint and may be too large',
    });
  }

  // FIX #3: non-parallel slopes are a warning, and the value is still returned
  if (notParallel) {
    warnings.push({
      code: 'roomplan.ceiling-reconstruction-not-parallel',
      reason: `sloped walls face directions more than ${SLOPE_PARALLEL_TOL_DEG} degrees apart: a single roof section cannot describe this ceiling, area is reported but flagged`,
    });
  }
  if (ceilingArea != null && floor != null && ceilingArea + 1e-9 < floor) {
    // arithmetic guard: the surplus decomposition makes this impossible
    warnings.push({ code: 'roomplan.ceiling-reconstruction-below-floor', reason: 'reconstructed ceiling smaller than the floor it covers; arithmetic guard' });
  }

  return {
    ...base, ceilingArea, method, status, coverage, reason, upperBound,
    roomLength, warnings, flat: false,
  };
}

// ---------------------------------------------------------------- zones ----

function shoelace2D(pts) {
  let a = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % pts.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

function inPolygon2D(p, poly, tol = 1e-7) {
  let yes = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[j], b = poly[i];
    if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]) yes = !yes;
  }
  if (yes) return true;
  // boundary tolerance, so a wall sitting exactly on the room outline counts
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[j], b = poly[i];
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy);
    if (l < 1e-9) continue;
    const t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (l * l);
    if (t < -tol / l || t > 1 + tol / l) continue;
    const qx = a[0] + t * dx, qy = a[1] + t * dy;
    if (Math.hypot(p[0] - qx, p[1] - qy) <= tol) return true;
  }
  return false;
}

function wallCentre2D(w) {
  const t = w && w.transform;
  if (!Array.isArray(t) || t.length !== 16 || !finite(t[12]) || !finite(t[14])) return null;
  return [t[12], t[14]];
}

/** Local -> source world; transform is column-major 4x4. */
function worldPoint(p, t) {
  return [
    t[0] * p[0] + t[4] * p[1] + t[8] * p[2] + t[12],
    t[1] * p[0] + t[5] * p[1] + t[9] * p[2] + t[13],
    t[2] * p[0] + t[6] * p[1] + t[10] * p[2] + t[14],
  ];
}

function floorZoneOf(s) {
  if (!s || !Array.isArray(s.polygonCorners) || s.polygonCorners.length < 3) return null;
  if (!Array.isArray(s.transform) || s.transform.length !== 16) return null;
  const pts = s.polygonCorners.map((p) => worldPoint([p.x, p.y, p.z], s.transform));
  if (pts.some((p) => p.some((v) => !finite(v)))) return null;
  return { poly: pts.map((p) => [p[0], p[2]]), area: shoelace2D(pts.map((p) => [p[0], p[2]])), y: pts.reduce((a, p) => a + p[1], 0) / pts.length };
}

function roomZoneOf(r) {
  if (!Array.isArray(r.vertices) || r.vertices.length < 3) return null;
  const poly = r.vertices.map((v) => [v.x, v.z]);
  if (poly.some((p) => !p.every(finite))) return null;
  return { poly, area: shoelace2D(poly), y: null };
}

function hasExplicitCeiling(room) {
  if (!room) return false;
  const a = Array.isArray(room.ceiling) ? room.ceiling : [];
  const b = Array.isArray(room.ceilingCurrent) ? room.ceilingCurrent : [];
  return a.length > 0 || b.length > 0;
}

/** Newell-type area of an explicit source ceiling polygon, in source units. */
function explicitCeilingGeometry(entry) {
  if (!entry || !Array.isArray(entry.transform) || entry.transform.length !== 16) return null;
  if (['holes', 'holeRings', 'interiors'].some(k => entry[k] && entry[k].length)) throw new Error('planar-polygon: unsupported ceiling hole rings; decompose into simple faces');
  if (Array.isArray(entry.polygon) && Array.isArray(entry.polygon[0]) && Array.isArray(entry.polygon[0][0])) throw new Error('planar-polygon: unsupported nested ceiling hole rings');
  let local = null;
  if (Array.isArray(entry.polygon) && entry.polygon.length >= 3) {
    local = entry.polygon.map((q) => (Array.isArray(q) && q.length === 2 ? { x: q[0], y: q[1], z: 0 } : null));
  } else if (Array.isArray(entry.polygonCorners) && entry.polygonCorners.length >= 3) {
    local = entry.polygonCorners.map((q) => (Array.isArray(q) && q.length === 3 ? { x: q[0], y: q[1], z: q[2] } : q));
  }
  if (!local || local.some((q) => !q || ![q.x, q.y, q.z].every(finite))) return null;
  const pts = local.map((q) => worldPoint([q.x, q.y, q.z], entry.transform));
  if (pts.some((p) => p.some((v) => !finite(v)))) return null;
  // planar Newell area + plan projection (the footprint the ceiling covers)
  let n = [0, 0, 0];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    n[0] += (a[1] - b[1]) * (a[2] + b[2]);
    n[1] += (a[2] - b[2]) * (a[0] + b[0]);
    n[2] += (a[0] - b[0]) * (a[1] + b[1]);
  }
  const area = Math.hypot(...n) / 2;
  if (!(area > 1e-6)) return null;
  // Validate the source ring without rejecting vertical measured upstands.
  require('./planar-polygon').triangulate(pts);
  const ys = pts.map((p) => p[1]);
  return {
    area,
    planPolygon: pts.map((p) => [p[0], p[2]]),
    yMin: Math.min(...ys),
    yMax: Math.max(...ys),
    points: pts,
  };
}

/**
 * Zones of a decoded capture: one per supplied room, plus one per remaining
 * source-room/story group of walls (the raw CapturedRoom case, where the whole
 * capture has no room polygons). This is the "ceilingByZone" idea from the
 * reference engine, expressed on the roomplan-dxf capture model.
 */
function collectZones(model) {
  const surfaces = (model && model.surfaces) || [];
  const walls = surfaces.filter((s) => s.kind === 'wall');
  const floors = surfaces.filter((s) => s.kind === 'floor');
  const zones = [];
  const used = new Set();
  const rooms = Array.isArray(model && model.rooms) ? model.rooms : [];

  for (const r of rooms) {
    const rz = roomZoneOf(r);
    const story = finite(r.story) ? r.story : 0;
    const mine = walls.filter((w) => {
      if (used.has(w)) return false;
      if (w.sourceRoomIndex != null && r.sourceRoomIndex != null && w.sourceRoomIndex === r.sourceRoomIndex) return true;
      if (w.sourceRoomIdentifier && r.identifier && w.sourceRoomIdentifier === r.identifier) return true;
      const c = wallCentre2D(w);
      return !!(c && rz && inPolygon2D(c, rz.poly, 0.02));
    });
    mine.forEach((w) => used.add(w));
    const storyFloors = floors.filter((f) => (finite(f.story) ? f.story : 0) === story);
    let floorArea = rz ? rz.area : null;
    let polygon = rz ? rz.poly : null;
    if (floorArea == null || !(floorArea > 0)) {
      const covering = storyFloors.map(floorZoneOf).filter(Boolean)
        .filter((f) => !polygon || f.poly.every((p) => inPolygon2D(p, polygon, 0.02)));
      const pool = covering.length ? covering : storyFloors.length === 1 ? [floorZoneOf(storyFloors[0])].filter(Boolean) : [];
      if (pool.length === 1) { floorArea = pool[0].area; polygon = polygon || pool[0].poly; }
    }
    zones.push({
      key: `room:${r.identifier != null ? r.identifier : zones.length}`,
      roomIdentifier: r.identifier != null ? r.identifier : null,
      label: r.label != null ? r.label : null,
      story, polygon, floorArea: floorArea > 0 ? floorArea : null,
      walls: mine, explicit: hasExplicitCeiling(r), room: r,
    });
  }

  const leftover = walls.filter((w) => !used.has(w));
  const groups = new Map();
  for (const w of leftover) {
    const key = w.sourceRoomIndex != null ? `source-room:${w.sourceRoomIndex}` : `story:${finite(w.story) ? w.story : 0}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(w);
  }
  for (const [key, ws] of groups) {
    const story = finite(ws[0].story) ? ws[0].story : 0;
    const srcIdx = ws[0].sourceRoomIndex != null ? ws[0].sourceRoomIndex : null;
    const own = floors.filter((f) => (srcIdx != null ? f.sourceRoomIndex === srcIdx : (finite(f.story) ? f.story : 0) === story));
    const fz = own.map(floorZoneOf).filter(Boolean);
    const area = fz.length ? fz.reduce((a, f) => a + f.area, 0) : null;
    // one polygon only when the zone is a single floor plate; several plates
    // have no single outline to draw, but the summed area is still usable
    const polygon = fz.length === 1 ? fz[0].poly : null;
    zones.push({
      key, roomIdentifier: null,
      label: null, story, polygon, floorArea: area && area > 0 ? area : null,
      walls: ws, explicit: false, room: null, sourceRoomIndex: srcIdx,
    });
  }
  return zones;
}

/** Per-zone ceiling decision: explicit source polygon first, then wall-top
 * reconstruction, then unavailable. Reconstruction NEVER runs over an explicit
 * ceiling. */
function zoneCeilings(model) {
  const out = [];
  for (const z of collectZones(model)) {
    if (z.explicit) {
      const room = z.room;
      const list = (Array.isArray(room.ceilingCurrent) && room.ceilingCurrent.length ? room.ceilingCurrent : room.ceiling) || [];
      const geoms = list.map(explicitCeilingGeometry).filter(Boolean);
      // ENVELOPE, not the sum of the supplied surfaces. Producers emit several
      // ceiling surfaces for one room that share the same plan footprint at
      // different heights ("stacked"), or overlapping roof pieces; summing them
      // double counted the same square metre (an anonymized regression example: three co-located
      // surfaces in one room = 3x the footprint). The ceiling quantity is the
      // plan union of the footprints, with each surface's own tilt kept.
      const env = geoms.length ? envelopeArea(geoms.map((g, i) => ({
        ref: `source-surface-${i + 1}`, planRing: g.planPolygon, surfaceAreaM2: g.area,
      }))) : null;
      const area = env && finite(env.envelopeAreaM2) ? env.envelopeAreaM2 : null;
      out.push({
        ...z, source: 'explicit', method: 'explicit', status: 'supplied',
        coverage: area != null ? 'source-derived' : 'unavailable',
        ceilingArea: area,
        ceilingEnvelope: env,
        envelopePlanAreaM2: env ? env.envelopePlanAreaM2 : null,
        surfaceAreaSumM2: env ? env.surfaceAreaSumM2 : null,
        stackedCount: env ? env.surfaceCount : 0,
        geometry: geoms,
        reason: area != null
          ? (env.usedFallback
            ? `explicit source ceiling polygon(s) SUMMED, not enveloped: a supplied surface has no plan footprint; ${env.surfaceCount} supplied surface(s), surface sum ${env.surfaceAreaSumM2.toFixed(3)} m2; wall-top reconstruction not run (explicit geometry always wins)`
            : `explicit source ceiling polygon(s) measured as a plan-union envelope, not a sum of surfaces; ${env.surfaceCount} supplied surface(s), ${(env.overlapAreaM2 || 0).toFixed(3)} m2 of footprint overlap counted once; surface sum ${env.surfaceAreaSumM2.toFixed(3)} m2 retained as a diagnostic; wall-top reconstruction not run (explicit geometry always wins)`)
          : 'explicit ceiling array present but no usable polygon; reconstruction deliberately skipped',
      });
      continue;
    }
    const part = reconstructCeilingForRoom(z.walls, z.floorArea);
    out.push({ ...z, ...part, source: 'reconstructed', ceilingArea: part.ceilingArea, geometry: null });
  }
  return out;
}

/** detectSlopedWalls: which walls carry a sloping top edge. Read from the RAW
 * local polygonCorners (x along the wall, y up) BEFORE any transform or
 * projection — dimensions.y is never used as slope evidence. */
function detectSlopedWalls(surfaces) {
  return (surfaces || [])
    .filter((s) => s && s.kind === 'wall')
    .map((s) => {
      const { pts, minY, maxY } = topProfile(s);
      const sloped = topEdgeSloped(s);
      const heights = pts.map((p) => p[1] - minY);
      return {
        identifier: s.identifier != null ? s.identifier : null,
        story: finite(s.story) ? s.story : 0,
        sloped,
        source: pts.length ? 'polygonCorners' : 'dimensions.y only (no local polygon)',
        ridgeHeightM: pts.length ? maxY - minY : (finite(s.dimensions && s.dimensions.y) ? s.dimensions.y : null),
        kneeHeightM: heights.length ? Math.min(...heights) : null,
        profileLengthM: pts.length ? profileLength(pts) : null,
      };
    })
    .filter((w) => w.sloped);
}

// Legacy-shaped helpers, kept close to the reference API so the maths can be
// cross-checked against the archived engine.

/** Per-room reconstruction over a decoded capture (reference reconstructCeiling). */
function reconstructCeiling(model) {
  const rooms = (model && model.rooms) || [];
  const surfaces = (model && model.surfaces) || [];
  if (!rooms.length) {
    const zones = collectZones(model);
    if (!zones.length) return null;
    const parts = zones.map((z) => ({ ...reconstructCeilingForRoom(z.walls, z.floorArea), zoneKey: z.key }));
    const known = parts.filter((p) => finite(p.ceilingArea));
    return {
      flat: parts.every((p) => p.flat === true),
      rooms: parts,
      ceilingArea: known.length === parts.length ? known.reduce((a, p) => a + p.ceilingArea, 0) : null,
    };
  }
  const parts = zoneCeilings(model).filter((z) => z.source === 'reconstructed');
  if (!parts.length) return null;
  const known = parts.filter((p) => finite(p.ceilingArea));
  return {
    flat: parts.every((p) => p.flat === true),
    rooms: parts,
    ceilingArea: known.length === parts.length ? known.reduce((a, p) => a + p.ceilingArea, 0) : null,
  };
}

/** Zone map form (reference ceilingByZone). */
function ceilingByZone(zones) {
  const map = new Map();
  for (const z of zones || []) {
    const part = reconstructCeilingForRoom(z.walls, z.floorArea);
    map.set(z.key, part);
  }
  return map;
}

module.exports = {
  SLOPE_PARALLEL_TOL_DEG, KNEE_MATCH_TOL_M, KNEE_SIDE_TOL_M, SLOPE_MIN_RISE_M, SEGMENT_MIN_RISE_M,
  topProfile, topEdgeSloped, wallHeightAt, slopeCutTriangles, profileLength, wallSegment,
  profileWall, reconstructCeilingForRoom, reconstructCeiling, ceilingByZone,
  collectZones, zoneCeilings, hasExplicitCeiling, explicitCeilingGeometry, shoelace2D,
  detectSlopedWalls,
};
