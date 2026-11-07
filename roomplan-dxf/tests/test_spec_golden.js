'use strict';
/**
 * tests/test_spec_golden.js — the executable half of SPEC.md section 7.
 *
 * Runs the REAL kernel (scripts/lib/*), never a copy of the maths, and compares
 * every golden number to 1e-4. A golden value the current code cannot reach is
 * reported as PENDING with the exact reason — never as a silent pass and never
 * as a FAIL that hides a real regression behind a missing feature.
 *
 * Fixtures are in metres. Wall polygons carry their LOWER vertices and a closed
 * outline ([-2,0],[2,0],[2,1.6],[0,2.5],[-2,1.6]); polygons without the bottom
 * vertices fall back to dimensions.y and produce a false negative.
 *
 * Exit code 1 only when a verdict is FAIL.
 */
const path = require('path');
const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const R = require(path.join(LIB, 'ceiling-reconstruct'));
const { buildReport } = require(path.join(LIB, 'quantities'));
const { buildPlanMeta } = require(path.join(LIB, 'plan-meta'));
const AC = require(path.join(LIB, 'authored-ceiling'));
const IA = require(path.join(LIB, 'interior-area'));
const PS = require(path.join(LIB, 'plan-statistics'));
const H = require(path.join(LIB, 'handoff'));
/** ArchiPlan fixtures (repo + commit recorded in each file's _meta). */
const STATS_FIXTURE = require(path.join(__dirname, 'fixtures', 'archiplan-plan-statistics.json'));
const HANDOFF_FIXTURE = require(path.join(__dirname, 'fixtures', 'archiplan-handoff.json'));
const statsCase = (id) => STATS_FIXTURE.cases.find((c) => c.id === id);
const handoffCase = (id) => HANDOFF_FIXTURE.cases.find((c) => c.id === id);

const TOL = 1e-4;
const rows = [];

function addRow(id, what, expected, actual, verdict, note) {
  rows.push({ id, what, expected, actual, verdict, note: note || '' });
}
function fmt(v) {
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'number') return v.toFixed(4);
  return String(v);
}
function numeric(id, what, expected, compute, note) {
  let actual;
  try {
    actual = compute();
  } catch (e) {
    addRow(id, what, fmt(expected), 'error', 'FAIL', e.message);
    return;
  }
  if (actual && typeof actual === 'object' && actual.pending) {
    addRow(id, what, fmt(expected), 'n/a', 'PENDING', actual.pending);
    return;
  }
  if (typeof actual !== 'number' || !Number.isFinite(actual)) {
    addRow(id, what, fmt(expected), fmt(actual), 'FAIL', 'not a finite number; nothing to compare');
    return;
  }
  const ok = Math.abs(actual - expected) <= TOL;
  addRow(id, what, fmt(expected), fmt(actual), ok ? 'PASS' : 'FAIL', note);
}
function pending(id, what, expected, reason) {
  addRow(id, what, fmt(expected), 'n/a', 'PENDING', reason);
}
function fixed(id, what, expected, actual, verdict, note, tol) {
  addRow(id, what, expected, actual, verdict, tol ? `${note} [tol ${tol}]` : note);
}
/** fixed() with the comparison done here, against an explicit tolerance.
 * `expected` and the value returned by `compute` may be a number or an array of
 * numbers (a golden rule with two outputs, e.g. gross / net). Every expectation
 * is derived in the TEST, never read back out of the kernel. */
function fixedNumbers(id, what, expected, compute, tol, note) {
  let actual;
  try {
    actual = compute();
  } catch (e) {
    fixed(id, what, String(expected), 'error', 'FAIL', e.message, tol);
    return;
  }
  const exp = Array.isArray(expected) ? expected : [expected];
  const act = actual === null || actual === undefined ? [] : Array.isArray(actual) ? actual : [actual];
  const ok = act.length === exp.length && exp.every((e, i) => typeof act[i] === 'number' && Number.isFinite(act[i]) && Math.abs(act[i] - e) <= tol);
  fixed(id, what, exp.map(fmt).join(' / '), act.length ? act.map(fmt).join(' / ') : 'null', ok ? 'PASS' : 'FAIL', note, tol);
}

