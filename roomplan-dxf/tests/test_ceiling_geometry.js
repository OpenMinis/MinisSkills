'use strict';
/**
 * tests/test_ceiling_geometry.js — ceilings as GEOMETRY / as labels.
 *
 * What this pins down (the failure this file exists for: a .usdz with no
 * ceilings at all, rooms with no height, a DXF whose room text had no "h"
 * because the height was never carried across, ONE tilted sheet stretched over
 * a whole room that only slopes along one wall, and door/window prims that
 * filled the holes cut for them):
 *
 *   1. a flat ceiling is ONE planar mesh prim at the measured height;
 *   2. a knee profile (slope along one wall, flat for the rest) is TWO prims:
 *      CeilingSlope_n from knee to ridge and CeilingFlat_n at the ridge, with
 *      the band area = run x room depth and the remainder = the rest;
 *   3. a shed profile with no flat run at all is one ramp;
 *   4. a gable (both profile ends low) gives two roof planes;
 *   5. a zone with no footprint gets NO ceiling plus usdz.ceiling-no-polygon;
 *   6. an explicit FLAT source ceiling stays ONE prim and is NOT drawn on the
 *      ceiling layer (a flat plane needs no dashed strips);
 *   7. the DXF room label carries "h 2." (flat) / "h 1." (sloped);
 *   8. --no-ceilings (buildDXF {ceilings:false}) removes every ceiling;
 *   9. no Door/Window/Opening prim projects more than 5% of itself onto the
 *      opening it names — the hole must stay a hole.
 */
const assert = require('assert');
const path = require('path');
const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const { ceilingSolids, heightLabel, splitCeilingPlan } = require(path.join(LIB, 'ceiling-3d'));
const { buildDXF } = require(path.join(LIB, 'dxf-writer'));
const { buildUsda } = require(path.join(LIB, 'usda-export'));
const { lint } = require(path.join(__dirname, 'lib', 'usda-lint'));

let checks = 0;
function check(name, fn) {
  try {
    fn();
    checks += 1;
  } catch (e) {
    console.error(`FAIL ${name}: ${e.message}`);
    process.exit(1);
  }
}
const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const wall = (id, corners, dims, transform) => ({
  identifier: id, kind: 'wall', story: 0, transform: transform || I,
  dimensions: dims || { x: 8, y: 2.5, z: 0.2 }, polygonCorners: corners,
});
const FLOOR = {
  identifier: 'F-1', kind: 'floor', story: 0, transform: I, dimensions: { x: 8, y: 0, z: 8 },
  polygonCorners: [{ x: -4, y: 0, z: -4 }, { x: 4, y: 0, z: -4 }, { x: 4, y: 0, z: 4 }, { x: -4, y: 0, z: 4 }],
};
const ROOM = {
  identifier: 'R-1', label: 'Soba', story: 0, area: 64, floorHeight: 0,
  vertices: [{ x: -4, z: -4 }, { x: 4, z: -4 }, { x: 4, z: 4 }, { x: -4, z: 4 }],
  centerX: 0, centerZ: 0,
};
// flat: every wall top edge horizontal at 2.5 m
const FLAT_WALL = wall('W-FLAT', [{ x: -4, y: 0, z: 0 }, { x: -4, y: 2.5, z: 0 }, { x: 4, y: 2.5, z: 0 }, { x: 4, y: 0, z: 0 }]);
// shed: one top edge running 1.6 -> 2.5 m over 8 m (no flat run: a pure ramp)
const SHED_WALL = wall('W-SHED', [{ x: -4, y: 0, z: 0 }, { x: -4, y: 1.6, z: 0 }, { x: 4, y: 2.5, z: 0 }, { x: 4, y: 0, z: 0 }]);
// gable: both ends at 1.6 m, ridge 2.5 m in the middle
const GABLE_WALL = wall('W-GAB', [{ x: -4, y: 0, z: 0 }, { x: -4, y: 1.6, z: 0 }, { x: 0, y: 2.5, z: 0 }, { x: 4, y: 1.6, z: 0 }, { x: 4, y: 0, z: 0 }]);
const model = (w) => ({ kind: 'optimized', surfaces: [FLOOR, w], objects: [], rooms: [ROOM] });

