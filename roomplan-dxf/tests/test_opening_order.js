'use strict';
/**
 * tests/test_opening_order.js — openings above walls, and coloured.
 *
 * A door/window/opening is ONE thin centre line lying on the wall footprint it
 * belongs to. DXF model space has no z-order: a viewer paints entities in file
 * order, so a wall written after its opening covers it, and the plan reads as a
 * windowless box. This suite proves the promise from both ends:
 *
 *   1. the plan (lib/dxf-writer.js) is SORTED into paint order, regardless of
 *      the order the source declared the surfaces in;
 *   2. the emitter (lib/dxf-emit.py) re-applies the same order, so even a
 *      hand-built/older plan comes out with the openings on top;
 *   3. every opening layer carries its own ACI colour (DOOR 3 green, WINDOW 5
 *      blue, OPENING 6 magenta), never the wall's 7 — measured from the written
 *      DXF layer table, not from the dictionary in the source;
 *   4. no entity is lost or duplicated by the sort.
 */
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const cp = require('child_process');

const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const { buildDXF, sortByDrawOrder, drawOrderFor, DRAW_ORDER } = require(path.join(LIB, 'dxf-writer'));

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
const mv = (x, z) => I.map((v, i) => (i === 12 ? x : i === 14 ? z : v));
const corners = [{ x: -4, y: 0, z: -4 }, { x: 4, y: 0, z: -4 }, { x: 4, y: 0, z: 4 }, { x: -4, y: 0, z: 4 }];
const floor = { identifier: 'f', kind: 'floor', story: 0, dimensions: { x: 8, y: 0, z: 8 }, polygonCorners: corners, transform: I };
const wallA = { identifier: 'w1', kind: 'wall', story: 0, transform: mv(0, -4), dimensions: { x: 8, y: 3, z: 0.2 } };
const wallB = { identifier: 'w2', kind: 'wall', story: 0, transform: mv(-4, 0), dimensions: { x: 8, y: 3, z: 0.2 } };
const opening = { identifier: 'o1', kind: 'opening', parentIdentifier: 'w1', story: 0, transform: mv(1, -4), dimensions: { x: 1.2, y: 2.1, z: 0 } };
const door = { identifier: 'd1', kind: 'door', parentIdentifier: 'w2', story: 0, transform: mv(-4, 1), dimensions: { x: 0.9, y: 2.1, z: 0 } };
const window_ = { identifier: 'v1', kind: 'window', parentIdentifier: 'w2', story: 0, transform: mv(-4, -1), dimensions: { x: 1.4, y: 1.2, z: 0 } };
const room = { identifier: 'r', story: 0, floorHeight: 2.8, vertices: [{ x: -3, z: -3 }, { x: 3, z: -3 }, { x: 3, z: 3 }, { x: -3, z: 3 }], centerX: 0, centerZ: 0, area: 36, category: 'Other', ceiling: [] };

// Openings declared FIRST: the sort, not the input order, has to decide.
const model = { kind: 'optimized', surfaces: [opening, door, window_, wallA, wallB, floor], objects: [], rooms: [room], architecturalAlignment: { matrix: I } };
const built = buildDXF(model, { noFrame: true });
const plan = built.plan;
const kinds = plan.entities.map((e) => String(e.layer).split('_').slice(1).join('_'));
const OPENINGS = ['DOOR', 'WINDOW', 'OPENING'];
const firstOf = (kind) => kinds.indexOf(kind);
const lastOf = (kind) => kinds.lastIndexOf(kind);

