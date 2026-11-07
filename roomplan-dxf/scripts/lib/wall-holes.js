'use strict';
/**
 * wall-holes.js — cut REAL door/window holes into a wall box, with no CSG
 * library and no boolean solver.
 *
 * RoomPlan gives every wall a box (dimensions x = length, y = height,
 * z = thickness, placed by a 4x4 transform) and gives every door / window /
 * opening a box plus a `parentIdentifier` pointing at that wall. Until now the
 * export drew the opening as a second box sitting on top of an unbroken wall,
 * so AR Quick Look showed full walls with objects stuck on them.
 *
 * Approach — grid decomposition in the wall's own (u, v) plane:
 *
 *   1. every opening that names this wall is projected onto the wall axes:
 *      u = (openingCentre - wallCentre) . uAxis + L/2        (0 .. L)
 *      v = (openingCentre - wallCentre) . vAxis + H/2        (0 .. H)
 *      width = dimensions.x, height = dimensions.y,
 *      bottom = v - height/2.
 *   2. the set of u boundaries {0, L, opening u edges} and v boundaries
 *      {0, H, opening v edges} is sorted, giving a grid of cells.
 *   3. a cell whose centre lies inside any opening rectangle is VOID, every
 *      other cell is SOLID. Overlapping openings therefore merge into one hole
 *      with no special case: the union is cut once.
 *   4. for every solid cell: emit the front face (w = -T/2), the back face
 *      (w = +T/2), and a side face on each edge that borders a void cell or the
 *      wall boundary. Those side faces ARE the door reveal / window jamb and
 *      the sill, and the wall ends, top and bottom stay closed, so the result is
 *      a watertight solid with every normal pointing outward.
 *
 * An opening that cannot be placed sensibly (no 4x4 transform, no positive
 * width/height, or a rectangle that falls outside the wall by more than
 * BOUND_TOL) is NOT cut: the wall stays solid and a `usdz.opening-not-cut`
 * warning records why. A protruding edge within BOUND_TOL is clamped, so a scan
 * whose door sits 8 mm past the wall end still gets its hole.
 *
 * A wall carrying `polygonCorners` is not a box; it is left whole (and the
 * opening reports the same warning), because an arbitrary n-gon has no (u, v)
 * grid to cut.
 *
 * API:
 *   wallFrame(wall, dimensions, thickness)   -> frame | null
 *   placeOpening(frame, opening)             -> { ok, reason, u0, u1, v0, v1 }
 *   cutWall(frame, rects)                    -> { points, faces, cutArea, frontArea, solidCells }
 *   buildWallWithHoles({ wall, dimensions, thickness, openings })
 *        -> { cut, geometry, frame, openings, cutArea, frontArea, warnings }
 */

const EPS = 1e-9;
/** How far an opening may overshoot the wall end before it is refused (m). */
const BOUND_TOL = 0.02;
const OPENING_KINDS = new Set(['door', 'window', 'opening']);

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
function unit(a) {
  const l = Math.hypot(a[0], a[1], a[2]);
  if (!(l > EPS)) return null;
  return [a[0] / l, a[1] / l, a[2] / l];
}

/** Is this surface an opening we may cut with? */
function isOpening(surface) {
  return Boolean(surface) && OPENING_KINDS.has(surface.kind);
}

/**
 * Local frame of a wall box. u runs 0..L along the wall, v runs 0..H up it,
 * w runs -T/2..+T/2 through the thickness; `at(u, v, w)` maps a local triple
 * back to world space using the wall's own transform, so the exported mesh and
 * its transform cannot drift apart.
 */
function wallFrame(wall, dimensions, thickness) {
  const m = wall && wall.transform;
  if (!Array.isArray(m) || m.length !== 16 || !m.every(Number.isFinite)) return null;
  const dims = dimensions || {};
  const L = dims.x;
  const H = dims.y;
  const T = thickness;
  if (!(L > EPS) || !(H > EPS) || !(T > EPS)) return null;
  const u = unit([m[0], m[1], m[2]]);
  const v = unit([m[4], m[5], m[6]]);
  const w = unit([m[8], m[9], m[10]]);
  if (!u || !v || !w) return null;
  const c = [m[12], m[13], m[14]];
  const origin = [
    c[0] - (u[0] * L) / 2 - (v[0] * H) / 2,
    c[1] - (u[1] * L) / 2 - (v[1] * H) / 2,
    c[2] - (u[2] * L) / 2 - (v[2] * H) / 2,
  ];
  const at = (uu, vv, ww) => [
    origin[0] + uu * u[0] + vv * v[0] + ww * w[0],
    origin[1] + uu * u[1] + vv * v[1] + ww * w[1],
    origin[2] + uu * u[2] + vv * v[2] + ww * w[2],
  ];
  return { L, H, T, u, v, w, centre: c, origin, at };
}