const flat = ceilingSolids(model(FLAT_WALL));
const shed = ceilingSolids(model(SHED_WALL));
const gable = ceilingSolids(model(GABLE_WALL));

/* ------------------------------------------- the real knee profile (hh) --- */
/**
 * Project-hh cross-section, measured from the scan itself:
 *   run 1.2248 m, rise 0.8342 m (tan 0.681 = 34.26 deg), knee 1.6489 m,
 *   ridge 2.4832 m, knee wall 7.81 m long.
 * Room 6 x 4 m; the sloped-top wall runs along +z at x = 0, so the ceiling
 * leaves the knee at z = 0 and is flat from z = 1.2248 to z = 4.
 */
const KNEE_M = 1.64893728;
const RIDGE_M = 2.48318140;
const RUN_M = 1.22484920;
const SEC_XFORM = [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 2, 1]; // local +x -> world +z, centred at (0, 0, 2)
const SEC_CORNERS = [
  { x: -2, y: 0, z: 0 },
  { x: -2, y: KNEE_M, z: 0 },
  { x: -2 + RUN_M, y: RIDGE_M, z: 0 },
  { x: 2, y: RIDGE_M, z: 0 },
  { x: 2, y: 0, z: 0 },
];
const HH = {
  kind: 'optimized',
  surfaces: [
    {
      identifier: 'F', kind: 'floor', story: 0, transform: I, dimensions: { x: 6, y: 0, z: 4 },
      polygonCorners: [{ x: 0, y: 0, z: 0 }, { x: 6, y: 0, z: 0 }, { x: 6, y: 0, z: 4 }, { x: 0, y: 0, z: 4 }],
    },
    wall('W-SEC', SEC_CORNERS, { x: 4, y: RIDGE_M, z: 0.2 }, SEC_XFORM),
    // knee wall (the LOW wall, 1.65 m) along the whole room at z = 0
    wall('W-KNEE', [{ x: -3, y: 0, z: 0 }, { x: -3, y: KNEE_M, z: 0 }, { x: 3, y: KNEE_M, z: 0 }, { x: 3, y: 0, z: 0 }], { x: 6, y: KNEE_M, z: 0.2 }, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 3, 0, 0, 1]),
    // the high wall at z = 4 and the far side wall at x = 6, both at the ridge
    wall('W-HIGH', [{ x: -3, y: 0, z: 0 }, { x: -3, y: RIDGE_M, z: 0 }, { x: 3, y: RIDGE_M, z: 0 }, { x: 3, y: 0, z: 0 }], { x: 6, y: RIDGE_M, z: 0.2 }, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 3, 0, 4, 1]),
    wall('W-SIDE', [{ x: -2, y: 0, z: 0 }, { x: -2, y: RIDGE_M, z: 0 }, { x: 2, y: RIDGE_M, z: 0 }, { x: 2, y: 0, z: 0 }], { x: 4, y: RIDGE_M, z: 0.2 }, [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 6, 0, 2, 1]),
  ],
  objects: [],
  rooms: [{
    identifier: 'hh', label: 'Soba', story: 0, area: 24, floorHeight: 0,
    vertices: [{ x: 0, z: 0 }, { x: 6, z: 0 }, { x: 6, z: 4 }, { x: 0, z: 4 }], centerX: 3, centerZ: 2,
  }],
};
const hh = ceilingSolids(HH);

