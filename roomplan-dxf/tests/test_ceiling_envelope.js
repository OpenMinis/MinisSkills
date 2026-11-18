'use strict';
/**
 * Ceiling ENVELOPE instead of the sum of supplied surfaces.
 *
 * an anonymized regression example evidence: one room carried three supplied ceiling surfaces with the
 * SAME plan footprint (stacked alternatives at different heights). The old
 * quantity added all three, reporting 3x the room. A ceiling quantity must
 * count each plan square metre once.
 */
const assert = require('assert');
const { unionArea, envelopeArea } = require('../scripts/lib/polygon-union');
const { zoneCeilings } = require('../scripts/lib/ceiling-reconstruct');
const { buildReport } = require('../scripts/lib/quantities');

const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const near = (a, b, tol = 1e-9) => Math.abs(a - b) <= tol;
let checks = 0;
const check = (name, fn) => { fn(); checks += 1; process.stdout.write(`ok ${checks} - ${name}\n`); };

// A HORIZONTAL ceiling at height y: the local plane's second axis (local y)
// becomes the source Z axis, so world = (lx, y, ly) and the plan footprint is
// the full ring (a horizontal plane has plan extent).
const flat = (ring, y = 2.5) => ({ polygon: ring.map((p) => [p[0], p[1]]),
  transform: [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, y, 0, 1] });
const ROOM = { identifier: 'room', story: 0, area: 16, floorHeight: 0,
  vertices: [{ x: 0, z: 0 }, { x: 4, z: 0 }, { x: 4, z: 4 }, { x: 0, z: 4 }] };

check('union of two disjoint rings adds both', () => {
  assert(near(unionArea([[[0, 0], [2, 0], [2, 2], [0, 2]], [[2, 0], [4, 0], [4, 2], [2, 2]]]).area, 8));
});
check('union of two identical rings counts one footprint', () => {
  assert(near(unionArea([[[0, 0], [2, 0], [2, 2], [0, 2]], [[0, 0], [2, 0], [2, 2], [0, 2]]]).area, 4));
});
check('union of two overlapping rings subtracts the overlap', () => {
  assert(near(unionArea([[[0, 0], [2, 0], [2, 2], [0, 2]], [[1, 1], [3, 1], [3, 3], [1, 3]]]).area, 7));
});
check('three stacked identical surfaces: envelope = footprint, sum kept as diagnostic', () => {
  const e = envelopeArea([1, 2, 3].map((k) => ({ ref: `s${k}`, planRing: [[0, 0], [4, 0], [4, 4], [0, 4]], surfaceAreaM2: 16 })));
  assert(near(e.envelopeAreaM2, 16));
  assert(near(e.envelopePlanAreaM2, 16));
  assert(near(e.surfaceAreaSumM2, 48));
  assert(near(e.overlapAreaM2, 32));
  assert.strictEqual(e.surfaceCount, 3);
  assert.strictEqual(e.usedFallback, false);
});
check('exclusive coverage: a real split roof keeps both halves', () => {
  const e = envelopeArea([
    { planRing: [[0, 0], [2, 0], [2, 2], [0, 2]], surfaceAreaM2: 4 },
    { planRing: [[2, 0], [4, 0], [4, 2], [2, 2]], surfaceAreaM2: 4 },
  ]);
  assert(near(e.envelopeAreaM2, 8));
  assert(near(e.overlapAreaM2, 0));
});
check('tilt factor is kept on the exclusive part', () => {
  // surface area 6 over a plan footprint of 4 => tilt 1.5
  const e = envelopeArea([{ planRing: [[0, 0], [2, 0], [2, 2], [0, 2]], surfaceAreaM2: 6 }]);
  assert(near(e.envelopeAreaM2, 6));
  assert(near(e.envelopePlanAreaM2, 4));
});
check('vertical (zero-plan) surface: sum fallback, never a zero ceiling', () => {
  const vertical = { polygon: [[0, 0], [1, 0], [1, 1], [0, 1]], transform: I };
  const model = { rooms: [{ ...ROOM, ceiling: [vertical] }], surfaces: [] };
  const z = zoneCeilings(model)[0];
  assert.strictEqual(z.ceilingEnvelope.usedFallback, true);
  assert(near(z.ceilingArea, 1));
  const report=buildReport({...model,kind:'optimized',objects:[]},{});
  assert(near(report.totals.ceilingArea.value,1));
  assert(/surface-sum fallback/.test(report.totals.ceilingArea.reason), 'fallback must not be described as a pure envelope');
  assert(/not a verified physical total/.test(report.totals.ceilingArea.reason));
  assert.strictEqual(report.totals.ceilingArea.status,'supplied');
  assert.strictEqual(report.totals.ceilingArea.coverage,'complete');
});
check('room with three stacked source surfaces reports 16 m2, not 48', () => {
  const ring = [[0, 0], [4, 0], [4, 4], [0, 4]];
  const model = { rooms: [{ ...ROOM, ceiling: [flat(ring, 2.5), flat(ring, 2.5), flat(ring, 2.5)] }], surfaces: [] };
  const z = zoneCeilings(model)[0];
  assert(near(z.ceilingArea, 16), `zone ${z.ceilingArea}`);
  assert(near(z.surfaceAreaSumM2, 48));
  assert(near(z.envelopePlanAreaM2, 16));
  assert.strictEqual(z.stackedCount, 3);
});
check('report totals.ceilingArea is the envelope, with the avoided double count recorded', () => {
  const ring = [[0, 0], [4, 0], [4, 4], [0, 4]];
  const capture = { kind: 'optimized', rooms: [{ ...ROOM, ceiling: [flat(ring, 2.5), flat(ring, 2.5), flat(ring, 2.5)] }], surfaces: [], objects: [] };
  const rep = buildReport(capture, {});
  assert(near(rep.totals.ceilingArea.value, 16), `${rep.totals.ceilingArea.value}`);
  assert(near(rep.totals.ceilingArea.envelope.surfaceAreaSumM2, 48));
  assert(near(rep.totals.ceilingArea.envelope.doubleCountAvoidedM2, 32));
  assert.strictEqual(rep.totals.ceilingArea.status, 'supplied');
  assert(/envelope/i.test(rep.totals.ceilingArea.reason));
  assert(!/multiplicity/.test(rep.totals.ceilingArea.reason));
});
check('per-room ceiling measure carries the envelope block', () => {
  const ring = [[0, 0], [4, 0], [4, 4], [0, 4]];
  const capture = { kind: 'optimized', rooms: [{ ...ROOM, ceiling: [flat(ring, 2.5), flat(ring, 2.5)] }], surfaces: [], objects: [] };
  const rep = buildReport(capture, {});
  const r = rep.rooms[0];
  assert(r.ceilingArea.envelope != null);
  assert(near(r.ceilingArea.value, 16));
  assert(near(r.ceilingArea.envelope.surfaceAreaSumM2, 32));
});
console.log(`ceiling envelope: ${checks} checks PASS`);