/**
 * Project one opening onto the wall plane. Pure geometry, no side effects:
 * the caller decides what to do with `ok:false`.
 */
function placeOpening(frame, opening) {
  const id = opening && opening.identifier != null ? String(opening.identifier) : 'anonymous';
  const m = opening && opening.transform;
  if (!Array.isArray(m) || m.length !== 16 || !m.every(Number.isFinite)) {
    return { ok: false, reason: 'missing or non-finite 4x4 transform', identifier: id };
  }
  const dims = (opening && opening.dimensions) || {};
  const ow = dims.x;
  const oh = dims.y;
  if (!(ow > EPS) || !(oh > EPS)) {
    return { ok: false, reason: 'no positive width/height dimensions', identifier: id };
  }
  const d = sub([m[12], m[13], m[14]], frame.centre);
  const uc = dot(d, frame.u) + frame.L / 2;
  const vc = dot(d, frame.v) + frame.H / 2;
  let u0 = uc - ow / 2;
  let u1 = uc + ow / 2;
  let v0 = vc - oh / 2;
  let v1 = vc + oh / 2;

  // Refuse an opening that is not meaningfully on this wall.
  if (u1 <= -BOUND_TOL || u0 >= frame.L + BOUND_TOL) {
    return { ok: false, reason: 'lies outside the wall length', identifier: id, u0, u1, v0, v1 };
  }
  if (v1 <= -BOUND_TOL || v0 >= frame.H + BOUND_TOL) {
    return { ok: false, reason: 'lies outside the wall height', identifier: id, u0, u1, v0, v1 };
  }
  const clamped = u0 < 0 || v0 < 0 || u1 > frame.L || v1 > frame.H;
  u0 = Math.min(Math.max(u0, 0), frame.L);
  u1 = Math.min(Math.max(u1, 0), frame.L);
  v0 = Math.min(Math.max(v0, 0), frame.H);
  v1 = Math.min(Math.max(v1, 0), frame.H);
  if (!(u1 - u0 > EPS) || !(v1 - v0 > EPS)) {
    return { ok: false, reason: 'rectangle collapses when clamped to the wall', identifier: id };
  }
  return {
    ok: true,
    identifier: id,
    kind: opening.kind,
    u0,
    u1,
    v0,
    v1,
    clamped,
    // what the capture asked for, before clamping to the wall bounds
    requested: { u0: uc - ow / 2, u1: uc + ow / 2, v0: vc - oh / 2, v1: vc + oh / 2 },
  };
}

function sortedUnique(values, lo, hi) {
  // Boundaries closer than 1 um are the same boundary: a scan routinely puts a
  // door sill 2e-8 m above the floor, and a sliver cell that thin would survive
  // rounding in the file as a degenerate face. Snap, then dedupe.
  const tol = 1e-6;
  const snapped = values.map((v) => (Math.abs(v - lo) <= tol ? lo : Math.abs(v - hi) <= tol ? hi : v));
  const sorted = snapped.sort((a, b) => a - b);
  const out = [];
  for (const v of sorted) {
    if (!out.length || Math.abs(v - out[out.length - 1]) > tol) out.push(v);
  }
  // the wall bounds are always grid lines and always the extremes
  out[0] = lo;
  out[out.length - 1] = hi;
  return out;
}

/**
 * Grid decomposition + surface extraction. Every face is emitted with the
 * winding that makes its Newell normal point OUT of the solid, so the mesh
 * writer needs no normal fix-up pass.
 */