/* ---------------------------------------- explicit flat room (HRT 2053) --- */
const HRT_AREA = 40.487412748294155;
// local XY polygon, rotated flat by its transform (local +y -> world -z), at 3.069 m
const hrtCeiling = (x0, x1) => ({
  polygon: [[x0, 0], [x1, 0], [x1, -7.3618], [x0, -7.3618]],
  transform: [1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 3.069, 0, 1],
});
const HRT = {
  kind: 'optimized',
  surfaces: [{
    identifier: 'F', kind: 'floor', story: 0, transform: I, dimensions: { x: 5.5, y: 0, z: 7.3618 },
    polygonCorners: [{ x: 0, y: 0, z: 0 }, { x: 5.5, y: 0, z: 0 }, { x: 5.5, y: 0, z: 7.3618 }, { x: 0, y: 0, z: 7.3618 }],
  }],
  objects: [],
  rooms: [{
    identifier: '2053', label: 'Room', story: 0, area: HRT_AREA, floorHeight: 0,
    vertices: [{ x: 0, z: 0 }, { x: 5.5, z: 0 }, { x: 5.5, z: 7.3618 }, { x: 0, z: 7.3618 }], centerX: 2.75, centerZ: 3.68,
    // the source cut the flat ceiling into TWO coplanar plates: still one ceiling
    ceiling: [hrtCeiling(0, 2.6), hrtCeiling(2.6, 5.5)],
    ceilingCurrent: [hrtCeiling(0, 2.6), hrtCeiling(2.6, 5.5)],
  }],
};
const hrt = ceilingSolids(HRT);

/* ------------------------------------------------------------ geometry -- */

check('flat ceiling: ONE part, one planar surface at the measured wall height', () => {
  assert.strictEqual(flat.ceilings.length, 1);
  const c = flat.ceilings[0];
  assert.strictEqual(c.method, 'flat');
  assert.strictEqual(c.parts.length, 1, 'a flat ceiling must never be split');
  assert.strictEqual(c.parts[0].kind, 'flat');
  assert.strictEqual(c.heightLabel, '2.50');
  for (const p of c.parts[0].points) assert(Math.abs(p[1] - 2.5) < 1e-9, `vertex at ${p[1]} m, not 2.50`);
  assert.deepStrictEqual(flat.warnings, []);
});

check('flat ceiling in USDZ: one CeilingFlat prim, 2 triangles, normal -Y, Height customData', () => {
  const res = buildUsda(model(FLAT_WALL), {});
  const body = res.text.slice(res.text.indexOf('def Mesh "CeilingFlat_1"'));
  const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1];
  assert.strictEqual(counts, '3, 3', `expected 2 triangles, got ${counts}`);
  const normals = /normal3f\[\] normals = \[([\s\S]*?)\]\n/.exec(body)[1];
  const ys = [...normals.matchAll(/\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)/g)].map((m) => Number(m[2]));
  assert(ys.length >= 2, 'no normals');
  for (const y of ys) assert(y < -0.999, `ceiling normal y=${y}, must be -Y (seen from below)`);
  assert(/string Height = "2\.50"/.test(res.text), 'Height "2.50" missing from ceiling customData');
  assert(/string Method = "flat"/.test(res.text));
  assert(/double Area = 64\.000000/.test(res.text), 'ceiling area missing');
  assert(/string Category = "Ceiling"/.test(res.text));
  assert(/string Identifier = "R-1"/.test(res.text));
  assert(/string Geometry = "flat plane at height 2\.50"/.test(res.text), 'flat plane must say so');
  assert(!/CeilingSlope/.test(res.text), 'a flat ceiling must not emit a slope prim');
});

/* --------------------------------------------- knee profile: TWO prims ---- */

check('hh profile: the ceiling is TWO parts — a sloped strip and a flat remainder', () => {
  assert.strictEqual(hh.ceilings.length, 1, 'one room, one ceiling');
  const c = hh.ceilings[0];
  assert.strictEqual(c.method, 'knee');
  assert.strictEqual(c.parts.length, 2, `expected 2 parts, got ${c.parts.length}`);
  assert.deepStrictEqual(c.parts.map((p) => p.kind), ['slope', 'flat']);
  assert.deepStrictEqual(hh.warnings, []);
});

