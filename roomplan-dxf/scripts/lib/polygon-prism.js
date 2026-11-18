'use strict';
/**
 * polygon-prism.js — turn a wall's planar `polygonCorners` into a SOLID prism.
 *
 * RoomPlan/Polycam hand a wall its plan outline as a closed 2D polygon in the
 * surface's local XZ.. no: in its local X/Y plane at z = 0 (the conventions
 * block in capture-v1 says "polygonCorners are surface-local; element.transform
 * maps local to source space"). Emitting that polygon as one flat sheet makes
 * the wall look like paper in AR Quick Look: it has no thickness, so once you
 * stand on the other side, backface culling makes it disappear.
 *
 * So a polygon wall is extruded along the surface's local +Z (its thickness
 * axis) from -T/2 to +T/2:
 *
 *   - two cap faces (front at -T/2 with normal -Z, back at +T/2 with normal +Z),
 *     ear-clipped because plan polygons are routinely CONCAVE (an L-shaped wall
 *     of 7 points would give overlapping, self-intersecting fans);
 *   - one quad per polygon edge, wound so its normal points away from the solid.
 *
 * Surface area of the result is 2*area(polygon) + perimeter*T, and the signed
 * volume from the winding is area(polygon)*T — both are asserted in
 * tests/test_wall_holes.js, so a flipped face or a forgotten cap cannot pass.
 *
 * Winding: the polygon is normalised to counter-clockwise seen from local +Z
 * first (Newell normal's z sign), which makes every outward direction a fixed
 * formula. A polygon that is not roughly perpendicular to the thickness axis
 * (|nz| < 0.5) is refused and the caller keeps the flat sheet.
 *
 * API: prismGeometry(cornersLocal, transform, thickness) -> geometry | null
 *      polygonArea2D(points) -> number
 *      earClip(points2D) -> [[i, j, k], ...]
 */

const EPS = 1e-9;

function cross2(a, b, c) {
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

/** Shoelace area (absolute) of a 2D polygon. */
function polygonArea2D(points) {
  let s = 0;
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    s += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(s) / 2;
}

/** True when p is inside triangle (a,b,c) or on its edge (used by ear clipping). */
function pointInTriangle(p, a, b, c) {
  const d1 = cross2(a, b, p);
  const d2 = cross2(b, c, p);
  const d3 = cross2(c, a, p);
  const hasNeg = d1 < -EPS || d2 < -EPS || d3 < -EPS;
  const hasPos = d1 > EPS || d2 > EPS || d3 > EPS;
  return !(hasNeg && hasPos);
}

/**
 * Ear-clipping triangulation of a simple (possibly concave) CCW polygon.
 * Returns triangles as index triples. Falls back to a fan if the polygon is
 * degenerate (duplicate or collinear vertices left a polygon no ear can be
 * clipped from), because a slightly wrong fan beats dropping the wall.
 */
function earClip(points) {
  const n = points.length;
  if (n < 3) return [];
  if (n === 3) return [[0, 1, 2]];
  const idx = [];
  for (let i = 0; i < n; i += 1) idx.push(i);
  const triangles = [];
  let guard = 0;
  while (idx.length > 3 && guard < 4 * n * n) {
    guard += 1;
    let clipped = false;
    for (let i = 0; i < idx.length; i += 1) {
      const i0 = idx[(i + idx.length - 1) % idx.length];
      const i1 = idx[i];
      const i2 = idx[(i + 1) % idx.length];
      const a = points[i0];
      const b = points[i1];
      const c = points[i2];
      const turn = cross2(a, b, c);
      if (turn <= EPS) continue; // reflex or collinear vertex: not an ear
      let contains = false;
      for (const j of idx) {
        if (j === i0 || j === i1 || j === i2) continue;
        if (pointInTriangle(points[j], a, b, c)) { contains = true; break; }
      }
      if (contains) continue;
      triangles.push([i0, i1, i2]);
      idx.splice(i, 1);
      clipped = true;
      break;
    }
    if (!clipped) break;
  }
  if (idx.length === 3) {
    triangles.push([idx[0], idx[1], idx[2]]);
  } else {
    // degenerate input: fan the remainder so the caps stay closed
    for (let i = 1; i < idx.length - 1; i += 1) triangles.push([idx[0], idx[i], idx[i + 1]]);
  }
  return triangles;
}

function unit(v) {
  const l = Math.hypot(v[0], v[1], v[2]);
  if (!(l > EPS)) return null;
  return [v[0] / l, v[1] / l, v[2] / l];
}

/** Newell normal of a 3D polygon. */
function newell(points) {
  const n = [0, 0, 0];
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    n[0] += (a[1] - b[1]) * (a[2] + b[2]);
    n[1] += (a[2] - b[2]) * (a[0] + b[0]);
    n[2] += (a[0] - b[0]) * (a[1] + b[1]);
  }
  return unit(n);
}

