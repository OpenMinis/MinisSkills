'use strict';
/**
 * polygon-union.js — exact plan area of the UNION of simple rings.
 *
 * Why this exists: a producer can emit several supplied ceiling surfaces that
 * describe the SAME plan footprint at different heights ("stacked"
 * alternatives), or overlapping pieces of one roof. Summing their areas
 * inflates the ceiling quantity (an anonymized regression example: one room carried three co-located
 * surfaces, 3x the footprint). The accounting convention uses the plan union
 * of source surfaces, not their arithmetic sum. This does not identify or
 * verify the physical ceiling; largest-surface-first allocation is not survey
 * evidence, and zero-plan-extent surfaces require a diagnosed sum fallback.
 *
 * Method: x-sweep over the split edges.
 *   1. split every edge at every intersection with every other edge, so no two
 *      edges cross inside an open slab;
 *   2. take the sorted distinct slab boundaries x_i;
 *   3. in each slab, evaluate every edge that spans the slab midpoint at that
 *      single x — for a simple ring the spanning edges pair up in y order, so
 *      each ring yields disjoint interior intervals;
 *   4. merge the intervals of ALL rings (set union, not XOR) and integrate.
 * The result is exact for straight-edged rings up to floating-point rounding;
 * no rasterisation, no bounding box, no approximation is involved.
 *
 * Constraints (deliberate, documented): simple rings only (no self
 * intersections, no holes). A hole must be decomposed into faces by the caller,
 * exactly as `explicitCeilingGeometry` already refuses ceiling hole rings.
 * Nothing here fabricates geometry or reinterprets a surface.
 */

const EPS = 1e-9;
const TOL = 1e-9;

const finite = (v) => typeof v === 'number' && Number.isFinite(v);

/** Signed ring area (shoelace, plan x/y). */
function ringArea(ring) {
  let a = 0;
  for (let i = 0; i < ring.length; i += 1) {
    const p = ring[i];
    const q = ring[(i + 1) % ring.length];
    a += p[0] * q[1] - q[0] * p[1];
  }
  return a / 2;
}

function validRing(ring) {
  return Array.isArray(ring) && ring.length >= 3
    && ring.every((p) => Array.isArray(p) && p.length >= 2 && finite(p[0]) && finite(p[1]));
}

/** Pairwise edge intersections (proper crossings only; touching/collinear is
 *  left to the sweep, which is still exact at a shared x). */
function splitPoints(a, b, c, d) {
  const r = [b[0] - a[0], b[1] - a[1]];
  const s = [d[0] - c[0], d[1] - c[1]];
  const den = r[0] * s[1] - r[1] * s[0];
  if (Math.abs(den) < 1e-14) return [];
  const qp = [c[0] - a[0], c[1] - a[1]];
  const t = (qp[0] * s[1] - qp[1] * s[0]) / den;
  const u = (qp[0] * r[1] - qp[1] * r[0]) / den;
  if (t < -TOL || t > 1 + TOL || u < -TOL || u > 1 + TOL) return [];
  const x = a[0] + t * r[0];
  const y = a[1] + t * r[1];
  if (t < TOL || t > 1 - TOL) return []; // endpoint: already a vertex
  return [[x, y]];
}