check('hh profile: the sloped strip spans knee..ridge, the flat one sits AT the ridge', () => {
  const [slope, flatPart] = hh.ceilings[0].parts;
  const ys = slope.points.map((p) => p[1]);
  assert(Math.abs(Math.min(...ys) - KNEE_M) < 1e-6, `slope min ${Math.min(...ys)} != knee ${KNEE_M}`);
  assert(Math.abs(Math.max(...ys) - RIDGE_M) < 1e-6, `slope max ${Math.max(...ys)} != ridge ${RIDGE_M}`);
  assert(slope.heightLabel === '1.65-2.48', slope.heightLabel);
  for (const p of flatPart.points) assert(Math.abs(p[1] - RIDGE_M) < 1e-6, `flat vertex at ${p[1]}, must be the ridge ${RIDGE_M}`);
  assert.strictEqual(flatPart.heightLabel, '2.48');
  // nothing is above the ridge and nothing below the knee anywhere
  for (const part of hh.ceilings[0].parts) {
    for (const p of part.points) assert(p[1] >= KNEE_M - 1e-6 && p[1] <= RIDGE_M + 1e-6);
  }
});

check('hh profile: sloped area = run x room depth (2%), flat = the rest', () => {
  const [slope, flatPart] = hh.ceilings[0].parts;
  const depth = 6; // the room is 6 m wide along the ridge (z runs 0..4)
  const expectedSlope = RUN_M * depth;
  assert(Math.abs(slope.area - expectedSlope) / expectedSlope < 0.02, `slope area ${slope.area} != run x depth ${expectedSlope}`);
  const expectedFlat = 24 - expectedSlope;
  assert(Math.abs(flatPart.area - expectedFlat) / expectedFlat < 0.02, `flat area ${flatPart.area} != ${expectedFlat}`);
  assert(Math.abs(slope.area + flatPart.area - 24) < 1e-6, 'the two parts must tile the whole footprint once');
});

check('hh profile in USDZ: CeilingSlope_1 + CeilingFlat_1 with their own customData', () => {
  const res = buildUsda(HH, {});
  assert(/def Mesh "CeilingSlope_1"/.test(res.text), 'no sloped ceiling prim');
  assert(/def Mesh "CeilingFlat_1"/.test(res.text), 'no flat ceiling prim');
  const named = res.summary.prims.filter((p) => p.category === 'Ceiling').map((p) => p.name);
  assert.deepStrictEqual(named.sort(), ['CeilingFlat_1', 'CeilingSlope_1']);
  const slopeBlock = res.text.slice(res.text.indexOf('def Xform "CeilingSlope_1"'), res.text.indexOf('def Xform "CeilingFlat_1"'));
  assert(/string Height = "1\.65-2\.48"/.test(slopeBlock), 'slope Height label wrong');
  assert(/string Method = "knee"/.test(slopeBlock), 'slope Method must be knee');
  assert(/string Geometry = "sloped strip/.test(slopeBlock), 'slope Geometry label wrong');
  const flatBlock = res.text.slice(res.text.indexOf('def Xform "CeilingFlat_1"'));
  assert(/string Height = "2\.48"/.test(flatBlock), 'flat Height label wrong');
  assert(/string Method = "flat"/.test(flatBlock), 'flat Method wrong');
  assert(/string Geometry = "flat plane/.test(flatBlock), 'flat Geometry label wrong');
  // both prims are real geometry, and the sloped one really is tilted
  const body = res.text.slice(res.text.indexOf('def Mesh "CeilingSlope_1"'));
  const pts = [.../point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body)[1].matchAll(/\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)/g)]
    .map((m) => Number(m[2]));
  assert(Math.max(...pts) - Math.min(...pts) > 0.5, 'the sloped prim is not actually sloped');
  const fbody = res.text.slice(res.text.indexOf('def Mesh "CeilingFlat_1"'));
  const fpts = [.../point3f\[\] points = \[([\s\S]*?)\]\n/.exec(fbody)[1].matchAll(/\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)/g)]
    .map((m) => Number(m[2]));
  assert(Math.max(...fpts) - Math.min(...fpts) < 1e-6, 'the flat prim is not flat');
});

check('hh profile: the split lands on the fall direction, not across it', () => {
  // the band must run the full width of the room along the ridge (6 m) and be
  // exactly `run` deep along the fall direction (z)
  const slope = hh.ceilings[0].parts[0];
  const xs = slope.points.map((p) => p[0]);
  const zs = slope.points.map((p) => p[2]);
  assert(Math.abs(Math.max(...xs) - Math.min(...xs) - 6) < 1e-6, 'the band does not span the room width');
  assert(Math.abs(Math.max(...zs) - Math.min(...zs) - RUN_M) < 1e-6, 'the band is not one run deep');
});

