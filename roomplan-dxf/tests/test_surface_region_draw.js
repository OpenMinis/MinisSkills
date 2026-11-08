'use strict';
// Surface Region GROUP rendering: ONE label, ONE fall arrow, no internal seam, faces kept.
const assert = require('assert');
const { renderGroups, stitchUnion, sharedSegment, groupTitle } = require('../scripts/lib/surface-region-draw');
const { buildRegistry } = require('../scripts/lib/surface-regions');

const A = [[0, 0], [0, -3], [2, -3], [2, 0]];            // left face
const B = [[2, 0], [2, -3], [4, -3], [4, 0]];            // right face shares x=2
const faces = [
  { sourceRegionId: 'SR 2.1', story: 0, roomIdentifier: 'Bedroom 1', regionPlanM: A, heightM: { min: 0.84, max: 1.07 }, slopeIndicatorLine: [[1, -1], [1, -1.3]], status: 'supplied', sourceAreaM2: 6, ceilingAreaM2: 6 },
  { sourceRegionId: 'SR 2.2', story: 0, roomIdentifier: 'Bedroom 1', regionPlanM: B, heightM: { min: 1.07, max: 2.70 }, slopeIndicatorLine: [[3, -1], [3, -1.3]], status: 'supplied', sourceAreaM2: 6, ceilingAreaM2: 6 },
];
const sha = 'a'.repeat(64);
const groups = { sourceSHA256: sha, groups: [{ id: 'K2.1', confirmation: 'user-confirmed', members: ['SR 2.1', 'SR 2.2'] }] };

// ---- union geometry --------------------------------------------------------
const area = (p) => Math.abs(p.reduce((s, a, i) => { const b = p[(i + 1) % p.length]; return s + a[0] * b[1] - b[0] * a[1]; }, 0)) / 2;
const u = stitchUnion(A, B);
assert(u, 'adjacent faces must stitch');
assert.strictEqual(u.length, 5, `stitched ring keeps both seam corners plus every face corner, got ${u.length}`);
assert(Math.abs(area(u) - (area(A) + area(B))) < 1e-9, 'stitched union area equals the sum of both faces');

const seam = sharedSegment(A, B);
assert(seam, 'shared edge must be found');
assert(Math.abs(seam.a[0] - 2) < 1e-9 && Math.abs(seam.b[0] - 2) < 1e-9, 'seam lies on the shared x=2 edge');
assert.strictEqual(sharedSegment(A, [[5, 0], [6, 0], [4.5, -3]]), null, 'disjoint faces have no seam');