function cutWall(frame, rects) {
  const us = [0, frame.L];
  const vs = [0, frame.H];
  for (const r of rects) {
    us.push(r.u0, r.u1);
    vs.push(r.v0, r.v1);
  }
  const U = sortedUnique(us, 0, frame.L);
  const V = sortedUnique(vs, 0, frame.H);
  const h = frame.T / 2;
  const at = frame.at;

  const points = [];
  const faces = [];
  const quad = (p0, p1, p2, p3) => {
    const base = points.length;
    points.push(p0, p1, p2, p3);
    faces.push([base, base + 1, base + 2, base + 3]);
  };

  const nu = U.length - 1;
  const nv = V.length - 1;
  const solid = [];
  const area = [];
  for (let i = 0; i < nu; i += 1) {
    solid.push([]);
    area.push([]);
    for (let j = 0; j < nv; j += 1) {
      const mu = (U[i] + U[i + 1]) / 2;
      const mv = (V[j] + V[j + 1]) / 2;
      const inside = rects.some((r) => mu > r.u0 && mu < r.u1 && mv > r.v0 && mv < r.v1);
      solid[i].push(!inside);
      area[i].push((U[i + 1] - U[i]) * (V[j + 1] - V[j]));
    }
  }
  const isSolid = (i, j) => i >= 0 && j >= 0 && i < nu && j < nv && solid[i][j];

  let cutArea = 0;
  let frontArea = 0;
  let solidCells = 0;
  for (let i = 0; i < nu; i += 1) {
    for (let j = 0; j < nv; j += 1) {
      if (!solid[i][j]) { cutArea += area[i][j]; continue; }
      solidCells += 1;
      frontArea += area[i][j];
      const u0 = U[i];
      const u1 = U[i + 1];
      const v0 = V[j];
      const v1 = V[j + 1];

      // front plane, w = -T/2, normal -w  (order: +v then +u)
      quad(at(u0, v0, -h), at(u0, v1, -h), at(u1, v1, -h), at(u1, v0, -h));
      // back plane, w = +T/2, normal +w
      quad(at(u0, v0, h), at(u1, v0, h), at(u1, v1, h), at(u0, v1, h));
      // left side, u = u0, normal -u
      if (!isSolid(i - 1, j)) quad(at(u0, v0, -h), at(u0, v0, h), at(u0, v1, h), at(u0, v1, -h));
      // right side, u = u1, normal +u
      if (!isSolid(i + 1, j)) quad(at(u1, v0, -h), at(u1, v1, -h), at(u1, v1, h), at(u1, v0, h));
      // bottom, v = v0, normal -v
      if (!isSolid(i, j - 1)) quad(at(u0, v0, -h), at(u1, v0, -h), at(u1, v0, h), at(u0, v0, h));
      // top, v = v1, normal +v
      if (!isSolid(i, j + 1)) quad(at(u0, v1, -h), at(u0, v1, h), at(u1, v1, h), at(u1, v1, -h));
    }
  }

  return { points, faces, cutArea, frontArea, solidCells, grid: { U, V } };
}

/**
 * Full wall decision: which openings cut, which do not, and what geometry to
 * export. A wall with no cuttable opening returns `cut:false` and no geometry,
 * so the caller keeps its plain box exactly as before.
 */
function buildWallWithHoles(options) {
  const opts = options || {};
  const wall = opts.wall;
  const dims = opts.dimensions || {};
  const thickness = opts.thickness;
  const openings = (Array.isArray(opts.openings) ? opts.openings : []).filter(isOpening);
  const warnings = [];
  const result = { cut: false, geometry: null, frame: null, openings: [], cutArea: 0, frontArea: 0, warnings };
  if (!openings.length) return result;

  const wallId = wall && wall.identifier != null ? String(wall.identifier) : null;
  const frame = wallFrame(wall, dims, thickness);
  if (!frame) {
    warnings.push({
      code: 'usdz.opening-not-cut',
      message: `Wall "${wallId || 'anonymous'}" keeps its openings uncut (USDZ): the wall has no usable 4x4 transform or no positive length/height/thickness.`,
    });
    return result;
  }
  result.frame = frame;
  if (Array.isArray(wall.polygonCorners) && wall.polygonCorners.length >= 3) {
    warnings.push({
      code: 'usdz.opening-not-cut',
      message: `Wall "${wallId || 'anonymous'}" keeps its openings uncut (USDZ): a wall exported from polygonCorners is an n-gon, not a box, so there is no (u, v) grid to cut.`,
    });
    return result;
  }

  const rects = [];
  for (const opening of openings) {
    const placed = placeOpening(frame, opening);
    if (!placed.ok) {
      warnings.push({
        code: 'usdz.opening-not-cut',
        message: `Opening "${placed.identifier}" not cut from wall "${wallId || 'anonymous'}" (USDZ): ${placed.reason}. The wall stays solid.`,
      });
      continue;
    }
    if (placed.clamped) {
      warnings.push({
        code: 'usdz.opening-clamped',
        message: `Opening "${placed.identifier}" on wall "${wallId || 'anonymous'}" (USDZ): exceeded the wall by less than ${BOUND_TOL} m and was clamped to the wall bounds.`,
      });
    }
    rects.push(placed);
  }
  result.openings = rects;
  if (!rects.length) return result;

  const cut = cutWall(frame, rects);
  if (!(cut.points.length > 0)) return result;
  result.cut = true;
  result.geometry = { points: cut.points, faces: cut.faces, kind: 'box-with-holes' };
  result.cutArea = cut.cutArea;
  result.frontArea = cut.frontArea;
  result.solidCells = cut.solidCells;
  result.grid = cut.grid;
  return result;
}

/** Group openings by the wall identifier they name. */
function indexOpeningsByParent(surfaces) {
  const map = new Map();
  for (const s of Array.isArray(surfaces) ? surfaces : []) {
    if (!isOpening(s)) continue;
    const parent = s.parentIdentifier;
    if (parent == null || parent === '') continue;
    const key = String(parent);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(s);
  }
  return map;
}

module.exports = {
  BOUND_TOL,
  OPENING_KINDS,
  isOpening,
  wallFrame,
  placeOpening,
  cutWall,
  buildWallWithHoles,
  indexOpeningsByParent,
};