check('splitCeilingPlan: a footprint narrower than the run stays one ramp', () => {
  const square = [[0, 0], [8, 0], [8, 8], [0, 8]];
  const s = splitCeilingPlan(square, [1, 0], 'minus', { run: 8, knee: 1.6, ridge: 2.5 });
  assert.strictEqual(s.parts.length, 1);
  assert.strictEqual(s.parts[0].kind, 'slope');
  const two = splitCeilingPlan(square, [1, 0], 'minus', { run: 3, knee: 1.6, ridge: 2.5 });
  assert.strictEqual(two.parts.length, 2);
  assert(Math.abs(two.parts[0].heightAt([0, 4]) - 1.6) < 1e-9, 'the band must start at the knee');
  assert(Math.abs(two.parts[0].heightAt([3, 4]) - 2.5) < 1e-9, 'the band must reach the ridge after `run`');
  assert(Math.abs(two.parts[1].heightAt([5, 4]) - 2.5) < 1e-9, 'the remainder must be flat at the ridge');
  assert(two.ridgeLines.length === 1, 'the ridge line must be traced');
});

check('sloped ceiling with no flat run: vertices at different heights, min<max', () => {
  const c = shed.ceilings[0];
  assert.strictEqual(c.parts.length, 1, 'a pure ramp has no flat remainder to emit');
  const ys = c.parts[0].points.map((p) => p[1]);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  assert(min < max - 0.2, `sloped ceiling is flat: ${min} .. ${max}`);
  assert(Math.abs(min - 1.6) < 1e-9 && Math.abs(max - 2.5) < 1e-9);
  assert.strictEqual(c.heightLabel, '1.60-2.50');
});

check('gable: two roof planes with the ridge in the middle', () => {
  const c = gable.ceilings[0];
  const slopes = c.parts.filter((p) => p.kind === 'slope');
  assert.strictEqual(slopes.length, 2, 'a gable must be two planes');
  const all = slopes.flatMap((s) => s.points.map((p) => p[1]));
  assert(Math.abs(Math.min(...all) - 1.6) < 1e-6 && Math.abs(Math.max(...all) - 2.5) < 1e-6);
  // ridge x = 0 on both planes, eaves at +-4
  for (const s of slopes) {
    const ridge = s.points.filter((p) => Math.abs(p[1] - 2.5) < 1e-6);
    assert(ridge.length >= 2, 'no ridge vertices');
    for (const p of ridge) assert(Math.abs(p[0]) < 1e-6, `ridge at x=${p[0]}`);
  }
});

check('no footprint polygon: no ceiling, warning usdz.ceiling-no-polygon', () => {
  const bare = { kind: 'raw', surfaces: [wall('W', [{ x: -2, y: 0, z: 0 }, { x: -2, y: 2.5, z: 0 }, { x: 2, y: 2.5, z: 0 }, { x: 2, y: 0, z: 0 }])], objects: [] };
  const r = ceilingSolids(bare);
  assert.strictEqual(r.ceilings.length, 0, 'a ceiling without a footprint would be invented');
  assert(r.warnings.some((w) => w.code === 'usdz.ceiling-no-polygon'), 'missing warning');
  const usda = buildUsda(bare, {});
  assert(!/Category = "Ceiling"/.test(usda.text), 'no ceiling prim may be written');
  assert(usda.warnings.some((w) => w.code === 'usdz.ceiling-no-polygon'));
});

check('heightLabel: "2.50" flat, "1.60-2.50" sloped, null when unknown', () => {
  assert.strictEqual(heightLabel(2.5, 2.5), '2.50');
  assert.strictEqual(heightLabel(1.6, 2.5), '1.60-2.50');
  assert.strictEqual(heightLabel(null, 2.5), null);
});

/* ------------------------------------ explicit FLAT ceiling (HRT 2053) ---- */

