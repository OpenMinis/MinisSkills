'use strict';
/**
 * tests/test_authored_ceiling.js — unit tests for scripts/lib/authored-ceiling.js
 * (SPEC section 5: ceiling as an authored 3D surface, G-5).
 * Independent expectations: the numbers are derived from the analytic surface
 * area (plan area x slope factor), never read back out of the module.
 */
const assert = require('assert');
const AC = require('../scripts/lib/authored-ceiling');

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
const TOL = 1e-9;
const near = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} != ${b} (tol ${tol})`);

// 4 x 5 m plan tilted 0.60 m over 5 m: area = 20 * sqrt(1 + 0.12^2)
const POLY = [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 5 }, { x: 0, y: 5 }];
const ELEV = [2.0, 2.0, 2.6, 2.6];
const GROSS = 20 * Math.sqrt(1 + 0.12 * 0.12);
const HOLE = [{ polygon: [{ x: 1, y: 1 }, { x: 2, y: 1 }, { x: 2, y: 2 }, { x: 1, y: 2 }] }];

check('planArea of the 4 x 5 plan', () => near(AC.planArea(POLY), 20, TOL));
check('newell area of the tilted loop', () => near(AC.newellArea3D([[0, 0, 2], [4, 0, 2], [4, 5, 2.6], [0, 5, 2.6]]), GROSS, TOL));
check('newell rejects a degenerate loop', () => assert.strictEqual(AC.newellArea3D([[0, 0, 0], [0, 0, 0], [0, 0, 0]]), null));

const flat = AC.authoredCeiling({ polygon: POLY, elevations: [2.5, 2.5, 2.5, 2.5] });
check('flat authored ceiling equals the plan area', () => { near(flat.areaM2, 20, TOL); assert.strictEqual(flat.slopeFactor, 1); });

const tilted = AC.authoredCeiling({ polygon: POLY, elevations: ELEV, holes: HOLE });
check('tilted authored ceiling gross', () => near(tilted.areaM2, GROSS, TOL));
check('hole scaled by ceilingArea/floorArea', () => near(tilted.netAreaM2, GROSS - 1 * (GROSS / 20), TOL));
check('measure shape is {value, coverage, reason}', () => {
  assert.strictEqual(tilted.coverage, 'computed');
  assert.strictEqual(tilted.reason, null);
  assert.strictEqual(tilted.value, tilted.netAreaM2);
  assert.strictEqual(tilted.status, 'computed');
});
check('holes aimed at the floor are not ceiling holes', () => {
  const r = AC.authoredCeiling({ polygon: POLY, elevations: ELEV, holes: [{ polygon: HOLE[0].polygon, target: 'floor' }] });
  near(r.netAreaM2, GROSS, TOL);
});
check('[x,y] plan points and a repeated closing vertex are accepted', () => {
  const r = AC.authoredCeiling({ polygon: [[0, 0], [4, 0], [4, 5], [0, 5], [0, 0]], elevations: ELEV });
  near(r.areaM2, GROSS, TOL);
});

// --------------------------------------------------------------- refusals
const refuses = (name, input, pattern) => check(name, () => {
  const r = AC.authoredCeiling(input);
  assert.strictEqual(r.value, null, 'value must be null');
  assert.strictEqual(r.status, 'unavailable');
  assert.ok(typeof r.reason === 'string' && pattern.test(r.reason), `reason was "${r.reason}"`);
});
refuses('no polygon -> reason', { elevations: ELEV }, /polygon/);
refuses('degenerate polygon -> reason', { polygon: [{ x: 0, y: 0 }, { x: 1, y: 0 }], elevations: [2, 2] }, /polygon/);
refuses('missing elevations -> reason (no invented floor area)', { polygon: POLY }, /elevations missing/);
refuses('elevation count mismatch -> reason', { polygon: POLY, elevations: [2, 2, 2] }, /count/);
refuses('non-finite elevation -> reason', { polygon: POLY, elevations: [2, 2, null, 2] }, /non-finite/);
refuses('non-planar surface -> reason', { polygon: POLY, elevations: [2, 2, 2.6, 2.7] }, /not planar/);
refuses('invalid hole polygon -> reason', { polygon: POLY, elevations: ELEV, holes: [{ polygon: [[0, 0], [1, 1]] }] }, /hole/);
refuses('zero plan floor area -> reason', { polygon: [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }], elevations: [2, 2, 2] }, /degenerate|floor area/);

check('no input at all is a refusal, not a throw', () => assert.strictEqual(AC.authoredCeiling().value, null));
check('input object is not mutated', () => {
  const input = { polygon: POLY.map((p) => ({ ...p })), elevations: ELEV.slice(), holes: HOLE };
  const before = JSON.stringify(input);
  AC.authoredCeiling(input);
  assert.strictEqual(JSON.stringify(input), before);
});

console.log(`authored-ceiling: ${checks} checks passed`);
