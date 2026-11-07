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
function fixed(id, what, expected, actual, verdict, note) {
  addRow(id, what, expected, actual, verdict, note);
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
  () => gableElement.grossAreaM2.value,
  `quantities.buildReport element grossAreaM2 (status ${gableElement.grossAreaM2.coverage})`);

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
pending('G-5', 'authored ceiling, 4 vertices 2.0-2.6 m: area per vertex elevations, holes scaled by ceilingArea/floorArea', 'rule',
  'no authored-ceiling model in the kernel: PlanEditorModel.ceilingElevations (per-vertex authored heights + hole scaling) is not ported. ceilings.js/ceiling-reconstruct.js only return the Newell area of a flat-or-tilted explicit ceiling polygon; hole scaling does not exist, so no golden number can be produced.');

// --------------------------------------------------------------- G-6 / G-7
pending('G-6', '1.00 x 1.00 m room, 0.15 m walls, reference edges: interior m2', 1.0,
  'interiorArea.ts interiorRoomArea (wall-footprint offset from reference edges) is not ported: scripts/lib has no interior/clear-area function. quantities.js polygonAreaM2 is the raw room polygon (reference/centreline), so 1.0000 m2 here would be a coincidence of fixture choice, not the golden algorithm.');
pending('G-7', 'same walls, no reference edges: centreline m2', 1.44,
  'same gap as G-6: no interior-vs-centreline mode exists in the kernel, so the 1.4400 m2 centreline rule cannot be exercised.');

// ------------------------------------------------------------------- G-8
std_room: {
  const room = { identifier: 'room-a', story: 0, area: 24, vertices: [{ x: 0, z: 0 }, { x: 6, z: 0 }, { x: 6, z: 4 }, { x: 0, z: 4 }] };
  // wall centreline laid exactly on the room's z=0 boundary, no source room link
  const boundary = { identifier: 'w-boundary', kind: 'wall', story: 0, dimensions: { x: 6, y: 2.5, z: 0.15 }, transform: at(3, 0) };
  const cap = { kind: 'optimized', surfaces: [boundary], objects: [], rooms: [room] };
  const element = buildReport(cap, {}).elements[0];
  const members = element.roomMemberships.filter((m) => m.roomIdentifier === 'room-a');
  fixed('G-8', 'wall on a room boundary: member of that room', '1 member', `${members.length} member`,
    members.length === 1 ? 'PASS' : 'FAIL',
    `method: ${members[0] ? members[0].method : 'n/a'}; engine boundary tolerance ${buildReport(cap, {}).conventions.roomBoundaryToleranceM} m`);

  // the SPEC asks for a 0.25 m tolerance; the kernel advertises 0.02 m
  const outside = { ...boundary, transform: at(3, -0.25) };
  const outsideMembers = buildReport({ kind: 'optimized', surfaces: [outside], objects: [], rooms: [room] }, {}).elements[0].roomMemberships.length;
  pending('G-8b', 'room membership at tolerance 0.25 m', '1 member', outsideMembers === 1
    ? 'membership found, but by the 0.02 m rule'
    : `a wall centreline 0.25 m outside the room boundary is NOT a member (${outsideMembers}); the kernel uses conventions.roomBoundaryToleranceM = 0.02 m, SPEC section 7 asks for 0.25 m -> contradiction C-4`);
}

// --------------------------------------------------------------- G-9 / G-10
pending('G-9', 'ArchiPlan fixture: living 10.9725 m2, net walls 35 - 1.89 m2', '10.9725 / 33.11',
  'ArchiPlan fixture not ported yet: planStatistics.ts (gross/net per level, living/gross, roomsWithoutArea) has no equivalent in scripts/lib and no fixture JSON for it exists in the package.');
pending('G-10', 'handoff fixture: quantity keys present, gaps[] for missing areas', 'keys + gaps[]',
  'handoff.ts not ported: scripts/lib has no handoff emitter, no quantity-key vocabulary and no gaps[] structure, so there is nothing to compare.');

// ------------------------------------------------------------------ G-11
pending('G-11', 'openings 1 m2 and 4 m2, threshold 3 m2: paint 10 / 1 m2', '10 / 1',
  'no wallPaintArea in the kernel: paint area with the free-opening threshold (3 m2) is not implemented anywhere in scripts/lib; SPEC section 5 names geometry.js wallPaintArea, which was not ported.');

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
  auxRow('A-4', 'G-1 gross status is computed (not estimated)', gableElement.grossAreaM2.coverage === 'computed', `coverage=${gableElement.grossAreaM2.coverage}`);
  auxRow('A-5', 'G-2 slope cut reported, not silently folded away', gableElement.slopeCut.status === 'computed' && Math.abs(gableElement.slopeCut.flatGrossArea - 10) <= TOL);
  auxRow('A-6', 'fixture trap: dropping the lower vertices changes the gable gross (1.8 vs 8.2)', (() => {
    const noBottom = wall('nob', [4, 2.5, 0.2], [[2, 1.6], [0, 2.5], [-2, 1.6]], at(0, 0));
    const el = buildReport(raw([noBottom]), {}).elements[0];
    // H is then maxY-minY = 0.9 instead of the wall height 2.5, so W*H-1.8 = 1.8
    noBottomGross = el.grossAreaM2.value;
    return Math.abs(el.grossAreaM2.value - 8.2) > TOL;
  })(), 'gross without bottom vertices = ' + String(noBottomGross) + ' (wrong, which is why the fixtures keep them)');
  auxRow('A-7', 'G-3 ceiling is not silently taken from dimensions.y', Math.abs(gableCeiling.heightMin - 1.6) <= TOL && Math.abs(gableCeiling.heightMax - 2.5) <= TOL, `h ${gableCeiling.heightMin}-${gableCeiling.heightMax}`);
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