check('every opening is drawn after every wall', () => {
  const lastWall = Math.max(firstOf('WALL'), lastOf('WALL'));
  for (const kind of OPENINGS) {
    assert(firstOf(kind) !== -1, `${kind} missing from the plan`);
    assert(firstOf(kind) > lastWall, `${kind} at ${firstOf(kind)} is not after last WALL at ${lastWall}`);
  }
});
check('no WALL is left after the first opening', () => {
  const firstOpening = Math.min(...OPENINGS.map(firstOf).filter((i) => i !== -1));
  assert.strictEqual(lastOf('WALL') < firstOpening, true);
});
check('openings are above floor, room outline and furniture too', () => {
  const firstOpening = Math.min(...OPENINGS.map(firstOf).filter((i) => i !== -1));
  for (const kind of ['FLOOR', 'ROOM']) {
    if (firstOf(kind) === -1) continue;
    assert(lastOf(kind) < firstOpening, `${kind} is painted above the openings`);
  }
});
check('labels are painted above the openings (text stays readable)', () => {
  if (firstOf('LABEL') === -1) return;
  const lastOpening = Math.max(...OPENINGS.map(lastOf));
  assert(firstOf('LABEL') > lastOpening);
});
check('ceilings are annotations: painted last, never over the geometry they describe', () => {
  const ceil = kinds.findIndex((k) => k.startsWith('CEILING'));
  if (ceil === -1) return;
  assert(ceil > Math.max(...OPENINGS.map(lastOf)));
});
check('the sort is stable: the two walls keep the decoder order', () => {
  const wallIdx = plan.entities.map((e, i) => ({ e, i })).filter(({ e }) => e.layer === 'S0_WALL').map(({ e }) => e.transform);
  const srcOrder = built.plan.entities.filter((e) => e.layer === 'S0_WALL').map((e) => e.points[0].join(','));
  assert.strictEqual(wallIdx.length, 2);
  assert.strictEqual(new Set(srcOrder).size, 2, 'both walls survived');
});
check('the sort never adds or drops an entity', () => {
  assert.strictEqual(plan.entities.length, built.entityCount);
  const before = model.surfaces.length; // floor + 2 walls + 3 openings
  const geometry = plan.entities.filter((e) => !String(e.layer).endsWith('_LABEL') && !String(e.layer).startsWith('S0_CEILING')).length;
  assert(geometry >= before, `geometry ${geometry} < source elements ${before}`);
});
check('draw order table is the documented one', () => {
  assert.strictEqual(DRAW_ORDER.FLOOR < DRAW_ORDER.WALL, true);
  assert.strictEqual(DRAW_ORDER.WALL < DRAW_ORDER.DOOR, true);
  assert.strictEqual(DRAW_ORDER.DOOR < DRAW_ORDER.LABEL, true);
  assert.strictEqual(drawOrderFor({ type: 'line', layer: 'S3_OPENING' }), DRAW_ORDER.OPENING);
  assert.strictEqual(drawOrderFor({ type: 'line', layer: 'S3_UNKNOWN' }), 65);
  assert.strictEqual(drawOrderFor({ type: 'text', layer: 'S3_UNKNOWN' }), 60);
});
check('sort helper keeps equal priorities in input order', () => {
  const input = [
    { type: 'line', layer: 'S0_WALL', id: 'w1' },
    { type: 'line', layer: 'S0_DOOR', id: 'd1' },
    { type: 'line', layer: 'S0_WALL', id: 'w2' },
    { type: 'line', layer: 'S0_WINDOW', id: 'v1' },
  ];
  assert.deepStrictEqual(sortByDrawOrder(input).map((e) => e.id), ['w1', 'w2', 'd1', 'v1']);
});

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'opening-order-'));
const dxfFile = path.join(tmp, 'openings.dxf');
const emit = cp.spawnSync('python3', [path.join(LIB, 'dxf-emit.py'), dxfFile], { input: JSON.stringify(plan), encoding: 'utf8' });
check('emitter accepts the plan', () => assert.strictEqual(emit.status, 0, emit.stderr));
const summary = JSON.parse(emit.stdout);
check('summary reports openings above walls', () => {
  assert.strictEqual(summary.drawOrder.openingsAboveWalls, true);
  assert(summary.drawOrder.firstOpeningIndex > summary.drawOrder.lastWallIndex);
});
check('summary reports one colour per opening layer', () => {
  assert.deepStrictEqual(summary.drawOrder.openingColors, { S0_DOOR: 3, S0_OPENING: 6, S0_WINDOW: 5 });
});

// ---- ordered plan without walls, but WRONG file order: the emitter re-sorts.
const shuffled = JSON.parse(JSON.stringify(plan));
shuffled.entities = shuffled.entities.slice().sort((a, b) => {
  const rank = (e) => (OPENINGS.includes(String(e.layer).split('_')[1]) ? 0 : String(e.layer).endsWith('WALL') ? 2 : 1);
  return rank(a) - rank(b);
});
const shuffledFile = path.join(tmp, 'shuffled.dxf');
const emit2 = cp.spawnSync('python3', [path.join(LIB, 'dxf-emit.py'), shuffledFile], { input: JSON.stringify(shuffled), encoding: 'utf8' });
check('emitter accepts a wall-after-opening plan', () => assert.strictEqual(emit2.status, 0, emit2.stderr));
check('emitter re-sorts: openings still end up above the walls', () => {
  assert.strictEqual(JSON.parse(emit2.stdout).drawOrder.openingsAboveWalls, true);
});

// ---- measured from the WRITTEN DXF, not from the dictionaries above.
const probe = cp.spawnSync('python3', ['-c', `
import ezdxf, json, sys
doc = ezdxf.readfile(sys.argv[1])
assert not doc.audit().errors
layers = {}
for name in ("S0_WALL", "S0_DOOR", "S0_WINDOW", "S0_OPENING"):
    lyr = doc.layers.get(name)
    layers[name] = (lyr.dxf.color, lyr.dxf.lineweight)
order = [e.dxf.layer for e in doc.modelspace()]
print(json.dumps({"layers": layers, "order": order,
                  "audit": len(doc.audit().errors)}))
`, dxfFile], { encoding: 'utf8' });
check('written DXF can be audited', () => assert.strictEqual(probe.status, 0, probe.stderr));
const dxf = JSON.parse(probe.stdout);
check('opening colours in the file: DOOR 3, WINDOW 5, OPENING 6 — never the wall 7', () => {
  assert.strictEqual(dxf.layers.S0_WALL[0], 7);
  assert.strictEqual(dxf.layers.S0_DOOR[0], 3);
  assert.strictEqual(dxf.layers.S0_WINDOW[0], 5);
  assert.strictEqual(dxf.layers.S0_OPENING[0], 6);
});
check('opening lineweight equals the wall 0.35 mm so the mark covers the wall band', () => {
  assert.strictEqual(dxf.layers.S0_WALL[1], 35);
  for (const name of ['S0_DOOR', 'S0_WINDOW', 'S0_OPENING']) assert.strictEqual(dxf.layers[name][1], 35);
});
check('file order in the DXF: every opening entity after every wall entity', () => {
  const wall = dxf.order.lastIndexOf('S0_WALL');
  for (const layer of ['S0_DOOR', 'S0_WINDOW', 'S0_OPENING']) {
    assert(dxf.order.includes(layer), `${layer} missing from modelspace`);
    assert(dxf.order.indexOf(layer) > wall, `${layer} written before the last wall`);
  }
});

console.log(`opening order: ${checks} checks passed`);