check('explicit flat ceiling: ONE prim at 3.07 m even when the source has two plates', () => {
  assert.strictEqual(hrt.ceilings.length, 1);
  const c = hrt.ceilings[0];
  assert.strictEqual(c.method, 'explicit');
  assert.strictEqual(c.parts.length, 1, 'a flat source ceiling cut into plates is still ONE ceiling');
  assert.strictEqual(c.parts[0].kind, 'flat');
  assert.strictEqual(c.heightLabel, '3.07');
  for (const p of c.parts[0].points) assert(Math.abs(p[1] - 3.069) < 1e-6, `vertex at ${p[1]}`);
  const usda = buildUsda(HRT, {});
  const ceilingPrims = usda.summary.prims.filter((p) => p.category === 'Ceiling');
  assert.strictEqual(ceilingPrims.length, 1, `expected 1 ceiling prim, got ${ceilingPrims.map((p) => p.name)}`);
  assert(/string Height = "3\.07"/.test(usda.text));
  assert(!/CeilingSlope/.test(usda.text), 'a flat ceiling must never be split');
});

/* ----------------------------------------------------------------- DXF -- */

const labelOf = (res) => res.plan.entities.filter((e) => e.type === 'text' && /_LABEL$/.test(e.layer));
const ceilEntities = (res, layer) => res.plan.entities.filter((e) => e.layer === layer);

check('DXF: ceilings are ON by default', () => {
  const res = buildDXF(model(SHED_WALL), { noFrame: true });
  assert.strictEqual(res.ceilingDiagnostics.enabled, true, 'ceilings must default on');
  assert(res.plan.entities.some((e) => e.layer === 'S0_CEILING'), 'no S0_CEILING layer content');
  assert(res.plan.layers.includes('S0_CEILING'));
});

check('DXF: a flat ceiling draws NOTHING on the ceiling layer (no strips across the room)', () => {
  const res = buildDXF(model(FLAT_WALL), { noFrame: true });
  assert.strictEqual(ceilEntities(res, 'S0_CEILING').length, 0, 'a flat ceiling must not be drawn');
  assert(!res.plan.layers.includes('S0_CEILING'), 'no ceiling layer may even be declared');
  // the height still reaches the room label
  const room = labelOf(res).map((e) => e.value).find((v) => v.startsWith('Soba'));
  assert(/h 2\.50$/.test(room), `label was "${room}"`);
});

check('DXF HRT: a flat explicit ceiling leaves S0_CEILING empty, the room label carries h 3.07', () => {
  const res = buildDXF(HRT, { noFrame: true });
  assert.strictEqual(ceilEntities(res, 'S0_CEILING').length, 0, `expected 0 ceiling entities, got ${JSON.stringify(ceilEntities(res, 'S0_CEILING'))}`);
  assert.strictEqual(ceilEntities(res, 'S0_CEILING_FLAT').length, 0, 'nothing at all for a flat ceiling');
  const room = labelOf(res).map((e) => e.value).find((v) => v.startsWith('Room'));
  assert(/Room {2}40\.49 m2 {2}h 3\.07/.test(room), `label was "${room}"`);
});

check('DXF hh: only the sloped band is orange — the flat remainder gets its own thin layer', () => {
  const res = buildDXF(HH, { noFrame: true });
  const band = ceilEntities(res, 'S0_CEILING');
  assert(band.filter((e) => e.type === 'line').length >= 4, 'band outline missing');
  const texts = band.filter((e) => e.type === 'text').map((e) => e.value);
  assert(texts.some((v) => /h 1\.65-2\.48 \(knee\)/.test(v)), `band height/method text missing: ${JSON.stringify(texts)}`);
  const flatLayer = ceilEntities(res, 'S0_CEILING_FLAT');
  assert(flatLayer.length > 0, 'the flat remainder must still be bounded and labelled');
  const flatTexts = flatLayer.filter((e) => e.type === 'text').map((e) => e.value);
  assert(flatTexts.some((v) => /h 2\.48 \(flat\)/.test(v)), `flat label missing: ${JSON.stringify(flatTexts)}`);
  assert(!flatTexts.some((v) => /knee/.test(v)), 'the flat part must not be labelled as a knee');
});