// ------------------------------------------------------------------ fixtures
const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const at = (x, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, 0, z, 1];
const rot90 = (z) => [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, z, 1];
const pts = (arr) => arr.map(([x, y, z = 0]) => ({ x, y, z }));
const wall = (id, dims, corners, transform) => ({
  identifier: id, kind: 'wall', story: 0,
  dimensions: { x: dims[0], y: dims[1], z: dims[2] },
  polygonCorners: pts(corners), transform,
  wallThickness: dims[2],
});

// gable 4 m span: eaves 1.6 m, ridge 2.5 m in the middle (closed outline, bottom vertices included)
const GABLE = [[-2, 0], [2, 0], [2, 1.6], [0, 2.5], [-2, 1.6]];
// shed 4 m span: 1.6 m at x=0 rising to 2.5 m at x=4 (mono-pitch)
const SHED = [[0, 0], [4, 0], [4, 2.5], [0, 1.6]];
// knee wall 5 x 1.6 m, top edge flat at the eave height
const KNEE = [[-2.5, 0], [2.5, 0], [2.5, 1.6], [-2.5, 1.6]];

const gableWall = wall('gable', [4, 2.5, 0.2], GABLE, at(0, 0));
const shedWall = wall('shed', [4, 2.5, 0.2], SHED, at(0, 0));
const kneeWall = wall('knee', [5, 1.6, 0.2], KNEE, rot90(-2.5));
const raw = (surfaces) => ({ kind: 'raw', sourceSHA256: 'golden', surfaces, objects: [] });

// ------------------------------------------------------------- G-1 / G-2
const gableReport = buildReport(raw([gableWall]), {});
const gableElement = gableReport.elements[0];

numeric('G-1', 'gable wall 4 x 2.5, ridge 2.5 -> 1.6: gross m2', 8.2,
  () => gableElement.area.value,
  `quantities.buildReport element area (status ${gableElement.area.coverage})`);

numeric('G-2', 'same wall: slope cut triangle m2 removed', 1.8,
  () => gableElement.slopeCut.cutArea,
  `slopeCut ${gableElement.slopeCut.status}, ${gableElement.slopeCut.triangles.length} triangles`);

// ------------------------------------------------------------- G-3 / G-4
let gableCeiling = null;
let shedCeiling = null;
numeric('G-3', 'gable room 20 m2, eave 1.6, ridge 2.5, knee 5 m: ceiling m2', 21.9317,
  () => { gableCeiling = R.reconstructCeilingForRoom([gableWall, kneeWall], 20); return gableCeiling.ceilingArea; },
  'reconstructCeilingForRoom (ArchiDrawing G1 port)');

numeric('G-4', 'shed roof, same footprint: ceiling m2', 20.5,
  () => { shedCeiling = R.reconstructCeilingForRoom([shedWall, kneeWall], 20); return shedCeiling.ceilingArea; },
  'reconstructCeilingForRoom (shed section, both slopes away from one eave)');

// ------------------------------------------------------------------- G-5
// Authored ceiling: a plan polygon + one height per vertex (SPEC section 5,
// PlanEditorModel.ceilingElevations / ceilingArea / netCeilingAreaM2).
// The expectation is derived HERE, not read from the kernel: the surface is the
// strip 4 m wide (x) by 5 m deep (y) tilted only in y, rising 2.00 -> 2.60 m
// over 5 m, so its area is 4 * sqrt(5^2 + 0.6^2); a 1 m2 plan hole is scaled by
// the same slope factor ceilingArea/floorArea.
const CEIL_POLY = [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 5 }, { x: 0, y: 5 }];
const CEIL_ELEV = [2.0, 2.0, 2.6, 2.6];
const CEIL_FLOOR = 20; // 4 x 5 plan
const CEIL_GROSS = 4 * Math.sqrt(5 * 5 + 0.6 * 0.6); // 20.1435
const CEIL_NET = CEIL_GROSS - 1 * (CEIL_GROSS / CEIL_FLOOR); // 19.1363
const CEIL_HOLE = [{ polygon: [{ x: 1, y: 1 }, { x: 2, y: 1 }, { x: 2, y: 2 }, { x: 1, y: 2 }] }];
let authoredCeiling = null;
fixedNumbers('G-5', 'authored ceiling 4 x 5 m, heights 2.00/2.00/2.60/2.60: gross / net with a 1 m2 hole', [CEIL_GROSS, CEIL_NET],
  () => {
    authoredCeiling = AC.authoredCeiling({ polygon: CEIL_POLY, elevations: CEIL_ELEV, holes: CEIL_HOLE });
    return [authoredCeiling.areaM2, authoredCeiling.netAreaM2];
  }, 1e-3,
  `authored-ceiling.authoredCeiling Newell loop; slopeFactor ${(CEIL_GROSS / CEIL_FLOOR).toFixed(6)}; SPEC section 7 tolerance widened from 1e-4 to 1e-3 as instructed for G-5`);

