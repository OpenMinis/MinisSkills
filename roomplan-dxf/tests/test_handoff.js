'use strict';
/**
 * tests/test_handoff.js — scripts/lib/handoff.js against the REAL ArchiPlan
 * package fixtures (SPEC §5 G-10).
 *
 * Inputs are the plan.json records extracted verbatim from the test packages;
 * the expected level numbers are the committed reference outputs of the same
 * handoff (tests/fixtures/skills/*.handoff.json, held equal to handoff.ts by
 * tests/skills-parity.test.ts). The one intentional deviation — areas we
 * derive where ArchiPlan printed null — is recorded in the fixture's
 * _meta.intentionalDeviation and checked explicitly below.
 */
const assert = require('assert');
const path = require('path');
const H = require('../scripts/lib/handoff');

const FIXTURE = require(path.join(__dirname, 'fixtures', 'archiplan-handoff.json'));
const TOL = 1e-4;
const QUANTITY_KEYS = ['floorArea', 'ceilingArea', 'wallAreaNetRoom', 'wallRunRoom',
  'livingAreaLevel', 'wallAreaNetLevel', 'wallAreaGrossLevel', 'wallRunLevel', 'doors', 'windows'];

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
const mv = (m, label) => {
  assert.ok(m && typeof m === 'object', `${label}: measure missing`);
  return m.value;
};
const caseOf = (id) => {
  const found = FIXTURE.cases.find((c) => c.id === id);
  assert.ok(found, `fixture case ${id} missing`);
  return found;
};

check('fixture records repo, commit and the class of packages used', () => {
  assert.ok(FIXTURE._meta.commit.length === 40);
  assert.ok(FIXTURE._meta.files.some((f) => f.includes('tests/skills-parity.test.ts')));
  assert.ok(FIXTURE._meta.intentionalDeviation, 'the null-vs-derived deviation must be documented in the fixture');
});

// ------------------------------------------------------ case 1: web package
const web = caseOf('web-project-package');
const webScope = H.handoff(web.input).scope;
check('web package produces a scope', () => assert.ok(webScope));
for (const [field, expected] of Object.entries(web.expected.summary)) {
  if (expected === null) continue;
  check(`web summary.${field}`, () => {
    if (['levelCount', 'roomCount', 'wallCount', 'doorCount', 'windowCount', 'furnitureCount'].includes(field)) assert.strictEqual(webScope.summary[field], expected, field);
    else near(mv(webScope.summary[field], field), expected, field);
  });
}
check('web summary has no living/gross area (no rooms -> unknown, not 0)', () => {
  assert.strictEqual(webScope.summary.livingArea, null);
  assert.strictEqual(webScope.summary.grossArea, null);
});
check('web level 0 numbers', () => {
  const level = webScope.levels[0];
  const exp = web.expected.levels[0];
  assert.strictEqual(level.index, exp.index);
  assert.strictEqual(level.name, exp.name);
  near(mv(level.wallRun, 'run'), exp.wallRun, 'wallRun');
  near(mv(level.wallAreaGross, 'gross'), exp.wallAreaGross, 'wallAreaGross');
  near(mv(level.wallAreaNet, 'net'), exp.wallAreaNet, 'wallAreaNet');
  near(mv(level.openingArea, 'opening'), exp.openingArea, 'openingArea');
  assert.strictEqual(level.doorCount, exp.doorCount);
  assert.strictEqual(level.windowCount, exp.windowCount);
  assert.strictEqual(level.wallCount, exp.wallCount);
  assert.strictEqual(level.furnitureCount, exp.furnitureCount);
});
check('web quantity keys and order (no livingAreaLevel without rooms)', () => {
  assert.deepStrictEqual(webScope.quantities.map((q) => q.key), web.expected.quantityKeys);
  for (const [key, value] of Object.entries(web.expected.quantityValues)) {
    const item = webScope.quantities.find((q) => q.key === key);
    assert.ok(item, `quantity ${key} missing`);
    near(item.quantity, value, `quantity ${key}`);
  }
});
check('web every quantity key belongs to the contracted vocabulary', () => {
  for (const q of webScope.quantities) assert.ok(QUANTITY_KEYS.includes(q.key), `unknown quantity key ${q.key}`);
});
check('web gaps say that per-room quantities are unavailable', () => {
  for (const text of web.expected.gapContains) assert.ok(webScope.gaps.includes(text), `missing gap: ${text}`);
});
check('web furniture inventory keeps the category bucket', () => {
  const bucket = webScope.levels[0].furniture.chair;
  assert.ok(bucket && bucket.count === 1, 'one chair expected');
  near(mv(bucket.items[0].width, 'width'), 1.3, 'chair width');
});

