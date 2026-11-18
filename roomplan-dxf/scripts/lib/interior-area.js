'use strict';
/**
 * interior-area.js — clear (interior) room area with the union of wall
 * footprints removed (SPEC §5, G-6 / G-7).
 *
 * Ported from ArchiPlan `editor/src/lib/utils/interiorArea.ts`
 * (`interiorRoomArea`, scanline integration) plus its `wallPathSpans`
 * dependency, stripped of TypeScript types and of the `$lib` alias so it is the
 * same pure-JS module in Node and in a browser. No dependencies.
 *
 * How it works: every coordinate is a plan (x, y) point. All polygons (room
 * ring, its holes, every wall footprint) are cut into horizontal bands at every
 * vertex height AND at every edge-crossing height. Inside one band the edge
 * order is fixed, so the band's midpoint gives the exact integral of a faceted
 * polygon. Per band: room/hole even-odd interval lengths, minus the length of
 * the union of wall-footprint intervals. The union is why two overlapping walls
 * are counted once and why a T-junction cannot punch the area twice.
 *
 * Conventions (`options.wallConvention`):
 *   'centerline' (default) — the wall path runs through the middle of the wall
 *     body, so each footprint is the path offset by ±thickness/2. This is what
 *     interiorArea.ts does and what a scan-derived plan carries.
 *   'reference-edges'      — the wall path IS the room's inner face, so the wall
 *     body lies entirely outside the room: the path is moved outward by
 *     thickness/2 before footprinting. Outward is decided per span from the
 *     room centroid, which is exact for star-shaped rings (all rooms that are a
 *     single ring with no self-intersection); when the normal is ambiguous the
 *     result is `null`, never a guess.
 *
 * Units: metres by default; `options.units === 'cm'` accepts centimetre input
 * (the TS original) and returns m² either way.
 *
 * Every refusal returns `null` — invalid ring, non-positive thickness, budget
 * exceeded, ambiguous outward normal. A partial area is never returned.
 */
const finite = (v) => typeof v === 'number' && Number.isFinite(v);

/** Point accepted as {x,y} or [x,y]; else null. */
function point(p) {
  if (Array.isArray(p) && p.length >= 2 && finite(p[0]) && finite(p[1])) return { x: p[0], y: p[1] };
  if (p && finite(p.x) && finite(p.y)) return { x: p.x, y: p.y };
  return null;
}

function ring(arr) {
  if (!Array.isArray(arr)) return null;
  const r = arr.map(point);
  if (r.length < 3 || r.some((p) => !p)) return null;
  if (r.length > 3 && Math.hypot(r[0].x - r[r.length - 1].x, r[0].y - r[r.length - 1].y) < 1e-12) r.pop();
  return r.length >= 3 ? r : null;
}

function shoelace(r) {
  let s = 0;
  for (let i = 0; i < r.length; i++) {
    const a = r[i], b = r[(i + 1) % r.length];
    s += a.x * b.y - b.x * a.y;
  }
  return s / 2;
}

/**
 * Centreline (reference-line) area of a room polygon in m²: the plain shoelace
 * area of the ring minus the plain area of every hole. This is the number a plan
 * gives before wall thickness is considered — G-7's "no reference edges" case.
 * Returns null on invalid input.
 */
function centerlineArea(r, holes, options) {
  const opts = options || {};
  const scale = opts.units === 'cm' ? 1e-4 : 1;
  const main = ring(r);
  if (!main) return null;
  const holesList = Array.isArray(holes) ? holes : [];
  let area = Math.abs(shoelace(main));
  for (const h of holesList) {
    const hr = ring(h);
    if (!hr) return null;
    area -= Math.abs(shoelace(hr));
  }
  const out = Math.max(0, area) * scale;
  return finite(out) ? out : null;
}

/**
 * Facets of a wall path: one span for a straight wall, `count` (=16) quadratic
 * Bezier facets when `curvePoint` is present — the same faceting the viewer and
 * the TS original use, so a curved wall is measured, never bounding-boxed.
 */
function wallPathSpans(wall) {
  if (!wall) return null;
  const start = point(wall.start), end = point(wall.end);
  if (!start || !end) return null;
  const control = wall.curvePoint ? point(wall.curvePoint) : null;
  if (wall.curvePoint && !control) return null;
  const count = control ? 16 : 1;
  const at = (t) => (control
    ? { x: (1 - t) * (1 - t) * start.x + 2 * (1 - t) * t * control.x + t * t * end.x,
        y: (1 - t) * (1 - t) * start.y + 2 * (1 - t) * t * control.y + t * t * end.y }
    : { x: start.x + (end.x - start.x) * t, y: start.y + (end.y - start.y) * t });
  const spans = [];
  for (let i = 0; i < count; i++) spans.push([at(i / count), at((i + 1) / count)]);
  return spans;
}

/** Even-odd x-intervals of a set of rings at height y. */
function intervals(rings, y) {
  const xs = [];
  for (const r of rings) {
    for (let i = 0; i < r.length; i++) {
      const a = r[i], b = r[(i + 1) % r.length];
      if ((a.y > y) !== (b.y > y)) xs.push(a.x + ((y - a.y) * (b.x - a.x)) / (b.y - a.y));
    }
  }
  xs.sort((a, b) => a - b);
  const result = [];
  for (let i = 0; i + 1 < xs.length; i += 2) result.push([xs[i], xs[i + 1]]);
  return result;
}