// --------------------------------------------------------------- G-6 / G-7
// Interior floor area excluding the union of wall footprints (SPEC section 5,
// ArchiPlan interiorArea.ts interiorRoomArea scanline integration).
// One physical plan, two ways of writing it down:
//   reference edges: the 1.00 x 1.00 m ring IS the room's inner face and the
//                    0.20 m wall body lies outside it -> clear area 1.0000 m2.
//   centreline:      the wall path runs through the middle of the body, so the
//                    same building is the 1.00 + 0.20 = 1.20 m square -> the
//                    clear area is still 1.0000 m2, the centreline polygon is
//                    1.20^2 = 1.4400 m2 (the SPEC number).
const IA_W = 0.20;
const sq = (size) => [{ x: 0, y: 0 }, { x: size, y: 0 }, { x: size, y: size }, { x: 0, y: size }];
const rectWalls = (size, thickness) => [
  { start: { x: 0, y: 0 }, end: { x: size, y: 0 }, thickness },
  { start: { x: size, y: 0 }, end: { x: size, y: size }, thickness },
  { start: { x: size, y: size }, end: { x: 0, y: size }, thickness },
  { start: { x: 0, y: size }, end: { x: 0, y: 0 }, thickness },
];
const RING_REF = sq(1.0); // inner face, walls on the outside
const RING_CL = sq(1.0 + IA_W); // centreline of the same 0.20 m walls
const IA_REF_WALLS = rectWalls(1.0, IA_W);
const IA_CL_WALLS = rectWalls(1.0 + IA_W, IA_W);
let g6Ref = null, g6Cl = null;
fixedNumbers('G-6', '1.00 x 1.00 m room, 0.20 m walls written on the inner face (reference edges): interior m2', 1.0,
  () => { g6Ref = IA.interiorRoomArea(RING_REF, [], IA_REF_WALLS, { wallConvention: 'reference-edges' }); return g6Ref; }, TOL,
  'interior-area.interiorRoomArea scanline bands; wall footprints offset outward by thickness/2 (SPEC 1.0000 m2 reached)');
// 0.20 m walls put the centreline polygon at 1.20 m -> 1.4400 m2, the SPEC value.
const CL_EXPECTED = Math.pow(1.0 + IA_W, 2); // 1.4400
fixedNumbers('G-7', 'same building on wall centrelines (1.20 m polygon): centreline m2', CL_EXPECTED,
  () => { g6Cl = IA.centerlineArea(RING_CL, []); return g6Cl; }, TOL,
  'interior-area.centerlineArea; 0.20 m walls -> 1.20 m centreline polygon -> 1.4400 m2');

