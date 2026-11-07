'use strict';
/* Wall areas with slopes — the G1 wall-side port on top of the strict
 * report1 engine:
 *   gross = W*H - SUM(dW*dH/2)   (one triangle per sloping top segment)
 * checked against the verified polygon area, never silently replacing it.
 * Reference: gable wall 4 m span, eaves 1.6 m, ridge 2.5 m -> 8.200000 m2.
 */
const assert = require('assert');
const R = require('../scripts/lib/ceiling-reconstruct');
const { buildReport } = require('../scripts/lib/quantities');

const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const pts = (a) => a.map(([x, y, z = 0]) => ({ x, y, z }));
const wall = (id, dims, corners, transform = I) => ({
  identifier: id, kind: 'wall', story: 0,
  dimensions: { x: dims[0], y: dims[1], z: dims[2] },
  polygonCorners: pts(corners), transform,
});
const GABLE = [[-2, 0], [2, 0], [2, 1.6], [0, 2.5], [-2, 1.6]];
const SHED = [[0, 0], [4, 0], [4, 2.5], [0, 1.6]];
const FLAT = [[-2, -1.25], [2, -1.25], [2, 1.25], [-2, 1.25]];

let checks = 0;
const check = (f) => { f(); checks++; };
const near = (a, b, tol = 1e-4) => Math.abs(a - b) <= tol;
const report = (surfaces) => buildReport({ kind: 'raw', surfaces, objects: [], rooms: null }, {});
const el = (r, id) => r.elements.find((e) => e.identifier === id);

// 1 ------------------------------------------- gable from the polygon: 8.2000
const rg = report([wall('gable', [4, 2.5, 0.2], GABLE)]);
const g = el(rg, 'gable');
check(() => assert(near(g.grossAreaM2.value, 8.2), `gable ${g.grossAreaM2.value}`));
check(() => assert.strictEqual(g.grossAreaM2.coverage, 'computed'));
check(() => assert(near(g.slopeCut.cutArea, 1.8, 1e-9)));
check(() => assert(near(g.slopeCut.ridgeHeight, 2.5, 1e-9)));
check(() => assert(near(g.slopeCut.kneeHeight, 1.6, 1e-9)));
check(() => assert(near(g.slopeCut.flatGrossArea, 10, 1e-9)));
check(() => assert(near(g.slopeCut.correctedGrossArea, 8.2, 1e-9)));
check(() => assert.strictEqual(g.slopeCut.triangles.length, 2)); // symmetric two-sided gable
check(() => assert.strictEqual(g.slopeCut.status, 'computed'));
check(() => assert(/W\*H/.test(g.slopeCut.note)));

// 2 ------------------------- gable through slopeCut from dimensions 4 x 2.5
const sc = R.slopeCutTriangles(wall('gable', [4, 2.5, 0.2], GABLE));
check(() => assert(near(sc.cutArea, 1.8, 1e-9)));
check(() => assert(near(sc.W * sc.H - sc.cutArea, 8.2, 1e-9)));
check(() => assert(near(sc.H, 2.5, 1e-9) && near(sc.W, 4, 1e-9)));

// 3 -------------------------------------------------------- shed wall slope
const rs = report([wall('shed', [4, 2.5, 0.2], SHED)]);
const sh = el(rs, 'shed');
check(() => assert(near(sh.grossAreaM2.value, 8.2), `shed ${sh.grossAreaM2.value}`));
check(() => assert.strictEqual(sh.slopeCut.triangles.length, 1));
check(() => assert(near(sh.slopeCut.cutArea, 1.8, 1e-9)));
check(() => assert(near(sh.slopeCut.correctedGrossArea, 8.2, 1e-9)));

// 4 ------------------------------------- flat wall stays W * H, no slope cut
const rf = report([wall('flat', [4, 2.5, 0.2], FLAT)]);
const fl = el(rf, 'flat');
check(() => assert(near(fl.grossAreaM2.value, 10, 1e-9)));
check(() => assert.strictEqual(fl.slopeCut.cutArea, 0));
check(() => assert.strictEqual(fl.slopeCut.slopeCount, 0));
check(() => assert.strictEqual(fl.slopeCut.status, 'computed'));
check(() => assert.strictEqual(fl.slopeCut.ridgeHeight, 2.5));

// dimension-only wall (no polygonCorners): rectangle, no slope evidence
const rDim = report([{ identifier: 'dim', kind: 'wall', story: 0, dimensions: { x: 4, y: 2.5, z: 0 }, polygonCorners: [], transform: I }]);
const dm = el(rDim, 'dim');
check(() => assert(near(dm.grossAreaM2.value, 10, 1e-9)));
check(() => assert.strictEqual(dm.slopeCut.status, 'unavailable'));
check(() => assert.strictEqual(dm.slopeCut.cutArea, null));

// 5 ------------------------ net of a sloped wall = corrected gross - openings
// door 1.0 x 1.6 m, fully inside the gable face (z = 0 -> coplanar)
const doorT = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1.0, 0, 1];
const door = { identifier: 'd1', kind: 'door', story: 0, parentIdentifier: 'gable', dimensions: { x: 1.0, y: 1.6, z: 0 }, polygonCorners: pts([[-0.5, -0.8], [0.5, -0.8], [0.5, 0.8], [-0.5, 0.8]]), transform: doorT };
const rn = report([wall('gable', [4, 2.5, 0.2], GABLE), door]);
const gn = el(rn, 'gable');
check(() => assert(near(gn.grossAreaM2.value, 8.2), String(gn.grossAreaM2.value)));
check(() => assert(near(gn.netAreaM2.value, 6.6), `net ${gn.netAreaM2.value}`)); // NOT 10 - 1.6 = 8.4
check(() => assert.strictEqual(gn.netAreaM2.coverage, 'computed'));

// 6 --------------------------- invalid polygon keeps the strict refusal: null
const nonPlanar = wall('bent', [4, 2.5, 0.2], [[-2, 0, 0], [2, 0, 0], [2, 2.5, 0.4], [-2, 2.5, 0]]);
const rb = report([nonPlanar]);
const bent = el(rb, 'bent');
check(() => assert.strictEqual(bent.grossAreaM2.value, null));
check(() => assert(/nonplanar/.test(bent.grossAreaM2.reason)));
const selfCross = wall('cross', [4, 2.5, 0.2], [[-2, 0, 0], [2, 2.5, 0], [2, 0, 0], [-2, 2.5, 0]]);
check(() => assert.strictEqual(el(report([selfCross]), 'cross').grossAreaM2.value, null));

// 7 ---------------------------------- detectSlopedWalls from RAW local corners
const detected = R.detectSlopedWalls([wall('gable', [4, 2.5, 0.2], GABLE), wall('flat', [4, 2.5, 0.2], FLAT), { identifier: 'x', kind: 'floor', polygonCorners: pts(FLAT) }]);
check(() => assert.strictEqual(detected.length, 1));
check(() => assert.strictEqual(detected[0].identifier, 'gable'));
check(() => assert(near(detected[0].ridgeHeightM, 2.5) && near(detected[0].kneeHeightM, 1.6)));
check(() => assert.strictEqual(detected[0].source, 'polygonCorners'));

// 8 ------------------------------ slopeCut surfaces in report.json + CSV safe
check(() => assert(gn.slopeCut && typeof gn.slopeCut.correctedGrossArea === 'number'));
check(() => assert(JSON.stringify(rn).includes('"slopeCut"')));

console.log(`wall-slopes: ${checks} checks passed`);