function world(p, m) {
  return [
    m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
    m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
    m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14],
  ];
}

/**
 * @param {number[][]} cornersLocal polygonCorners in surface-local space (n >= 3)
 * @param {number[]} transform column-major 4x4 mapping local -> source space
 * @param {number} thickness total thickness, metres (> 0)
 * @returns {null|{points:number[][], faces:number[][], area:object}}
 */
function prismGeometry(cornersLocal, transform, thickness) {
  if (!Array.isArray(cornersLocal) || cornersLocal.length < 3) return null;
  if (!(thickness > EPS)) return null;
  if (!Array.isArray(transform) || transform.length !== 16 || !transform.every(Number.isFinite)) return null;

  let poly = cornersLocal.map((p) => [Number(p[0]), Number(p[1]), Number(p[2])]);
  if (!poly.every((p) => p.every(Number.isFinite))) return null;
  // drop a repeated closing vertex
  const first = poly[0];
  const last = poly[poly.length - 1];
  if (poly.length > 3 && Math.hypot(first[0] - last[0], first[1] - last[1], first[2] - last[2]) < 1e-7) poly.pop();
  if (poly.length < 3) return null;

  const nLocal = newell(poly);
  if (!nLocal || Math.abs(nLocal[2]) < 0.5) return null; // not a plan polygon
  // normalise to CCW seen from local +Z, so every outward normal has one formula
  if (nLocal[2] < 0) poly.reverse();

  const flat = poly.map((p) => [p[0], p[1]]);
  const area2d = polygonArea2D(flat);
  if (!(area2d > EPS)) return null;
  const tris = earClip(flat);
  if (!tris.length) return null;

  const h = thickness / 2;
  const points = [];
  const faces = [];
  const add = (p) => {
    points.push(world(p, transform));
    return points.length - 1;
  };
  const lo = poly.map((p) => add([p[0], p[1], -h]));
  const hi = poly.map((p) => add([p[0], p[1], h]));

  // front cap (z = -h): normals -Z, so the CCW triangles are reversed
  for (const [a, b, c] of tris) faces.push([lo[c], lo[b], lo[a]]);
  // back cap (z = +h): normals +Z, original CCW order
  for (const [a, b, c] of tris) faces.push([hi[a], hi[b], hi[c]]);
  // one quad per edge: [a(-h), b(-h), b(+h), a(+h)] points away from the solid
  let perimeter = 0;
  for (let i = 0; i < poly.length; i += 1) {
    const j = (i + 1) % poly.length;
    perimeter += Math.hypot(poly[j][0] - poly[i][0], poly[j][1] - poly[i][1]);
    faces.push([lo[i], lo[j], hi[j], hi[i]]);
  }

  return {
    points,
    faces,
    kind: 'prism',
    area: {
      ends: 2 * area2d,
      sides: perimeter * thickness,
      total: 2 * area2d + perimeter * thickness,
      polygon: area2d,
      perimeter,
      volume: area2d * thickness,
    },
  };
}

module.exports = { prismGeometry, polygonArea2D, earClip };
