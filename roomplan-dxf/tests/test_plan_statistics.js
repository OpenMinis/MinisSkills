'use strict';
/**
 * tests/test_plan_statistics.js — scripts/lib/plan-statistics.js against the
 * REAL ArchiPlan fixtures (SPEC §5 G-9).
 *
 * Every expectation comes from the fixture file, and the fixture file's numbers
 * come from ArchiPlan tests/planStatistics.test.ts (commit recorded in _meta).
 * Nothing is read back out of the port: if the port disagrees, this test FAILS
 * with both numbers and the deviation is written up in REPORT.md — the
 * expectation is never adjusted to match the code.
 */
const assert = require('assert');
const path = require('path');
const PS = require('../scripts/lib/plan-statistics');

const FIXTURE = require(path.join(__dirname, 'fixtures', 'archiplan-plan-statistics.json'));
const TOL = 1e-4;

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
function near(actual, expected, label) {
  assert.ok(typeof actual === 'number' && Number.isFinite(actual), `${label}: expected ${expected}, got ${actual}`);
  assert.ok(Math.abs(actual - expected) <= TOL, `${label}: expected ${expected}, got ${actual} (delta ${(actual - expected).toFixed(6)})`);
}
const caseOf = (id) => {
  const found = FIXTURE.cases.find((c) => c.id === id);
  assert.ok(found, `fixture case ${id} missing`);
  return found;
};

// --------------------------------------------------------------- provenance
check('fixture records where it comes from (repo + commit)', () => {
  assert.strictEqual(typeof FIXTURE._meta.commit, 'string');
  assert.ok(FIXTURE._meta.commit.length === 40, 'full commit sha expected');
  assert.ok(FIXTURE._meta.files.some((f) => f.includes('tests/planStatistics.test.ts')));
});

// ------------------------------------------------- case 1: studio 4 x 3 m
check('case 1 is capture-v1 (our contract), not ArchiPlan plan.json', () => {
  assert.strictEqual(caseOf('studio-4x3-interior-face').input.schemaVersion, 'roomplan.capture/1');
});

const studio = PS.planStatistics(caseOf('studio-4x3-interior-face').input);
const studioExp = caseOf('studio-4x3-interior-face').expected;

check('case 1 produces a statistics block', () => assert.ok(studio.ok && studio.statistics));
check('case 1 version/units', () => {
  assert.strictEqual(studio.statistics.version, 1);
  assert.strictEqual(studio.statistics.units, 'metres');
});
for (const [field, expected] of Object.entries(studioExp.totals)) {
  check(`case 1 totals.${field} = ${expected}`, () => near(studio.statistics.totals[field], expected, `totals.${field}`));
}
check('case 1 living area is the interior-face number 10.9725', () => near(studio.statistics.totals.livingArea, 10.9725, 'livingArea'));
check('case 1 net walls are 35 - 1.89', () => near(studio.statistics.totals.wallAreaNet, 35 - 1.89, 'wallAreaNet'));
check('case 1 level indices', () => assert.deepStrictEqual(studio.statistics.levels.map((l) => l.index), studioExp.levelIndices));
check('case 1 level 0 totals equal the plan totals', () => assert.deepStrictEqual(studio.statistics.levels[0].totals, studio.statistics.totals));
check('case 1 room block', () => {
  assert.strictEqual(studio.statistics.rooms.length, 1);
  const room = studio.statistics.rooms[0];
  const exp = studioExp.rooms[0];
  assert.strictEqual(room.id, exp.id);
  assert.strictEqual(room.name, exp.name);
  assert.strictEqual(room.level, exp.level);
  assert.strictEqual(room.floorOpening, exp.floorOpening);
  near(room.floorArea, exp.floorArea, 'rooms[0].floorArea');
  near(room.ceilingHeight, exp.ceilingHeight, 'rooms[0].ceilingHeight');
});
check('case 1 costs', () => assert.deepStrictEqual(studio.statistics.costs, studioExp.costs));
check('case 1 has no area gap', () => assert.deepStrictEqual(studio.gaps, []));
check('case 1 room area provenance is computed by interiorRoomArea', () => {
  const a = studio.areas['room-a'];
  assert.strictEqual(a.status, 'computed');
  assert.ok(/interiorRoomArea/.test(a.reason));
});

// --------------------------------------------- case 2: native QA Kitchen
const native = PS.planStatistics(caseOf('qa-kitchen-native-plan').input);
const nativeExp = caseOf('qa-kitchen-native-plan').expected;