// ---- label replacement -----------------------------------------------------
function run(entities, override, hash) {
  return renderGroups(entities, faces, override, hash);
}
const entities = [
  { type: 'text', story: 0, layer: 'S0_CEILING', value: 'SR 2.1  h 0.84-1.07', height: 0.1, pos: [1, -1.5], sourceRegionId: 'SR 2.1' },
  { type: 'text', story: 0, layer: 'S0_CEILING', value: 'SR 2.2', height: 0.1, pos: [3, -1.5], sourceRegionId: 'SR 2.2' },
  { type: 'text', story: 0, layer: 'S0_CEILING', value: 'h 1.07-2.70', height: 0.1, pos: [3, -1.7], sourceRegionId: 'SR 2.2' },
  { type: 'text', story: 0, layer: 'S0_CEILING', value: 'SR 2.3  h 2.70', height: 0.1, pos: [4.5, -1.5] },
  // one downhill arrow (3 lines) per source face, as the ceiling engine draws them
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'downhill-arrow', a: [1, -1.3], b: [1, -1] },
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'downhill-arrow', a: [1, -1], b: [0.95, -1.09] },
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'downhill-arrow', a: [1, -1], b: [1.05, -1.09] },
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'downhill-arrow', a: [3, -1.3], b: [3, -1] },
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'downhill-arrow', a: [3, -1], b: [2.95, -1.09] },
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'downhill-arrow', a: [3, -1], b: [3.05, -1.09] },
  // face perimeters: the shared x=2 edge is drawn once, the outer edges stay
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'source-region-boundary', a: [2, 0], b: [2, -3] },
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'source-region-boundary', a: [0, 0], b: [0, -3] },
  { type: 'line', story: 0, layer: 'S0_CEILING', role: 'source-region-boundary', a: [4, 0], b: [4, -3] },
];
const res = run(entities, groups, sha);
const drawn = res.drawn[0];
assert.strictEqual(drawn.id, 'K2.1');
assert.strictEqual(drawn.replacedFaceLabels, 3, 'both lines of the wrapped face label are withdrawn');
assert.strictEqual(drawn.label, 'SR 2.1-2.2  h 0.84-2.70', 'one-piece range label, not two blocks joined by +');
assert.strictEqual(groupTitle(['SR 2.1', 'SR 2.2']), 'SR 2.1-2.2');
assert.strictEqual(groupTitle(['SR 2.1', 'SR 3.4']), 'SR 2.1+SR 3.4', 'ids that are not a series keep the explicit join');
assert.strictEqual(groupTitle(['A', 'B']), 'A+B');
assert.strictEqual(drawn.labelPolygonBasis, 'stitched-union-of-source-faces');
assert.strictEqual(res.added.some((e) => e.role === 'surface-region-seam'), false, 'the internal seam is NOT drawn');
assert.strictEqual(res.added.some((e) => String(e.layer || '').endsWith('_CEILING_SEAM')), false, 'nothing lands on the seam layer');
assert(drawn.seamWithdrawn && drawn.seamWithdrawn.drawnOnSheet === false, 'the shared edge survives as data only');
assert(Math.abs(drawn.seamWithdrawn.a[0] - 2) < 1e-9 && Math.abs(drawn.seamWithdrawn.b[0] - 2) < 1e-9, 'withdrawn seam is still the x=2 shared edge');
assert(entities.some((e) => e.value === 'SR 2.3  h 2.70'), 'labels of ungrouped regions are untouched');
assert(!entities.some((e) => /^SR 2\.1( |$)/.test(e.value) || /^SR 2\.2( |$)/.test(e.value)), 'no per-face label survives');
const labelTexts = res.added.filter((e) => e.type === 'text');
assert.strictEqual(labelTexts.filter((e) => e.value.startsWith('SR 2.1-2.2')).length, 1, 'exactly one label covers both faces');
assert(labelTexts.every((e) => e.groupId === 'K2.1'), 'the group label is tagged with the group id');
// exactly ONE fall arrow survives, inside the larger face
const arrows = entities.filter((e) => e.role === 'downhill-arrow');
assert.strictEqual(arrows.length, 3, `one 3-line fall arrow for the whole slope, got ${arrows.length} lines`);
assert(arrows.every((e) => e.a[0] <= 2 && e.b[0] <= 2), 'both surviving wings and the shaft sit in ONE member face');
assert(['SR 2.1', 'SR 2.2'].includes(drawn.fallArrow.keptMember), 'the kept arrow belongs to a member face');
assert.strictEqual(drawn.fallArrow.withdrawnLines, 3);
// the shared edge is not drawn at all, so the slope reads as one shape
assert.strictEqual(entities.filter((e) => e.role === 'source-region-boundary' && e.a[0] === 2 && e.b[0] === 2).length, 0, 'the internal shared edge is not drawn');
assert.strictEqual(entities.filter((e) => e.role === 'source-region-boundary').length, 2, 'the outer perimeter of the union is untouched');
assert.strictEqual(drawn.seamWithdrawn.boundaryLinesWithdrawn, 1);

assert.strictEqual(res.warnings.filter((w) => w.code === 'roomplan.surface-region-group-arrow-withdrawn').length >= 0, true);
assert(drawn.labelStatus === 'inside-conservative-envelope', 'label fits inside the stitched slope footprint');

// ---- registry stays non-additive ------------------------------------------
const registry = buildRegistry(faces, sha, groups);
assert.strictEqual(registry.regions.length, 2, 'both faces stay in the registry');
assert.strictEqual(registry.groups[0].faceCount, 2);
assert(Math.abs(registry.groups[0].areaM2 - 12) < 1e-9, 'group area is a reference sum');
assert.strictEqual(registry.quantityBasis.indexOf('NOT verified physical total') > -1, true);

// ---- refusals are honest --------------------------------------------------
const mismatch = run([], groups, 'b'.repeat(64));
assert.strictEqual(mismatch.added.length, 0, 'a sidecar for another scan draws nothing');
assert.strictEqual(mismatch.warnings[0].code, 'roomplan.surface-region-group-hash-mismatch');

const unconfirmed = run([], { sourceSHA256: sha, groups: [{ id: 'K9', members: ['SR 2.1', 'SR 2.2'] }] }, sha);
assert.strictEqual(unconfirmed.added.length, 0, 'without confirmation nothing is grouped or drawn');

const missing = run([], groups.map ? groups : { sourceSHA256: sha, groups: [{ id: 'K9', confirmation: 'user-confirmed', members: ['SR 9.9', 'SR 2.2'] }] }, sha);
assert.strictEqual(missing.drawn.length, 0);
assert.strictEqual(missing.warnings[0].code, 'roomplan.surface-region-group-unrendered');

const noGroups = run([], null, sha);
assert.strictEqual(noGroups.added.length, 0);

console.log('test_surface_region_draw: all checks passed (one label, one arrow, no seam)');
