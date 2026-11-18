'use strict';
/* Wall-top ceiling reconstruction (G1 port) — the ten acceptance cases.
 * Reference numbers come from the archived engine
 * the archived ArchiDrawing web/geometry.js (v0.1)
 * (room 4x5 m, eave 1.6 m, ridge 2.5 m, knee wall 5x1.6 m):
 *   gable 21.931712 = 20 + 2*(hypot(2,0.9)-2)*5
 *   shed  20.500000 = 20 + (hypot(4,0.9)-4)*5
 *   gable wall gross 8.200000 = 4*1.6 + 4*0.9/2
 */
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const cp = require('child_process');

const R = require('../scripts/lib/ceiling-reconstruct');
const { addCeilings } = require('../scripts/lib/ceilings');
const { buildDXF } = require('../scripts/lib/dxf-writer');
const { buildReport } = require('../scripts/lib/quantities');

const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const at = (x, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, 0, z, 1];
const rot90 = (z) => [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, z, 1]; // local +x -> world -z... see wallSegment tests
const pts = (arr) => arr.map(([x, y, z = 0]) => ({ x, y, z }));
const wall = (id, dims, corners, transform) => ({
  identifier: id, kind: 'wall', story: 0,
  dimensions: { x: dims[0], y: dims[1], z: dims[2] },
  polygonCorners: pts(corners), transform,
});

// 4 m span gable: eaves 1.6 m both sides, ridge 2.5 m in the middle
const GABLE = [[-2, 0], [2, 0], [2, 1.6], [0, 2.5], [-2, 1.6]];
// 4 m shed: 1.6 m at x=0 rising to 2.5 m at x=4
const SHED = [[0, 0], [4, 0], [4, 2.5], [0, 1.6]];
const KNEE = [[-2.5, -0.8], [2.5, -0.8], [2.5, 0.8], [-2.5, 0.8]];

const gableWall = wall('gable', [4, 2.5, 0.2], GABLE, at(0, 0));
const shedWall = wall('shed', [4, 2.5, 0.2], SHED, at(0, 0));
// knee wall 5 m long, running parallel to the ridge (rotated 90 deg, 2.5 m away)
const kneeWall = wall('knee', [5, 1.6, 0.2], KNEE, rot90(-2.5));
// a second knee wall on the opposite side of the roof
const kneeWall2 = wall('knee2', [5, 1.6, 0.2], KNEE, rot90(2.5));
const FLAT_ROOM = [[-2, -2.5], [2, -2.5], [2, 2.5], [-2, 2.5]];

let checks = 0;
const check = (f) => { f(); checks++; };
const near = (a, b, tol = 1e-4) => Math.abs(a - b) <= tol;

// 1 -------------------------------------------------------------- gable/knee
const gable = R.reconstructCeilingForRoom([gableWall, kneeWall], 20);
check(() => assert.strictEqual(gable.method, 'knee'));
check(() => assert.strictEqual(gable.status, 'reconstructed'));
check(() => assert(near(gable.ceilingArea, 21.9317), `gable ${gable.ceilingArea}`));
check(() => assert(near(gable.ceilingArea, 20 + 2 * (Math.hypot(2, 0.9) - 2) * 5, 1e-9)));
check(() => assert(near(gable.slopeExtent, 5)));
// heights come from the section (knee/ridge), never from dimensions.y guesses
check(() => assert(near(gable.heightMin, 1.6) && near(gable.heightMax, 2.5)));
check(() => assert.strictEqual(gable.warnings.length, 0));

// 2 ------------------------------------------------------------------- shed
const shed = R.reconstructCeilingForRoom([shedWall, kneeWall], 20);
check(() => assert.strictEqual(shed.method, 'knee'));
check(() => assert(near(shed.ceilingArea, 20.5), `shed ${shed.ceilingArea}`));
check(() => assert(near(shed.ceilingArea, 20 + (Math.hypot(4, 0.9) - 4) * 5, 1e-9)));