// ------------------------------------------------------------------- G-8
std_room: {
  const room = { identifier: 'room-a', story: 0, area: 24, vertices: [{ x: 0, z: 0 }, { x: 6, z: 0 }, { x: 6, z: 4 }, { x: 0, z: 4 }] };
  // wall centreline laid exactly on the room's z=0 boundary, no source room link
  const boundary = { identifier: 'w-boundary', kind: 'wall', story: 0, dimensions: { x: 6, y: 2.5, z: 0.15 }, transform: at(3, 0) };
  const cap = { kind: 'optimized', surfaces: [boundary], objects: [], rooms: [room] };
  const element = buildReport(cap, {}).elements[0];
  const members = element.roomRefs.filter((m) => m.roomIdentifier === 'room-a');
  fixed('G-8', 'wall on a room boundary: member of that room', '1 member', `${members.length} member`,
    members.length === 1 ? 'PASS' : 'FAIL',
    `method: ${members[0] ? members[0].method : 'n/a'}; engine boundary tolerance ${buildReport(cap, {}).conventions.roomBoundaryToleranceM} m`);

  // G-8b: DECIDED 2026-11-07 — the kernel tolerance stays 0.02 m. The 0.25 m
  // value inherited from report-model.js is REJECTED (it would make a wall
  // 25 cm outside a room a member of that room, which is a wrong takeoff, not a
  // convenience). This row now asserts the accepted rule instead of pending on
  // the rejected one; SPEC section 7 G-8b was corrected to 0.02 m.
  const outside = { ...boundary, transform: at(3, -0.25) };
  const outsideReport = buildReport({ kind: 'optimized', surfaces: [outside], objects: [], rooms: [room] }, {});
  const outsideMembers = outsideReport.elements[0].roomRefs.length;
  const tol = outsideReport.conventions.roomBoundaryToleranceM;
  fixed('G-8b', 'wall centreline 0.25 m outside the boundary: NOT a member (tolerance 0.02 m)', '0 members, tol 0.02',
    `${outsideMembers} members, tol ${tol}`, outsideMembers === 0 && tol === 0.02 ? 'PASS' : 'FAIL',
    'decision 2026-11-07: 0.02 m is the rule; report-model.js tolerated 0.25 m and that value is not adopted (SPEC section 7 G-8b corrected)');
}

// --------------------------------------------------------------- G-9 / G-10
// G-9: the ArchiPlan studio fixture (4 x 3 m centreline, 0.15 m walls, 2.50 m
// tall, one 0.90 x 2.10 m door) through the ported planStatistics. Expected
// numbers are tests/planStatistics.test.ts assertions, carried in the fixture.
{
  const fixture = statsCase('studio-4x3-interior-face');
  const stats = PS.planStatistics(fixture.input);
  fixedNumbers('G-9', 'ArchiPlan fixture: living 10.9725 m2, net walls 35 - 1.89 m2', [10.9725, 35 - 1.89],
    () => (stats.ok ? [stats.statistics.totals.livingArea, stats.statistics.totals.wallAreaNet] : [null, null]), TOL,
    `plan-statistics.planStatistics on fixture case '${fixture.id}' (ArchiPlan ${STATS_FIXTURE._meta.commit.slice(0, 7)}); ` +
    `gross ${stats.statistics ? stats.statistics.totals.grossArea : 'n/a'} = living + 14 x 0.15 / 2, wallAreaGross ${stats.statistics ? stats.statistics.totals.wallAreaGross : 'n/a'}, ` +
    `roomsWithoutArea ${stats.statistics ? stats.statistics.totals.roomsWithoutArea : 'n/a'}`);
}

// G-10: the ArchiPlan native package through the ported handoff: the contracted
// quantity keys, per-room boundary figures and gaps[] for what is missing.
{
  const handCase = handoffCase('native-project-package');
  const hand = H.handoff(handCase.input);
  const KEYS = ['floorArea', 'ceilingArea', 'wallAreaNetRoom', 'wallRunRoom', 'livingAreaLevel', 'wallAreaNetLevel', 'wallAreaGrossLevel', 'wallRunLevel', 'doors', 'windows'];
  const presentKeys = hand.ok ? [...new Set(hand.scope.quantities.map((q) => q.key))].sort() : [];
  const keysOk = JSON.stringify(presentKeys) === JSON.stringify([...KEYS].sort());
  // a room the source cannot measure must produce a gap, not a zero quantity
  const gapProbe = H.handoff({
    walls: [{ id: 'w', start: { x: 0, y: 0 }, end: { x: 4, y: 0 }, height: 2.5, thickness: 0.15, level: 0 }],
    openings: [], furniture: [], levels: [], rooms: [{ id: 'r', name: 'Label only', level: 0 }],
  });
  const gapsOk = gapProbe.ok && gapProbe.scope.gaps.some((g) => /has no measured floor area/.test(g)) &&
    !gapProbe.scope.quantities.some((q) => q.room === 'Label only');
  const level0 = hand.ok ? hand.scope.levels.find((l) => l.index === 0) : null;
  fixed('G-10', 'handoff fixture: quantity keys present, gaps[] for missing areas', '10 keys + gaps[]',
    `${presentKeys.length} keys${keysOk ? ' exact' : ''}, gaps ${gapsOk ? 'reported' : 'missing'}`,
    keysOk && gapsOk ? 'PASS' : 'FAIL',
    `handoff.handoff on fixture case '${handCase.id}' (ArchiPlan ${HANDOFF_FIXTURE._meta.commit.slice(0, 7)}); ` +
    `level 0 net ${level0 && level0.wallAreaNet ? level0.wallAreaNet.value : 'n/a'} m2, run ${level0 && level0.wallRun ? level0.wallRun.value : 'n/a'} m; ` +
    'ceilings come from reconstructCeilingForRoom with a method');
}