check('DXF: the sloped band area matches the 3D band (one split, two consumers)', () => {
  const res = buildDXF(HH, { noFrame: true });
  const rec = res.ceilingDiagnostics.records.find((r) => r.roomIdentifier === 'hh');
  assert(rec && rec.ceilingDrawn, 'the hh ceiling must be drawn');
  const expected = RUN_M * 6;
  assert(Math.abs(rec.bandAreaM2 - expected) / expected < 0.02, `DXF band ${rec.bandAreaM2} != ${expected}`);
  assert(Math.abs(rec.flatAreaM2 - (24 - expected)) / (24 - expected) < 0.02);
});

check('DXF room label carries the area and "h 1." for a sloped ceiling', () => {
  const res = buildDXF(model(SHED_WALL), { noFrame: true });
  const labels = labelOf(res).map((e) => e.value);
  const room = labels.find((v) => v.startsWith('Soba'));
  assert(room, `no room label: ${JSON.stringify(labels)}`);
  assert(/Soba {2}64\.00 m2 {2}h 1\.60-2\.50/.test(room), `label was "${room}"`);
});

check('DXF: sloped ceiling is visible (band outline + fall line + method text)', () => {
  const res = buildDXF(model(SHED_WALL), { noFrame: true });
  const ceil = ceilEntities(res, 'S0_CEILING');
  assert(ceil.filter((e) => e.type === 'line').length >= 4, 'dashed band outline missing');
  const texts = ceil.filter((e) => e.type === 'text').map((e) => e.value);
  assert(texts.some((v) => /h 1\.60-2\.50 \(section\)/.test(v)), `method/height text missing: ${JSON.stringify(texts)}`);
  // 4 dashed outline edges + the fall line = 5 (a pure ramp has no flat part)
  assert.strictEqual(ceil.filter((e) => e.type === 'line').length, 5, 'fall line missing');
});

check('DXF: --no-ceilings removes every ceiling entity', () => {
  const res = buildDXF(model(SHED_WALL), { noFrame: true, ceilings: false });
  assert.strictEqual(res.ceilingDiagnostics.enabled, false);
  assert(!res.plan.entities.some((e) => String(e.layer).endsWith('_CEILING')), 'ceiling entities survived --no-ceilings');
  assert(!res.plan.layers.some((n) => n.endsWith('_CEILING')));
});

check('DXF: no height known -> no "h" part at all (never a zero)', () => {
  const bare = { kind: 'raw', surfaces: [], objects: [] };
  const res = buildDXF(bare, { noFrame: true });
  assert.strictEqual(labelOf(res).length, 0);
  const noHeight = { kind: 'optimized', surfaces: [], objects: [], rooms: [{ ...ROOM, vertices: roomVertices(), area: 64 }] };
  const r2 = buildDXF(noHeight, { noFrame: true });
  const label = labelOf(r2).map((e) => e.value).find((v) => v.startsWith('Soba'));
  assert(label && !/ h /.test(label), `an unknown height must not be written as a number: "${label}"`);
});

function roomVertices() {
  return [{ x: -4, z: -4 }, { x: 4, z: -4 }, { x: 4, z: 4 }, { x: -4, z: 4 }];
}

check('DXF room label of a room without a polygon is "Kat N — area — h" at the story centre', () => {
  const raw = {
    kind: 'raw', objects: [],
    surfaces: [FLOOR, wall('W', [{ x: -4, y: 0, z: 0 }, { x: -4, y: 2.5, z: 0 }, { x: 4, y: 2.5, z: 0 }, { x: 4, y: 0, z: 0 }])],
  };
  const res = buildDXF(raw, { noFrame: true });
  const story = labelOf(res).map((e) => e.value).find((v) => v.startsWith('Kat'));
  assert(story, `no story label: ${JSON.stringify(labelOf(res).map((e) => e.value))}`);
  assert(/^Kat 0 \u2014 64\.00 m2/.test(story), `label was "${story}"`);
});

/* ------------------------------------------------------- openings: holes -- */