/** All edges of all rings, split at mutual crossings. */
function splitEdges(rings) {
  const edges = [];
  for (const ring of rings) {
    for (let i = 0; i < ring.length; i += 1) {
      const a = ring[i];
      const b = ring[(i + 1) % ring.length];
      if (a[0] === b[0] && a[1] === b[1]) continue;
      edges.push({ ring, a: [a[0], a[1]], b: [b[0], b[1]], cuts: [] });
    }
  }
  for (let i = 0; i < edges.length; i += 1) {
    for (let j = i + 1; j < edges.length; j += 1) {
      const p = splitPoints(edges[i].a, edges[i].b, edges[j].a, edges[j].b);
      if (!p.length) continue;
      const [x, y] = p[0];
      const t = (Math.hypot(x - edges[i].a[0], y - edges[i].a[1]))
        / (Math.hypot(edges[i].b[0] - edges[i].a[0], edges[i].b[1] - edges[i].a[1]));
      edges[i].cuts.push({ t, p: [x, y] });
      edges[j].cuts.push({
        t: (Math.hypot(x - edges[j].a[0], y - edges[j].a[1]))
          / (Math.hypot(edges[j].b[0] - edges[j].a[0], edges[j].b[1] - edges[j].a[1])),
        p: [x, y],
      });
    }
  }
  const pieces = [];
  for (const e of edges) {
    const cuts = e.cuts.slice().sort((u, v) => u.t - v.t);
    let prev = e.a;
    for (const c of cuts) {
      if (Math.hypot(c.p[0] - prev[0], c.p[1] - prev[1]) > EPS) pieces.push({ ring: e.ring, a: prev, b: c.p });
      prev = c.p;
    }
    if (Math.hypot(e.b[0] - prev[0], e.b[1] - prev[1]) > EPS) pieces.push({ ring: e.ring, a: prev, b: e.b });
  }
  return pieces;
}

function mergeIntervals(intervals) {
  if (!intervals.length) return [];
  const sorted = intervals.slice().sort((a, b) => a[0] - b[0]);
  const out = [sorted[0].slice()];
  for (let i = 1; i < sorted.length; i += 1) {
    const last = out[out.length - 1];
    const cur = sorted[i];
    if (cur[0] <= last[1] + 1e-12) last[1] = Math.max(last[1], cur[1]);
    else out.push(cur.slice());
  }
  return out;
}

/** Interior y-intervals of ONE ring at the vertical line x = X (even-odd pairing). */
function ringIntervalsAt(pieces, ring, X) {
  const ys = [];
  for (const p of pieces) {
    if (p.ring !== ring) continue;
    const xmin = Math.min(p.a[0], p.b[0]);
    const xmax = Math.max(p.a[0], p.b[0]);
    if (!(xmin < X - 1e-12 && xmax > X + 1e-12)) continue; // vertical/no span
    const t = (X - p.a[0]) / (p.b[0] - p.a[0]);
    ys.push(p.a[1] + t * (p.b[1] - p.a[1]));
  }
  ys.sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i + 1 < ys.length; i += 2) out.push([ys[i], ys[i + 1]]);
  return out;
}

/**
 * Plan area of the union of `rings`.
 * @returns {{area:number, status:'computed'|'unavailable', reason:string|null}}
 */
function unionArea(rings) {
  const raw = (rings || []).filter(validRing);
  // Identical rings (or the same array passed twice) must count once, not
  // collapse to a zero-height pairing inside the sweep.
  const seen = new Set();
  const list = [];
  for (const r of raw) {
    const key = r.map((p) => `${Math.round(p[0] * 1e9)},${Math.round(p[1] * 1e9)}`).join(';');
    if (seen.has(key)) continue;
    seen.add(key);
    list.push(r);
  }
  if (!list.length) return { area: 0, status: 'unavailable', reason: 'no valid ring to union' };
  const pieces = splitEdges(list);
  const xsSet = new Set();
  for (const p of pieces) { xsSet.add(p.a[0]); xsSet.add(p.b[0]); }
  const xs = Array.from(xsSet).sort((a, b) => a - b);
  let total = 0;
  for (let i = 0; i + 1 < xs.length; i += 1) {
    const x0 = xs[i];
    const x1 = xs[i + 1];
    const width = x1 - x0;
    if (width <= EPS) continue;
    const X = (x0 + x1) / 2;
    const intervals = [];
    for (const ring of list) for (const iv of ringIntervalsAt(pieces, ring, X)) intervals.push(iv);
    for (const iv of mergeIntervals(intervals)) total += (iv[1] - iv[0]) * width;
  }
  return { area: total, status: 'computed', reason: null };
}