// --------------------------------------------------- case 2: native package
const nat = caseOf('native-project-package');
const natScope = H.handoff(nat.input).scope;
check('native package produces a scope', () => assert.ok(natScope));
for (const [field, expected] of Object.entries(nat.expected.summary)) {
  check(`native summary.${field}`, () => {
    if (['levelCount', 'roomCount', 'wallCount', 'doorCount', 'windowCount', 'furnitureCount'].includes(field)) assert.strictEqual(natScope.summary[field], expected, field);
    else near(mv(natScope.summary[field], field), expected, field);
  });
}
check('native level count and names', () => assert.deepStrictEqual(natScope.levels.map((l) => l.name), nat.expected.levels.map((l) => l.name)));
for (const expLevel of nat.expected.levels) {
  const level = natScope.levels.find((l) => l.index === expLevel.index);
  check(`native level ${expLevel.index} present`, () => assert.ok(level));
  for (const [field, expected] of Object.entries(expLevel)) {
    if (field === 'index' || field === 'name') continue;
    check(`native level ${expLevel.index} ${field}`, () => {
      if (expected === null) {
        assert.strictEqual(level[field], null, `${field} should be null on a level with no measurable room`);
        return;
      }
      if (['wallCount', 'furnitureCount', 'doorCount', 'windowCount'].includes(field)) assert.strictEqual(level[field], expected, field);
      else near(mv(level[field], field), expected, field);
    });
  }
}
check('native room entry carries boundary figures from the room own walls only', () => {
  const room = natScope.levels[0].rooms[0];
  const exp = nat.expected.room;
  assert.strictEqual(room.name, exp.name);
  near(mv(room.floorArea, 'floorArea'), exp.floorArea, 'floorArea');
  near(mv(room.ceilingArea, 'ceilingArea'), exp.ceilingArea, 'ceilingArea');
  assert.strictEqual(room.ceilingMethod, exp.ceilingMethod);
  near(mv(room.ceilingHeight, 'ceilingHeight'), exp.ceilingHeight, 'ceilingHeight');
  near(mv(room.boundaryWallRun, 'boundaryWallRun'), exp.boundaryWallRun, 'boundaryWallRun');
  near(mv(room.boundaryWallAreaGross, 'boundaryWallAreaGross'), exp.boundaryWallAreaGross, 'boundaryWallAreaGross');
  near(mv(room.boundaryWallAreaNet, 'boundaryWallAreaNet'), exp.boundaryWallAreaNet, 'boundaryWallAreaNet');
  assert.strictEqual(room.boundaryDoorCount, exp.boundaryDoorCount);
  assert.strictEqual(room.boundaryWindowCount, exp.boundaryWindowCount);
  assert.strictEqual(room.boundaryWallCount, exp.boundaryWallCount);
  assert.ok(/geometric membership/.test(room.boundaryMethod), `boundaryMethod: ${room.boundaryMethod}`);
});
check('native quantity keys are exactly the contracted keys, in order, per room then per level', () => {
  assert.deepStrictEqual(natScope.quantities.slice(0, 10).map((q) => q.key), nat.expected.quantityKeys);
  for (const q of natScope.quantities) assert.ok(QUANTITY_KEYS.includes(q.key), `unknown quantity key ${q.key}`);
});
check('native quantity values', () => {
  for (const [key, value] of Object.entries(nat.expected.quantityValues)) {
    const item = natScope.quantities.find((q) => q.key === key && (q.room != null || !['floorArea', 'ceilingArea', 'wallAreaNetRoom', 'wallRunRoom'].includes(key)));
    assert.ok(item, `quantity ${key} missing`);
    near(item.quantity, value, `quantity ${key}`);
  }
});
check('native room quantities are attributed to the room, level ones to the level', () => {
  for (const q of natScope.quantities.slice(0, 4)) {
    assert.strictEqual(q.room, 'QA Kitchen');
    assert.strictEqual(q.level, 'Entry');
  }
  for (const q of natScope.quantities.slice(4, 10)) {
    assert.strictEqual(q.room, null);
    assert.strictEqual(q.level, 'Entry');
  }
});
check('native has no gaps: nothing is missing on this package', () => assert.deepStrictEqual(natScope.gaps, nat.expected.gapContains));
check('native ceiling method comes from our ceiling layer', () => {
  const rooms = natScope.levels.flatMap((l) => l.rooms);
  for (const room of rooms) assert.ok(['flat', 'knee', 'section', 'extrusion', 'unavailable'].includes(room.ceilingMethod), `method ${room.ceilingMethod}`);
});