/** Area of a prim's triangles projected onto the plane of its own opening. */
function projectedOntoOpening(text, primName, normal) {
  const i = text.indexOf(`def Xform "${primName}"`);
  assert(i >= 0, `${primName} missing`);
  const next = text.indexOf('def Xform "', i + 10);
  const block = text.slice(i, next < 0 ? undefined : next);
  const m = /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(block);
  if (!m) return { area: 0, hasMesh: false };
  const pts = [...m[1].matchAll(/\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)/g)].map((x) => [Number(x[1]), Number(x[2]), Number(x[3])]);
  // every point is a triangle vertex (v/vt/vn split), so sum point triples
  let area = 0;
  for (let k = 0; k + 2 < pts.length; k += 3) {
    const [a, b, c] = [pts[k], pts[k + 1], pts[k + 2]];
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    area += Math.abs(n[0] * normal[0] + n[1] * normal[1] + n[2] * normal[2]) / 2;
  }
  return { area, hasMesh: true };
}

const OPENING_MODEL = {
  kind: 'raw',
  objects: [],
  surfaces: [
    // a wall box 4 x 2.5, its local z is the thickness axis -> opening plane normal (0,0,1)
    // the wall's local origin sits at its bottom-left corner, so u runs 0..4
    { identifier: 'W-1', kind: 'wall', story: 0, transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 1.25, 0, 1], dimensions: { x: 4, y: 2.5, z: 0.16 } },
    { identifier: 'D-1', kind: 'door', parentIdentifier: 'W-1', story: 0, transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1.5, 1.05, 0, 1], dimensions: { x: 0.9, y: 2.1, z: 0.16 } },
    { identifier: 'N-1', kind: 'window', parentIdentifier: 'W-1', story: 0, transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 3.0, 1.5, 0, 1], dimensions: { x: 1.2, y: 1.4, z: 0.16 } },
  ],
};

check('no Door/Window prim covers its opening: projection < 5% of the hole', () => {
  const res = buildUsda(OPENING_MODEL, {});
  for (const [name, openArea] of [['Door_1', 0.9 * 2.1], ['Window_1', 1.2 * 1.4]]) {
    const { area, hasMesh } = projectedOntoOpening(res.text, name, [0, 0, 1]);
    assert(!hasMesh || area / openArea < 0.05,
      `${name} projects ${(100 * area / openArea).toFixed(1)}% of the opening: the hole is filled again`);
  }
  assert(res.warnings.some((w) => w.code === 'usdz.opening-hole-only'), 'the hole-only export must be reported');
  const prim = res.summary.prims.find((p) => p.name === 'Door_1');
  assert(prim && prim.emptyXform && prim.points === 0, 'the opening prim must be an empty Xform');
});

check('the opening still exists by name, with its measured size, and the wall is really cut', () => {
  const res = buildUsda(OPENING_MODEL, {});
  assert(/def Xform "Door_1"/.test(res.text) && /def Xform "Window_1"/.test(res.text));
  assert(/double Width = 0\.900000/.test(res.text) && /double Height = 2\.100000/.test(res.text));
  assert(/int Openings = 2/.test(res.text), "both openings must be cut");
  assert(/double CutArea = 3\.570000/.test(res.text), `the door and window must both be cut (cut area ${/double CutArea = ([\d.]+)/.exec(res.text)}`);
  assert(res.summary.holes.openingsCut === 2, `expected 2 cut openings, got ${res.summary.holes.openingsCut}`);
});

/* ------------------------------------------------------------ lint 0/0 --- */

check('USDZ ceilings pass usda-lint with zero errors and zero warnings', () => {
  for (const m of [model(FLAT_WALL), model(SHED_WALL), model(GABLE_WALL), HH, HRT, OPENING_MODEL]) {
    const res = buildUsda(m, {});
    const r = lint(res.text, { name: 'room.usda' });
    assert.deepStrictEqual(r.errors, [], JSON.stringify(r.errors.slice(0, 2)));
    assert.deepStrictEqual(r.warnings, [], JSON.stringify(r.warnings.slice(0, 2)));
  }
});

console.log(`ceiling geometry: ${checks} checks passed`);