check('case 2 produces a statistics block', () => assert.ok(native.ok && native.statistics));
for (const [field, expected] of Object.entries(nativeExp.totals)) {
  check(`case 2 totals.${field} = ${expected}`, () => near(native.statistics.totals[field], expected, `totals.${field}`));
}
check('case 2 level indices include the empty Future Floor', () => assert.deepStrictEqual(native.statistics.levels.map((l) => l.index), nativeExp.levelIndices));
for (const level of native.statistics.levels) {
  const exp = nativeExp.levelTotals[String(level.index)];
  for (const [field, expected] of Object.entries(exp)) {
    check(`case 2 level ${level.index} ${field} = ${expected}`, () => near(level.totals[field], expected, `level ${level.index} ${field}`));
  }
}
check('case 2 QA Kitchen keeps a measured area and is NOT counted as unenclosed', () => {
  assert.strictEqual(native.statistics.totals.roomsWithoutArea, 0);
  const room = native.statistics.rooms[0];
  assert.strictEqual(room.name, 'QA Kitchen');
  assert.strictEqual(room.level, 0);
  assert.ok(room.floorArea > nativeExp.rooms[0].floorAreaGreaterThan, `floorArea ${room.floorArea} must exceed ${nativeExp.rooms[0].floorAreaGreaterThan}`);
  near(room.floorArea, nativeExp.rooms[0].floorArea, 'rooms[0].floorArea');
  near(room.ceilingHeight, nativeExp.rooms[0].ceilingHeight, 'rooms[0].ceilingHeight');
});
check('case 2 costs count only priced items', () => assert.deepStrictEqual(native.statistics.costs, nativeExp.costs));
check('case 2 a level without rooms does not invent living area (source sums zero)', () => {
  const level2 = native.statistics.levels.find((l) => l.index === 2);
  near(level2.totals.livingArea, 0, 'level 2 livingArea');
});

// ------------------------------------------------- refusals / gaps (10.x)
check('a room without a polygon has no area and is counted, never estimated', () => {
  const r = PS.planStatistics({
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 }],
    openings: [], furniture: [], levels: [],
    rooms: [{ id: 'orphan', name: 'Label only', level: 0 }],
  });
  assert.ok(r.ok);
  assert.strictEqual(r.statistics.totals.roomsWithoutArea, 1);
  assert.strictEqual(r.statistics.rooms[0].floorArea, undefined, 'unknown area must be omitted, never 0');
  assert.strictEqual(r.areas.orphan.value, null);
  assert.strictEqual(r.gaps.length, 1);
});
check('a floor opening contributes exactly zero, like the source', () => {
  const r = PS.planStatistics({
    walls: [], openings: [], furniture: [], levels: [],
    rooms: [{ id: 'open', name: 'Stair void', level: 0, floorOpening: true, polygon: [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }] }],
  });
  assert.strictEqual(r.statistics.totals.roomsWithoutArea, 0);
  assert.strictEqual(r.statistics.rooms[0].floorArea, 0);
  assert.strictEqual(r.areas.open.status, 'computed');
});
check('an opening without a height falls back to 2.0 / 1.2 m and says so', () => {
  const r = PS.planStatistics({
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 }],
    openings: [{ id: 'd', wallID: 'w', kind: 'door', width: 1 }, { id: 'win', wallID: 'w', kind: 'window', width: 1 }],
    furniture: [], rooms: [], levels: [],
  });
  near(r.statistics.totals.openingArea, 1 * 2.0 + 1 * 1.2, 'openingArea');
  assert.strictEqual(r.statistics.totals.doorCount, 1);
  assert.strictEqual(r.statistics.totals.windowCount, 1);
});
check('an unusable input returns null with a reason, not a block of zeros', () => {
  const r = PS.planStatistics({ walls: [], openings: [], rooms: [], furniture: [] });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.statistics, null);
  assert.ok(typeof r.reason === 'string' && r.reason.length > 10, `reason: ${r.reason}`);
});
check('a wall thinner than zero is refused by interiorRoomArea, not treated as no wall', () => {
  const r = PS.planStatistics({
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 }],
    openings: [], furniture: [], levels: [],
    rooms: [{ id: 'r', name: 'R', level: 0, polygon: [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 3 }, { x: 0, y: 3 }], holes: [[{ x: 0, y: 0 }]] }],
  });
  assert.strictEqual(r.areas.r.value, null);
  assert.strictEqual(r.statistics.totals.roomsWithoutArea, 1);
});
check('rounding matches planStatistics.ts: 6 decimals', () => {
  const r = PS.planStatistics({
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 1 / 3, y: 0 }, height: 2.5, thickness: 0.12, level: 0 }],
    openings: [], furniture: [], rooms: [], levels: [],
  });
  const v = r.statistics.totals.wallAreaGross;
  assert.strictEqual(v, Math.round(v * 1e6) / 1e6);
});

console.log(`plan-statistics: ${checks} checks passed (fixtures: ArchiPlan ${FIXTURE._meta.commit.slice(0, 7)})`);