// ------------------------------------------------ codes, gaps, deviations
check('codes are applied only to keys that actually produced a quantify', () => {
  const r = H.handoff(nat.input, { codes: { wallAreaNetLevel: 'ZID-01', doors: 'VR-01', notAKey: 'X' } });
  const coded = r.scope.quantities.filter((q) => q.code);
  for (const q of coded) assert.ok(['wallAreaNetLevel', 'doors'].includes(q.key), `unexpected code on ${q.key}`);
  assert.deepStrictEqual(r.scope.codesApplied, ['doors', 'wallAreaNetLevel']);
  assert.ok(!r.scope.quantities.some((q) => q.code === 'X'));
});
check('a room without a measured area produces a gap and no zero quantity', () => {
  const r = H.handoff({
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 }],
    openings: [], furniture: [], levels: [],
    rooms: [{ id: 'r1', name: 'Label only', level: 0 }],
  });
  assert.strictEqual(r.ok, true);
  assert.ok(r.scope.gaps.some((g) => /has no measured floor area/.test(g)), r.scope.gaps.join(' | '));
  const roomKeys = r.scope.quantities.filter((q) => q.room === 'Label only').map((q) => q.key);
  assert.deepStrictEqual(roomKeys, [], 'no room quantity may be emitted from an unknown area');
});
check('an opening whose parent wall is absent is reported as a gap, not double counted', () => {
  const r = H.handoff({
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 }],
    openings: [{ id: 'd', wallID: 'ghost', kind: 'door', width: 0.9, height: 2.1 }],
    furniture: [], levels: [], rooms: [],
  });
  assert.ok(r.scope.gaps.some((g) => /references wall 'ghost'/.test(g)), r.scope.gaps.join(' | '));
  const level = r.scope.levels.find((l) => l.index === 0);
  assert.strictEqual(level.doorCount, 0, 'an opening on a missing wall is not a level door');
});
check('a room without photos is reported (only when it has none)', () => {
  const base = {
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 }],
    openings: [], furniture: [], levels: [],
  };
  const bare = H.handoff({ ...base, rooms: [{ id: 'r', name: 'Bare', level: 0, polygon: [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 3 }, { x: 0, y: 3 }] }] });
  assert.ok(bare.scope.gaps.includes("Room 'Bare' (Ground Floor) has no photos."));
  const withPhoto = H.handoff({ ...base, rooms: [{ id: 'r', name: 'Snapped', level: 0, photos: ['a.png'], polygon: [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 3 }, { x: 0, y: 3 }] }] });
  assert.ok(!withPhoto.scope.gaps.some((g) => /no photos/.test(g)));
});
check('a referenced photo missing from the asset list is a gap (package evidence)', () => {
  const r = H.handoff(nat.input, { assets: ['other.png'] });
  assert.ok(r.scope.gaps.some((g) => g === "Photo 'chair.png' is referenced but not included in the package."), r.scope.gaps.join(' | '));
  assert.deepStrictEqual(r.scope.evidence.missingPhotos, ['chair.png']);
});
check('supplied boundaryWallIDs win over geometric membership and are labelled as such', () => {
  const r = H.handoff({
    walls: [
      { id: 'a', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 },
      { id: 'b', start: { x: 4, y: 0 }, end: { x: 4, y: 3 }, height: 2.5, thickness: 0.15, level: 0 },
    ],
    openings: [{ id: 'd', wallID: 'a', kind: 'door', width: 0.9, height: 2.1 }],
    furniture: [], levels: [],
    rooms: [{ id: 'r', name: 'Half', level: 0, boundaryWallIDs: ['a'], polygon: [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 3 }, { x: 0, y: 3 }] }],
  });
  const room = r.scope.levels[0].rooms[0];
  assert.strictEqual(room.boundaryMethod, 'supplied boundaryWallIDs');
  near(mv(room.boundaryWallRun, 'run'), 4, 'boundaryWallRun');
  near(mv(room.boundaryWallAreaNet, 'net'), 10 - 0.9 * 2.1, 'boundaryWallAreaNet');
});
check('the documented deviation is real: ArchiPlan printed null areas, we derive them', () => {
  const ref = nat.expected;
  assert.ok(ref.summary.livingArea > 0, 'our port must have a living area here');
  assert.strictEqual(FIXTURE._meta.intentionalDeviation.referenceNulls.case2['summary.livingArea'], null);
});
check('units are the source units both ways', () => {
  assert.deepStrictEqual(natScope.units, { metric: 'metres and square metres', imperial: 'feet and square feet, rounded to 0.1' });
  const q = natScope.quantities[0];
  assert.strictEqual(q.unit, 'm²');
  assert.strictEqual(q.imperialUnit, 'ft²');
  assert.ok(Math.abs(q.imperialQuantity - q.quantity * 10.76391042) <= 0.1,
    `imperial conversion: ${q.imperialQuantity} vs ${(q.quantity * 10.76391042).toFixed(3)} (measure() rounds to 0.1)`);
});

console.log(`handoff: ${checks} checks passed (fixtures: ArchiPlan ${FIXTURE._meta.commit.slice(0, 7)})`);