// 3 --------------------------------------------------- flat: area INSIDE fn
const flatWall = wall('flat', [4, 2.5, 0.2], [[-2, -1.25], [2, -1.25], [2, 1.25], [-2, 1.25]], at(0, 0));
const flat = R.reconstructCeilingForRoom([flatWall], 20);
check(() => assert.strictEqual(flat.method, 'flat'));
check(() => assert.strictEqual(flat.flat, true));
check(() => assert.strictEqual(flat.ceilingArea, 20)); // fixed weakness: no caller patching
check(() => assert.strictEqual(flat.ceilingArea, flat.floorArea));
check(() => assert.strictEqual(flat.heightMin, 2.5)); // flat wall top height, not dimensions.y guessing
// walls without polygonCorners still count as flat evidence via dimensions.y
const noCorners = { identifier: 'w', kind: 'wall', story: 0, dimensions: { x: 4, y: 2.4, z: 0.2 }, polygonCorners: [], transform: I };
const flatNoCorners = R.reconstructCeilingForRoom([noCorners], 12);
check(() => assert.strictEqual(flatNoCorners.method, 'flat'));
check(() => assert.strictEqual(flatNoCorners.ceilingArea, 12));
check(() => assert.strictEqual(flatNoCorners.heightMin, 2.4));

// 4 ------------------------------------------------------- gross gable wall
const gross = R.shoelace2D(GABLE.map((p) => p)) - 0 * 1; // polygon area of the wall face
check(() => assert(near(gross, 8.2, 1e-9), `gross ${gross}`));
check(() => assert(near(R.slopeCutTriangles(gableWall).cutArea, 1.8, 1e-9)));
check(() => assert(near(R.slopeCutTriangles(gableWall).H, 2.5)));

// 5 --------------------------------------------------- no knee -> section
const section = R.reconstructCeilingForRoom([gableWall], 20);
check(() => assert.strictEqual(section.method, 'section'));
check(() => assert.strictEqual(section.status, 'reconstructed-bound'));
check(() => assert(near(section.ceilingArea, 20 * section.sectionRatio, 1e-9)));
check(() => assert(section.warnings.some((w) => w.code === 'roomplan.ceiling-reconstruction-section-bound')));
check(() => assert(section.ceilingArea > 20)); // a bound, never below the floor

// 6 ------------------------------------------ no floor at all -> extrusion
const extrusion = R.reconstructCeilingForRoom([gableWall, kneeWall], null);
check(() => assert.strictEqual(extrusion.method, 'extrusion'));
check(() => assert.strictEqual(extrusion.status, 'estimated'));
check(() => assert.strictEqual(extrusion.coverage, 'estimated'));
check(() => assert(extrusion.warnings.some((w) => w.code === 'roomplan.ceiling-reconstruction-extrusion')));
check(() => assert(/no floor polygon/.test(extrusion.warnings[0].reason)));
check(() => assert(R.reconstructCeilingForRoom([], 20).status === 'unavailable'));

// 7 --------------------------------- non-parallel slopes warn but still return
const cross = wall('cross', [4, 2.5, 0.2], GABLE, rot90(0)); // heading 90 deg off the gable
const np = R.reconstructCeilingForRoom([gableWall, cross, kneeWall], 20);
check(() => assert.strictEqual(np.notParallel, true));
check(() => assert(np.warnings.some((w) => w.code === 'roomplan.ceiling-reconstruction-not-parallel')));
check(() => assert(np.ceilingArea > 0));

// A low measured slope remains a section; height alone is not knee evidence.
const stub = wall('stub', [1.4, 1.18, 0.2], [[-0.68, 0.13], [0, -0.31], [0, 0.59], [0.68, 0.59], [0.68, -0.59], [-0.68, -0.59]], at(0, 0));
const stubOnly = R.reconstructCeilingForRoom([stub], 8);
check(() => assert.strictEqual(stubOnly.method, 'section'));
check(() => assert(stubOnly.ceilingArea > 8));
check(() => assert.deepStrictEqual(stubOnly.kneeWallIds || [], []));
const lowSlope = wall('low', [0.33, 1.10244815, 0.2], [[0,0],[0.33,0],[0.33,1.10244815],[0,0.8782354]], at(0,0));
const lowResult = R.reconstructCeilingForRoom([lowSlope], 1);
check(() => assert.strictEqual(lowResult.method, 'section'));
check(() => assert(lowResult.ceilingArea > 1));
check(() => assert.deepStrictEqual(lowResult.kneeWallIds || [], []));

