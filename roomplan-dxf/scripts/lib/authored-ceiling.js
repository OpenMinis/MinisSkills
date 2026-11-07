'use strict';
/**
 * authored-ceiling.js — a ceiling authored as a 3D surface: a plan polygon plus
 * one height per vertex (SPEC §5, G-5).
 *
 * Port of the native editor's `PlanEditorModel` quantities:
 *   - `ceilingAreaM2`      -> Newell area of the 3D loop (plan x/y + per-vertex z)
 *   - `netCeilingAreaM2`   -> ceilingArea - sum(hole plan areas) * (ceilingArea / floorArea)
 *   - `ceilingElevations`  -> `elevations` here; `hasAuthoredCeilingProfile` ->
 *                             the explicit "no authored profile" refusal below.
 *
 * A hole loop lies in the same ceiling plane as the whole surface, so its PLAN
 * area is scaled by the same slope factor the complete surface has. That is why
 * the factor is `ceilingArea / floorArea` and not a per-hole slope.
 *
 * Nothing is invented: without a polygon with >= 3 vertices AND one finite
 * height per vertex the answer is `null` with a reason, never the floor area
 * and never a rectangle substitute (SPEC §2.4).
 *
 * Pure JavaScript, zero dependencies, metres, plan = (x, y) with `y` mapped to
 * plan depth (the native model stores CGPoint x/y; SWIFT_RENAME below keeps the
 * mapping explicit for anyone reading both files side by side).
 */
const SWIFT_RENAME = { planX: 'x', planY: 'y', height: 'z' };

const finite = (v) => typeof v === 'number' && Number.isFinite(v);

/** Plan points accepted as {x,y} or [x,y]; anything else is null. */
function planPoint(p) {
  if (Array.isArray(p) && p.length >= 2 && finite(p[0]) && finite(p[1])) return { x: p[0], y: p[1] };
  if (p && finite(p.x) && finite(p.y)) return { x: p.x, y: p.y };
  return null;
}

function planRing(poly) {
  if (!Array.isArray(poly)) return null;
  const ring = poly.map(planPoint);
  if (ring.length < 3 || ring.some((p) => !p)) return null;
  // A repeated closing vertex is legal input, not a fourth corner.
  if (ring.length > 3 && Math.hypot(ring[0].x - ring[ring.length - 1].x, ring[0].y - ring[ring.length - 1].y) < 1e-9) ring.pop();
  return ring.length >= 3 ? ring : null;
}

/** Signed shoelace area in plan (m²); sign carries the winding. */
function signedPlanArea(ring) {
  let sum = 0;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i], b = ring[(i + 1) % ring.length];
    sum += a.x * b.y - b.x * a.y;
  }
  return sum / 2;
}

/** Plan area (m²) of a ring, always positive. */
function planArea(ring) {
  const r = planRing(ring);
  return r ? Math.abs(signedPlanArea(r)) : null;
}

/**
 * Newell vector of a 3D loop: N = sum(P_i x P_(i+1)). The loop does not have to
 * be closed explicitly. Returns {vector, magnitude, areaM2, planar, unit}.
 */
function newell(loop) {
  if (!Array.isArray(loop) || loop.length < 3) return { error: 'fewer than 3 vertices' };
  const p = loop.map((q) => {
    if (Array.isArray(q) && q.length >= 3) return finite(q[0]) && finite(q[1]) && finite(q[2]) ? [q[0], q[1], q[2]] : null;
    if (q && finite(q.x) && finite(q.y) && finite(q.z)) return [q.x, q.y, q.z];
    return null;
  });
  if (p.some((q) => !q)) return { error: 'non-finite vertex coordinate' };
  const n = p.length;
  let nx = 0, ny = 0, nz = 0;
  for (let i = 0; i < n; i++) {
    const a = p[i], b = p[(i + 1) % n];
    nx += a[1] * b[2] - a[2] * b[1];
    ny += a[2] * b[0] - a[0] * b[2];
    nz += a[0] * b[1] - a[1] * b[0];
  }
  const magnitude = Math.hypot(nx, ny, nz);
  if (!(magnitude > 1e-12)) return { error: 'degenerate loop (zero Newell magnitude)' };
  const unit = [nx / magnitude, ny / magnitude, nz / magnitude];
  // Planarity: every vertex must sit on the plane through the Newell normal
  // (distance measured from the loop centroid so the check is translation-free).
  const c = p.reduce((s, q) => [s[0] + q[0] / n, s[1] + q[1] / n, s[2] + q[2] / n], [0, 0, 0]);
  const deviationM = Math.max(...p.map((q) => Math.abs((q[0] - c[0]) * unit[0] + (q[1] - c[1]) * unit[1] + (q[2] - c[2]) * unit[2])));
  return { vector: [nx, ny, nz], magnitude, areaM2: magnitude / 2, unit, centroid: c, deviationM, planar: deviationM <= 1e-3 };
}