/**
 * Interior area of a room in m², excluding the union of the wall footprints.
 *
 * @param {Array}   r         room ring, plan metres
 * @param {Array}   holes     array of hole rings (plan metres)
 * @param {Array}   walls     [{ start, end, thickness, curvePoint? }]
 * @param {object}  [options] { units:'m'|'cm', wallConvention:'centerline'|'reference-edges',
 *                             maxEdges:600, maxLevelsTimesEdges:2e6 }
 * @returns {number|null} m², or null when the input is invalid / over budget /
 *          the outward normal cannot be decided. Never a partial area.
 */
function interiorRoomArea(r, holes, walls, options) {
  const opts = options || {};
  const scale = opts.units === 'cm' ? 1e-4 : 1;
  const maxEdges = finite(opts.maxEdges) ? opts.maxEdges : 600;
  const budget = finite(opts.maxLevelsTimesEdges) ? opts.maxLevelsTimesEdges : 2e6;
  const main = ring(r);
  if (!main) return null;
  const holeRings = [];
  for (const h of Array.isArray(holes) ? holes : []) {
    const hr = ring(h);
    if (!hr) return null;
    holeRings.push(hr);
  }
  const room = [main, ...holeRings];

  // Outward direction reference for `reference-edges`: the ring centroid. Exact
  // for a star-shaped (every normal room) ring; ambiguous normals are refused.
  const centroid = main.reduce((s, p) => ({ x: s.x + p.x / main.length, y: s.y + p.y / main.length }), { x: 0, y: 0 });
  const referenceEdges = opts.wallConvention === 'reference-edges';

  const footprints = [];
  for (const wall of Array.isArray(walls) ? walls : []) {
    const thickness = wall ? wall.thickness : undefined;
    if (!finite(thickness) || thickness <= 0) return null;
    const spans = wallPathSpans(wall);
    if (!spans) return null;
    const half = thickness / 2;
    for (const [s, e] of spans) {
      const dx = e.x - s.x, dy = e.y - s.y;
      const length = Math.hypot(dx, dy);
      if (!finite(length)) return null;
      if (length === 0) continue;
      const ux = dx / length, uy = dy / length; // along
      let nx = -uy, ny = ux; // across
      if (referenceEdges) {
        // The wall body must sit outside the room: point the offset away from
        // the room centroid. A wall whose midpoint is at the centroid has no
        // defined outside, so the area is refused rather than guessed.
        const mx = (s.x + e.x) / 2 - centroid.x, my = (s.y + e.y) / 2 - centroid.y;
        const d = mx * nx + my * ny;
        if (Math.abs(d) < 1e-9) return null;
        if (d < 0) { nx = -nx; ny = -ny; }
      }
      const ox = referenceEdges ? nx * half : 0, oy = referenceEdges ? ny * half : 0;
      // Square end caps close corners and T junctions; overlapping walls count once.
      footprints.push([[-half, -half], [length + half, -half], [length + half, half], [-half, half]]
        .map(([along, across]) => ({
          x: s.x + ox + along * ux - across * uy,
          y: s.y + oy + along * uy + across * ux,
        })));
    }
  }

  const polygons = [...room, ...footprints];
  const edges = [];
  for (const p of polygons) for (let i = 0; i < p.length; i++) edges.push([p[i], p[(i + 1) % p.length]]);
  if (edges.length > maxEdges) return null;

  // Band boundaries: every vertex height plus every proper crossing height.
  const levels = polygons.reduce((acc, p) => acc.concat(p.map((q) => q.y)), []);
  for (let i = 0; i < edges.length; i++) {
    const [a, b] = edges[i], dx = b.x - a.x, dy = b.y - a.y;
    for (let j = i + 1; j < edges.length; j++) {
      const [c, d] = edges[j], ex = d.x - c.x, ey = d.y - c.y;
      const cross = dx * ey - dy * ex;
      if (cross === 0) continue;
      const t = ((c.x - a.x) * ey - (c.y - a.y) * ex) / cross;
      const u = ((c.x - a.x) * dy - (c.y - a.y) * dx) / cross;
      if (t > 0 && t < 1 && u > 0 && u < 1) levels.push(a.y + t * dy);
    }
  }
  const ys = [...new Set(levels)].sort((a, b) => a - b);
  if (ys.length * edges.length > budget) return null;

  let area = 0;
  for (let i = 1; i < ys.length; i++) {
    const y = (ys[i - 1] + ys[i]) / 2;
    const blocked = footprints.map((r2) => intervals([r2], y)).flat().sort((a, b) => a[0] - b[0]);
    const union = [];
    for (const item of blocked) {
      const last = union[union.length - 1];
      if (last && item[0] <= last[1]) last[1] = Math.max(last[1], item[1]);
      else union.push([...item]);
    }
    let width = 0;
    for (const [left, right] of intervals(room, y)) {
      width += right - left;
      for (const [a, b] of union) width -= Math.max(0, Math.min(right, b) - Math.max(left, a));
    }
    area += Math.max(0, width) * (ys[i] - ys[i - 1]);
  }
  const out = area * scale;
  return finite(out) ? out : null;
}

module.exports = {
  interiorRoomArea,
  centerlineArea,
  wallPathSpans,
  shoelace,
};