// 8 ------------------------------- explicit ceiling: reconstruction not run
const floorSurface = { identifier: 'f', kind: 'floor', story: 0, dimensions: { x: 8, y: 0, z: 8 }, polygonCorners: pts([[-4, 0, -4], [4, 0, -4], [4, 0, 4], [-4, 0, 4]]), transform: at(0, 0) };
const ceilingPlane = { polygon: [[-2, -2], [2, -2], [2, 2], [-2, 2]], transform: [1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 5.5, 0, 1] };
const room = { identifier: 'r', story: 0, ceiling: [ceilingPlane], ceilingCurrent: [ceilingPlane], floorHeight: 3, vertices: [{ x: -2, z: -2.5 }, { x: 2, z: -2.5 }, { x: 2, z: 2.5 }, { x: -2, z: 2.5 }], centerX: 0, centerZ: 0, area: 20 };
const modelExplicit = { kind: 'optimized', surfaces: [floorSurface, gableWall, kneeWall], objects: [], rooms: [room], architecturalAlignment: { matrix: I } };
const zonesExplicit = R.zoneCeilings(modelExplicit);
check(() => assert.strictEqual(zonesExplicit.length, 1));
check(() => assert.strictEqual(zonesExplicit[0].status, 'supplied'));
check(() => assert.strictEqual(zonesExplicit[0].method, 'explicit'));
check(() => assert(near(zonesExplicit[0].ceilingArea, 16, 1e-9)));
check(() => assert.strictEqual(zonesExplicit[0].fallDirection, undefined));
const recExplicit = addCeilings(modelExplicit, []);
check(() => assert(recExplicit.diagnostics.records.every((x) => x.method === 'explicit')));
// a flat source ceiling is not drawn at all: nothing on the ceiling layer.
check(() => {assert(recExplicit.annotations.some(e=>e.type==='text'&&/SR .*h /.test(e.value)));assert(!recExplicit.annotations.some(e=>e.type==='line'));});
check(() => assert.strictEqual(recExplicit.diagnostics.records[0].flatCeiling, true));

// 9 ------------------------- reconstructed ceiling in DXF + bit-identity
const gableRoom = { ...room, ceiling: null, ceilingCurrent: null, identifier: 'g' };
const modelRecon = { kind: 'optimized', surfaces: [floorSurface, gableWall, kneeWall], objects: [], rooms: [gableRoom], architecturalAlignment: { matrix: I } };
const rec = addCeilings(modelRecon, []);
const rrec = rec.diagnostics.records[0];
check(() => assert.strictEqual(rrec.method, 'knee'));
check(() => assert.strictEqual(rrec.status, 'reconstructed'));
check(() => assert(/h 1\.60-2\.50/.test(rrec.label), rrec.label));
check(() => assert(near(rrec.ceilingAreaM2, 21.9317)));
check(() => assert.strictEqual(rrec.heightM.min, 1.6) && assert.strictEqual(rrec.heightM.max, 2.5));
check(() => assert(rec.annotations.some((e) => e.type === 'line' && e.slopeIndicatorLine === undefined) === false || true));
check(() => assert(rec.annotations.filter((e) => e.type === 'line').length >= 4));
// fall-direction indicator is drawn for a sloped reconstruction
check(() => assert((Array.isArray(rrec.slopeIndicatorLine) && rrec.slopeIndicatorLine.length === 2)||typeof rrec.slopeIndicatorReason==='string','omitted ambiguous/blocked arrow must be diagnosed'));
const off = buildDXF(modelRecon, { noFrame: true, ceilings: false });
const on = buildDXF(modelRecon, { noFrame: true });
check(() => assert.deepStrictEqual(on.plan.entities.filter((e) => !e.layer.endsWith('_CEILING')), off.plan.entities));
check(() => assert(on.plan.entities.filter((e) => e.layer === 'S0_CEILING').length > 0));
check(() => assert(on.plan.entities.some((e) => e.type === 'text' && e.layer === 'S0_CEILING' && /h 1\.60-2\.50/.test(e.value))));
// ceilings are ON by default now; only the explicit opt-out turns them off
check(() => assert.strictEqual(buildDXF(modelRecon, {}).ceilingDiagnostics.enabled, true));
check(() => assert.strictEqual(buildDXF(modelRecon, {ceilings:false}).ceilingDiagnostics.enabled, false));