// ------------------------------------------------------------------ G-11
// Paint area with the trade free-opening threshold (SPEC section 5, geometry.js
// wallPaintArea + PAINT_FREE_OPENING_M2 = 3). Two 10 m2 walls: one with a 1 m2
// opening, one with a 4 m2 opening. An opening up to 3 m2 deducts nothing, so
// wall A paints 10 m2; above the threshold only the excess comes off, so wall B
// deducts 1 m2 and paints 9 m2. Net stays geometric (9 and 6): paint is a
// SEPARATE field and never replaces netArea.
const paintWall = (id, originX) => ({ identifier: id, kind: 'wall', story: 0, dimensions: { x: 4, y: 2.5, z: 0.2 }, transform: at(originX, 0) });
const paintOpening = (id, parent, width, height, originX) => ({ identifier: id, kind: 'window', story: 0, parentIdentifier: parent, dimensions: { x: width, y: height, z: 0 }, transform: at(originX, 0) });
const paintCapture = raw([paintWall('w-small', 0), paintOpening('o-1', 'w-small', 1, 1, 0), paintWall('w-large', 5), paintOpening('o-4', 'w-large', 2, 2, 5)]);
const paintReport = buildReport(paintCapture, {});
const paintWalls = paintReport.elements.filter((e) => e.kind === 'wall');
const paintA = paintWalls.find((e) => e.identifier === 'w-small');
const paintB = paintWalls.find((e) => e.identifier === 'w-large');
fixedNumbers('G-11', 'openings 1 m2 and 4 m2, threshold 3 m2: paint on wall A / excess deducted on wall B (m2)', [10, 1],
  () => [paintA.paintArea.value, paintA.area.value - paintB.paintArea.value], TOL,
  `quantities.buildReport paintArea, PAINT_FREE_OPENING_M2=${paintReport.conventions.paintFreeOpeningM2}; wall A paint 10.0000 (1 m2 opening free), wall B paint 9.0000 with 1.0000 deducted (4 - 3); net stays geometric ${paintA.netArea.value.toFixed(4)} / ${paintB.netArea.value.toFixed(4)}; totals.paintArea=${paintReport.totals.paintArea.value.toFixed(4)}`);

// ------------------------------------------------------------------ G-12
{
  // alignment 7.9724 deg means the sheet bearing OFFSET is +7.9724; project() maps
  // world (x,y,z) -> sheet (x,-z), so a rotation about +Y by -8 deg yields that offset.
  const a = (-7.9724 * Math.PI) / 180;
  const m = [Math.cos(a), 0, -Math.sin(a), 0, 0, 1, 0, 0, Math.sin(a), 0, Math.cos(a), 0, 0, 0, 0, 1];
  const model = {
    meta: { orientationDegrees: 193.7412, orientationSource: 'scan', orientationConfidence: 0.9 },
    architecturalAlignment: { matrix: m },
    originalFilename: 'golden.json',
  };
  const legacy = buildPlanMeta(model, { project: 'G-12', northFlip: false }).north;
  const modern = buildPlanMeta(model, { project: 'G-12' }).north;
  const offset = modern.alignmentBearingOffsetDegrees;
  const legacyBearing = legacy.degreesClockwiseFromDrawingUp;
  const defaultBearing = modern.degreesClockwiseFromDrawingUp;
  // decided 2026-11-07 on site: the default (flip) formula points north.
  fixed('G-12', 'heading 193.7412 deg, alignment 7.9724 deg: default sheet bearing', 174.2312,
    defaultBearing, Math.abs(defaultBearing - 174.2312) <= TOL ? 'PASS' : 'FAIL',
    `alignmentBearingOffset ${offset}; legacy formula gives ${legacyBearing.toFixed(4)} (180 deg away, kept only as --no-north-flip)`);
}