/**
 * Envelope of a set of supplied surfaces.
 *
 * Each surface contributes `surfaceAreaM2` (developed area, from the source
 * plane) and a `planRing` (its footprint). Surfaces may be stacked duplicates
 * (same footprint, different height) or overlapping alternatives.
 *
 *   envelopePlanAreaM2  exact union of the footprints — what the room covers
 *   surfaceAreaSumM2    the old arithmetic sum, retained as a diagnostic
 *   overlapAreaM2       sum - union, i.e. what the sum double counted
 *   envelopeAreaM2      Σ (exclusive plan area of a surface) × its own tilt
 *                       factor (surfaceArea/planArea), so a sloped surface keeps
 *                       its developed area while a stacked duplicate adds 0.
 *
 * Exclusive plan area is assigned in descending surface area order (largest
 * first), which is deterministic and keeps the dominant surface's tilt. The
 * order only matters when overlapping surfaces have DIFFERENT tilts; that case
 * is reported as `orderSensitive: true` with the min/max bounds so the caller
 * can warn instead of hiding the ambiguity.
 */
function envelopeArea(parts) {
  const items = (parts || [])
    .filter((p) => p && validRing(p.planRing) && finite(p.surfaceAreaM2))
    .map((p) => {
      const plan = Math.abs(ringArea(p.planRing));
      return { ring: p.planRing, ref: p.ref ?? null, surfaceAreaM2: p.surfaceAreaM2, planAreaM2: plan,
        tilt: plan > 1e-9 ? p.surfaceAreaM2 / plan : 1 };
    });
  if (!items.length) {
    return { envelopeAreaM2: null, envelopePlanAreaM2: null, surfaceAreaSumM2: null, overlapAreaM2: null,
      surfaceCount: 0, orderSensitive: false, bounds: null, method: null,
      reason: 'no supplied surface with a usable plan ring and area' };
  }
  const surfaceAreaSumM2 = items.reduce((s, q) => s + q.surfaceAreaM2, 0);
  // A supplied surface with no plan extent (a vertical plane: the producer wrote
  // an upstand) cannot be unioned in plan. Fall back to the arithmetic sum and
  // SAY SO instead of returning a zero ceiling.
  if (items.some((q) => q.planAreaM2 <= 1e-9)) {
    return {
      envelopeAreaM2: surfaceAreaSumM2, envelopePlanAreaM2: 0, surfaceAreaSumM2,
      overlapAreaM2: null, surfaceCount: items.length, orderSensitive: false, bounds: null,
      usedFallback: true,
      method: 'surface-sum fallback: at least one supplied surface has no plan footprint (vertical plane), so no plan-union envelope exists',
      reason: 'a supplied ceiling surface has zero plan extent; the arithmetic surface sum is reported and is NOT an envelope',
    };
  }
  const union = unionArea(items.map((q) => q.ring));
  const order = items.slice().sort((a, b) => b.surfaceAreaM2 - a.surfaceAreaM2 || b.planAreaM2 - a.planAreaM2);
  let cursor = 0;
  let envelope = 0;
  for (const q of order) {
    const cum = unionArea(order.slice(0, order.indexOf(q) + 1).map((z) => z.ring)).area;
    const exclusive = Math.max(0, cum - cursor);
    cursor = cum;
    envelope += exclusive * q.tilt;
  }
  const tilts = items.map((q) => q.tilt);
  const orderSensitive = items.length > 1 && (Math.max(...tilts) - Math.min(...tilts)) > 0.01;
  return {
    envelopeAreaM2: envelope,
    envelopePlanAreaM2: union.area,
    surfaceAreaSumM2,
    overlapAreaM2: Math.max(0, items.reduce((s, q) => s + q.planAreaM2, 0) - union.area),
    surfaceCount: items.length,
    orderSensitive,
    usedFallback: false,
    bounds: orderSensitive ? { minM2: union.area * Math.min(...tilts), maxM2: union.area * Math.max(...tilts) } : null,
    method: 'exact plan-union (x-sweep, split edges) of the supplied surface footprints; each surface counts once, largest first, developed area kept by its own tilt factor',
    reason: null,
  };
}

module.exports = { unionArea, envelopeArea, ringArea, validRing };