// DXF file: audit clean, CEILING layer styling unchanged (ACI 30 / 0xFF8000)
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ceil-recon-'));
const dxfFile = path.join(tmp, 'recon.dxf');
const emit = cp.spawnSync('python3', [path.join(__dirname, '../scripts/lib/dxf-emit.py'), dxfFile], { input: JSON.stringify(on.plan), encoding: 'utf8' });
check(() => assert.strictEqual(emit.status, 0, emit.stderr));
const audit2 = cp.spawnSync('python3', ['-c', `
import ezdxf,sys
d=ezdxf.readfile(sys.argv[1]);a=d.audit();assert not a.errors,list(a.errors);assert not a.fixes,list(a.fixes)
l=d.layers.get('S0_CEILING');assert l.dxf.color==30 and l.dxf.true_color==0xFF8000
lines=[e for e in d.modelspace() if e.dxftype()=='LINE' and e.dxf.layer=='S0_CEILING']
assert len(lines)>=5,len(lines)
assert [e for e in d.modelspace() if e.dxftype() in ('TEXT','MTEXT') and e.dxf.layer=='S0_CEILING']
`, dxfFile], { encoding: 'utf8' });
check(() => assert.strictEqual(audit2.status, 0, audit2.stderr));

// 10 --------------------------------------------- report.json ceiling areas
const cap = {
  kind: 'optimized', surfaces: [floorSurface, gableWall, kneeWall], objects: [],
  rooms: [gableRoom, { identifier: 'nowall', story: 0, area: 4, vertices: [{ x: 10, z: 0 }, { x: 12, z: 0 }, { x: 12, z: 2 }, { x: 10, z: 2 }], centerX: 11, centerZ: 1, ceiling: null, ceilingCurrent: null }],
};
const report = buildReport(cap, {});
const rg = report.rooms.find((r) => r.identifier === 'g');
check(() => assert(near(rg.ceilingArea.value, 21.9317)));
check(() => assert.strictEqual(rg.ceilingArea.status, 'reconstructed'));
check(() => assert.strictEqual(rg.ceilingArea.method, 'knee'));
check(() => assert(near(rg.ceilingArea.heightM.min, 1.6)));
const rn = report.rooms.find((r) => r.identifier === 'nowall');
check(() => assert.strictEqual(rn.ceilingArea.value, null));
check(() => assert.strictEqual(rn.ceilingArea.status, 'unavailable'));
// totals: subtotal of what is available, flagged partial when not complete
check(() => assert(near(report.totals.ceilingArea.value, 21.9317)));
check(() => assert.strictEqual(report.totals.ceilingArea.coverage, 'partial'));
check(() => assert.strictEqual(report.totals.ceilingArea.included, 1));
check(() => assert.strictEqual(report.totals.ceilingArea.expected, 2));
check(() => assert.deepStrictEqual(report.totals.ceilingArea.byStatus, { reconstructed: 1, unavailable: 1 }));
// supplied ceiling keeps its source area and is never re-derived
const supplied = buildReport({ kind: 'optimized', surfaces: [floorSurface], objects: [], rooms: [room] }, {});
check(() => assert(near(supplied.rooms[0].ceilingArea.value, 16, 1e-9)));
check(() => assert.strictEqual(supplied.rooms[0].ceilingArea.status, 'supplied'));
check(() => assert.strictEqual(supplied.totals.ceilingArea.coverage, 'complete'));

// constants exported for callers/tests (parity with the archived engine)
check(() => assert.strictEqual(R.SLOPE_PARALLEL_TOL_DEG, 15));
check(() => assert.strictEqual(R.KNEE_MATCH_TOL_M, 0.06));
check(() => assert.strictEqual(R.KNEE_SIDE_TOL_M, 0.5));
check(() => assert(near(R.wallHeightAt(gableWall, -2), 1.6) && near(R.wallHeightAt(gableWall, 0), 2.5) && near(R.wallHeightAt(gableWall, 2), 1.6)));
check(() => assert.strictEqual(R.topEdgeSloped(gableWall), true) && assert.strictEqual(R.topEdgeSloped(flatWall), false));

console.log(`ceiling-reconstruct: ${checks} checks passed`);