// ------------------------------------------------- behaviour behind the numbers
const aux = [];
let noBottomGross = null;
const auxRow = (id, what, ok, detail) => aux.push({ id, what, verdict: ok ? 'PASS' : 'FAIL', detail: detail || '' });
try {
  auxRow('A-1', 'G-3 method is "knee"', gableCeiling && gableCeiling.method === 'knee', `method=${gableCeiling && gableCeiling.method} status=${gableCeiling && gableCeiling.status}`);
  auxRow('A-2', 'G-3/G-4 ceiling >= floor footprint (arithmetic guard)', gableCeiling.ceilingArea > 20 && shedCeiling.ceilingArea > 20);
  auxRow('A-3', 'G-4 method is "knee"', shedCeiling && shedCeiling.method === 'knee', `method=${shedCeiling && shedCeiling.method}`);
  auxRow('A-4', 'G-1 gross status is computed (not estimated)', gableElement.area.status === 'computed', `coverage=${gableElement.area.coverage}`);
  auxRow('A-5', 'G-2 slope cut reported, not silently folded away', gableElement.slopeCut.status === 'computed' && Math.abs(gableElement.slopeCut.flatGrossArea - 10) <= TOL);
  auxRow('A-6', 'fixture trap: dropping the lower vertices changes the gable gross (1.8 vs 8.2)', (() => {
    const noBottom = wall('nob', [4, 2.5, 0.2], [[2, 1.6], [0, 2.5], [-2, 1.6]], at(0, 0));
    const el = buildReport(raw([noBottom]), {}).elements[0];
    // H is then maxY-minY = 0.9 instead of the wall height 2.5, so W*H-1.8 = 1.8
    noBottomGross = el.area.value;
    return Math.abs(el.area.value - 8.2) > TOL;
  })(), 'gross without bottom vertices = ' + String(noBottomGross) + ' (wrong, which is why the fixtures keep them)');
  auxRow('A-7', 'G-3 ceiling is not silently taken from dimensions.y', Math.abs(gableCeiling.heightMin - 1.6) <= TOL && Math.abs(gableCeiling.heightMax - 2.5) <= TOL, `h ${gableCeiling.heightMin}-${gableCeiling.heightMax}`);
  const g6ClInterior = IA.interiorRoomArea(RING_CL, [], IA_CL_WALLS, { wallConvention: 'centerline' });
  auxRow('A-8', 'G-6 also holds when the same plan is written on the centreline (ring 1.15 m)', Math.abs(g6ClInterior - 1.0) <= TOL && Math.abs(g6Ref - 1.0) <= TOL,
    `centreline fixture interiorRoomArea=${g6ClInterior}, reference-edge fixture=${g6Ref}, centreline polygon=${g6Cl}`);
  auxRow('A-9', 'G-5 refuses instead of guessing: no elevations -> null with a reason', (() => {
    const r = AC.authoredCeiling({ polygon: CEIL_POLY });
    return r.value === null && typeof r.reason === 'string' && r.reason.length > 0;
  })(), `reason="${AC.authoredCeiling({ polygon: CEIL_POLY }).reason}"`);
  auxRow('A-10', 'G-5 hole scaling uses ceilingArea/floorArea, not a bare plan-area deduction', (() => {
    const r = AC.authoredCeiling({ polygon: CEIL_POLY, elevations: CEIL_ELEV, holes: CEIL_HOLE });
    return Math.abs(r.netAreaM2 - (CEIL_GROSS - 1)) > 1e-3 && Math.abs(r.slopeFactor - CEIL_GROSS / CEIL_FLOOR) <= 1e-12;
  })(), `net=${authoredCeiling && authoredCeiling.netAreaM2.toFixed(4)} vs naive gross-1=${(CEIL_GROSS - 1).toFixed(4)}`);
  auxRow('A-11', 'G-11 threshold edges: an opening exactly at 3 m2 and two 2 m2 openings deduct nothing', (() => {
    const cap = raw([
      paintWall('w-exact', 0), paintOpening('o-3', 'w-exact', 3, 1, 0),
      paintWall('w-pair', 5), paintOpening('p-1', 'w-pair', 2, 1, 5), paintOpening('p-2', 'w-pair', 2, 1, 5),
    ]);
    const walls = buildReport(cap, {}).elements.filter((e) => e.kind === 'wall');
    const exact = walls.find((e) => e.identifier === 'w-exact').paintArea.value;
    const pair = walls.find((e) => e.identifier === 'w-pair').paintArea.value;
    return Math.abs(exact - 10) <= TOL && Math.abs(pair - 10) <= TOL;
  })(), `3 m2 opening -> paint 10, two 2 m2 openings -> paint 10 (per-opening rule, not a summed 4 m2)`);
  auxRow('A-12', 'G-11 paint never replaces net: net keeps the full geometric deduction', Math.abs(paintA.netArea.value - 9) <= TOL && Math.abs(paintB.netArea.value - 6) <= TOL && Math.abs(paintA.paintArea.value - 10) <= TOL,
    `net ${paintA.netArea.value}/${paintB.netArea.value} paint ${paintA.paintArea.value}/${paintB.paintArea.value}; totals net ${paintReport.totals.wallAreaNet.value} paint ${paintReport.totals.paintArea.value}`);
  auxRow('A-14', 'G-8b decision: 0.02 m accepted, 0.25 m REJECTED, and the boundary is exactly at 0.02 m', (() => {
    const room2 = { identifier: 'room-b', story: 0, vertices: [{ x: 0, z: 0 }, { x: 6, z: 0 }, { x: 6, z: 4 }, { x: 0, z: 4 }] };
    const wallAt = (z) => ({ identifier: 'w-t', kind: 'wall', story: 0, dimensions: { x: 6, y: 2.5, z: 0.15 }, transform: at(3, z) });
    const members = (z) => buildReport({ kind: 'optimized', surfaces: [wallAt(z)], objects: [], rooms: [room2] }, {}).elements[0].roomRefs.length;
    const inside = members(-0.02), justOutside = members(-0.03), farOutside = members(-0.25);
    return inside === 1 && justOutside === 0 && farOutside === 0;
  })(), 'inside 0.02 m -> member, 0.03 m -> not a member, 0.25 m -> not a member; the 0.25 m value from report-model.js is documented as NOT adopted (SPEC section 7 G-8b corrected to 0.02 m, no kernel change)');
  auxRow('A-13', 'D-1 evidence: 1.4400 m2 is the shoelace of a 1.20 m square, not of 1.00 m + 0.15 m walls', Math.abs(IA.centerlineArea(sq(1.2), []) - 1.44) <= TOL,
    `centerlineArea(1.20 m square)=${IA.centerlineArea(sq(1.2), [])}; 0.15 m walls give 1.15 m -> ${IA.centerlineArea(RING_CL, [])}`);
} catch (e) {
  auxRow('A-0', 'aux checks crashed', false, e.message);
}