/** Newell area (m²) of a 3D loop, or null when the loop is invalid. */
function newellArea3D(loop) {
  const r = newell(loop);
  return r.error ? null : r.areaM2;
}

function unavailable(reason, extra) {
  return Object.assign({ status: 'unavailable', coverage: 'unavailable', method: 'authored', value: null, areaM2: null, netAreaM2: null, reason }, extra || {});
}

/**
 * Authored ceiling area, gross and net.
 *
 * @param {object} input
 *   polygon   plan ring [{x,y}] (m) — the room/ceiling outline
 *   elevations one finite height (m) per polygon vertex, same order
 *   holes     optional [{ polygon: [{x,y}], target?: 'ceiling'|'floor'|'both' }]
 *   floorAreaM2 optional plan floor area; defaults to |shoelace(polygon)|
 * @returns {object} on success:
 *   { status:'computed', coverage:'computed', method:'authored',
 *     value, areaM2, netAreaM2, floorAreaM2, holeAreaM2, slopeFactor,
 *     planar, deviationM, holes:[{areaM2}], reason:null }
 *   or `{ status:'unavailable', value:null, reason }` — never a guess.
 */
function authoredCeiling(input) {
  const opts = input || {};
  const ring = planRing(opts.polygon);
  if (!ring) return unavailable('no authored ceiling polygon with at least 3 finite plan vertices');
  const elevations = Array.isArray(opts.elevations) ? opts.elevations : null;
  if (!elevations) return unavailable('no authored ceiling profile: elevations missing (native: ceilingElevations empty)');
  if (elevations.length !== ring.length) {
    return unavailable(`authored ceiling elevation count ${elevations.length} does not match polygon vertex count ${ring.length}`);
  }
  if (!elevations.every(finite)) return unavailable('authored ceiling elevations contain a non-finite height');

  const loop = ring.map((p, i) => [p.x, p.y, elevations[i]]);
  const nw = newell(loop);
  if (nw.error) return unavailable(`authored ceiling loop rejected: ${nw.error}`);
  if (!nw.planar) return unavailable(`authored ceiling surface is not planar within 1 mm (deviation ${nw.deviationM.toFixed(4)} m)`, { deviationM: nw.deviationM });

  const floorArea = finite(opts.floorAreaM2) && opts.floorAreaM2 > 0 ? opts.floorAreaM2 : Math.abs(signedPlanArea(ring));
  if (!(floorArea > 0)) return unavailable('plan floor area is zero; hole scaling is undefined');

  const holes = [];
  for (const hole of Array.isArray(opts.holes) ? opts.holes : []) {
    if (!hole) continue;
    const target = hole.target || 'ceiling';
    if (target !== 'ceiling' && target !== 'both') continue;
    const holeRing = planRing(hole.polygon || hole.points || hole);
    if (!holeRing) return unavailable('ceiling hole without a valid plan polygon');
    const area = Math.abs(signedPlanArea(holeRing));
    if (!finite(area)) return unavailable('ceiling hole with a non-finite plan area');
    holes.push({ areaM2: area });
  }
  const holeArea = holes.reduce((s, h) => s + h.areaM2, 0);
  const slopeFactor = nw.areaM2 / floorArea;
  const netArea = Math.max(0, nw.areaM2 - holeArea * slopeFactor);
  return {
    status: 'computed',
    coverage: 'computed',
    method: 'authored',
    value: netArea,
    areaM2: nw.areaM2,
    netAreaM2: netArea,
    floorAreaM2: floorArea,
    holeAreaM2: holeArea,
    slopeFactor,
    planar: true,
    deviationM: nw.deviationM,
    holes,
    reason: null,
  };
}

module.exports = {
  authoredCeiling,
  newell,
  newellArea3D,
  planArea,
  signedPlanArea,
  planRing,
  SWIFT_RENAME,
};
