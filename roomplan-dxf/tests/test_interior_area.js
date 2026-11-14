'use strict';
/**
 * tests/test_interior_area.js — unit tests for scripts/lib/interior-area.js
 * (SPEC section 5: interior floor area excluding wall footprints, G-6 / G-7).
 * Expectations are computed here from the fixture geometry (clear opening =
 * ring minus wall thickness), never read back out of the module.
 */
const assert = require('assert');
const IA = require('../scripts/lib/interior-area');

let checks = 0;
function check(name, fn) {
  try {
    fn();
    checks++;
  } catch (e) {
    console.error(`FAIL ${name}: ${e.message}`);
    process.exit(1);
  }
}
const near = (a, b, tol = 1e-9) => assert.ok(Math.abs(a - b) <= tol, `${a} != ${b} (tol ${tol})`);

const sq = (size, origin = 0) => [
  { x: origin, y: origin }, { x: origin + size, y: origin }, { x: origin + size, y: origin + size }, { x: origin, y: origin + size },
];
const rectWalls = (size, thickness, origin = 0) => {
  const o = origin;
  return [
    { start: { x: o, y: o }, end: { x: o + size, y: o }, thickness },
    { start: { x: o + size, y: o }, end: { x: o + size, y: o + size }, thickness },
    { start: { x: o + size, y: o + size }, end: { x: o, y: o + size }, thickness },
    { start: { x: o, y: o + size }, end: { x: o, y: o }, thickness },
  ];
};

// ------------------------------------------------------------- whole ring
check('room with no walls is its own area', () => near(IA.interiorRoomArea(sq(2), [], []), 4));
check('room with no walls and a 1 m2 hole', () => near(IA.interiorRoomArea(sq(2), [sq(1)], []), 3));
check('centerlineArea of a 2 m square', () => near(IA.centerlineArea(sq(2), []), 4));
check('centerlineArea subtracts holes', () => near(IA.centerlineArea(sq(2), [sq(1)]), 3));

// ------------------------------------------- G-6 / G-7 physical plan, 0.15 m
const T = 0.15;
check('G-6 reference edges: 1.00 m clear room is exactly 1.0000 m2',
  () => near(IA.interiorRoomArea(sq(1.0), [], rectWalls(1.0, T), { wallConvention: 'reference-edges' }), 1.0, 1e-12));
check('G-7 centreline: ring 1.15 m, 0.15 m walls -> the same 1.0000 m2 clear area',
  () => near(IA.interiorRoomArea(sq(1.15), [], rectWalls(1.15, T)), 1.0, 1e-12));
check('G-7 centreline polygon area is 1.15^2 = 1.3225 m2',
  () => near(IA.centerlineArea(sq(1.15), []), 1.3225, 1e-12));
check('centreline walls on the inner-face ring would eat 0.075 m per side (0.7225 m2)',
  () => near(IA.interiorRoomArea(sq(1.0), [], rectWalls(1.0, T)), 0.7225, 1e-12));

// ------------------------------------------------------------- union, not sum
check('two identical overlapping walls count once', () => {
  const wall = { start: { x: 1.15, y: 0 }, end: { x: 1.15, y: 1.15 }, thickness: T };
  const one = IA.interiorRoomArea(sq(1.15), [], [wall]);
  const two = IA.interiorRoomArea(sq(1.15), [], [wall, { ...wall }]);
  near(two, one, 1e-12);
  near(one, 1.15 * 1.15 - 0.5 * 1.15 * T, 1e-9); // one wall along a full side
});
check('a wall outside the room removes nothing', () => {
  const outside = { start: { x: -1, y: 0 }, end: { x: -1, y: 2 }, thickness: T };
  near(IA.interiorRoomArea(sq(2), [], [outside]), 4, 1e-12);
});
check('a thin interior partition removes its footprint', () => {
  const partition = { start: { x: 1, y: 0 }, end: { x: 1, y: 2 }, thickness: 0.1 };
  near(IA.interiorRoomArea(sq(2), [], [partition]), 4 - 2 * 0.1, 1e-12);
});
check('curved wall is faceted (16 segments), not bounding-boxed', () => {
  const curved = { start: { x: 0, y: 0.5 }, end: { x: 2, y: 0.5 }, curvePoint: { x: 1, y: 1.5 }, thickness: 0.1 };
  const area = IA.interiorRoomArea(sq(2), [], [curved]);
  assert.ok(area !== null);
  const facets = IA.wallPathSpans(curved);
  assert.strictEqual(facets.length, 16);
  const length = facets.reduce((s, [a, b]) => s + Math.hypot(b.x - a.x, b.y - a.y), 0);
  assert.ok(length < 2.6, `faceted path length ${length} should be well under the bounding box perimeter`);
  assert.ok(area < 4 && area > 3.5, `area ${area}`);
});

// ----------------------------------------------------------------- units
check("units:'cm' accepts the TS original's centimetres and still answers m2", () => {
  const ringCm = sq(115);
  const wallsCm = rectWalls(115, 15);
  near(IA.interiorRoomArea(ringCm, [], wallsCm, { units: 'cm' }), 1.0, 1e-12);
  near(IA.centerlineArea(ringCm, [], { units: 'cm' }), 1.3225, 1e-12);
});

// --------------------------------------------------------------- refusals
check('ring with fewer than 3 points is null', () => assert.strictEqual(IA.interiorRoomArea([{ x: 0, y: 0 }, { x: 1, y: 1 }], [], []), null));
check('non-finite vertex is null', () => assert.strictEqual(IA.interiorRoomArea([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: NaN, y: 1 }], [], []), null));
check('thickness 0 is null (not a free pass)', () => assert.strictEqual(IA.interiorRoomArea(sq(2), [], [{ start: { x: 0, y: 0 }, end: { x: 2, y: 0 }, thickness: 0 }]), null));
check('missing wall endpoints is null', () => assert.strictEqual(IA.interiorRoomArea(sq(2), [], [{ thickness: 0.1 }]), null));
check('invalid hole ring is null', () => assert.strictEqual(IA.interiorRoomArea(sq(2), [[{ x: 0, y: 0 }]], []), null));
check('edge budget is refused, not truncated', () => {
  const walls = [];
  for (let i = 0; i < 200; i++) walls.push({ start: { x: (i % 20) * 0.1, y: Math.floor(i / 20) * 0.1 }, end: { x: (i % 20) * 0.1 + 0.05, y: Math.floor(i / 20) * 0.1 + 0.05 }, thickness: 0.01 });
  assert.strictEqual(IA.interiorRoomArea(sq(2), [], walls, { maxEdges: 600 }), null);
});
check('budget on levels x edges is refused', () => assert.strictEqual(IA.interiorRoomArea(sq(2), [], rectWalls(2, T), { maxLevelsTimesEdges: 4 }), null));
check('centerlineArea null on invalid input', () => assert.strictEqual(IA.centerlineArea([{ x: 0, y: 0 }], []), null));

console.log(`interior-area: ${checks} checks passed`);