// ------------------------------------------------------------------- output
const cols = [
  ['ID', 6, (r) => r.id],
  ['CASE', 54, (r) => r.what],
  ['EXPECTED', 12, (r) => r.expected],
  ['ACTUAL', 12, (r) => r.actual],
  ['VERDICT', 8, (r) => r.verdict],
];
const cell = (s, n) => {
  s = String(s);
  return (s.length > n ? s.slice(0, n - 1) + '…' : s).padEnd(n);
};
console.log('\n=== SPEC section 7 golden numbers (tolerance 1e-4) ===');
console.log(cols.map(([h, n]) => cell(h, n)).join('') + 'NOTE');
console.log(cols.map(([, n]) => cell('', n).replace(/ /g, '-')).join('') + '-'.repeat(40));
for (const r of rows) console.log(cols.map(([, n, f]) => cell(f(r), n)).join('') + r.note);

console.log('\n=== auxiliary behaviour checks ===');
for (const a of aux) console.log(`${cell(a.id, 6)}${cell(a.what, 66)}${cell(a.verdict, 8)}${a.detail}`);

const count = (v) => rows.filter((r) => r.verdict === v).length;
const auxFail = aux.filter((a) => a.verdict === 'FAIL').length;
console.log(`\nspec-golden: ${count('PASS')} PASS, ${count('PENDING')} PENDING, ${count('FAIL')} FAIL of ${rows.length} golden rows` +
  ` | aux ${aux.length - auxFail}/${aux.length} passed`);
if (count('FAIL') || auxFail) {
  console.error('\nFAIL: at least one golden number or behaviour check regressed.');
  process.exit(1);
}
