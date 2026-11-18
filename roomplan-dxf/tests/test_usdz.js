'use strict';
/**
 * tests/test_usdz.js — the USDZ export (usdz-writer.js + usda-export.js).
 *
 * The .usdz is a ZIP of ASCII .usda. Nothing here needs Apple's SDK: the
 * archive is verified by PYTHON's own zipfile (an independent implementation,
 * so a self-consistent bug in our CRC/offset bookkeeping cannot pass), and the
 * layer text is checked with plain string/regex assertions.
 *
 * Covered:
 *   - the archive opens, lists room.usda, STOREs it and every payload starts on
 *     a 64-byte boundary;
 *   - zipfile.testzip() returns None (CRC-32 of every entry is correct);
 *   - #usda 1.0 header: defaultPrim/room, metersPerUnit 1, upAxis Y;
 *   - one `def Mesh` per element, named/categorised per contract, with
 *     customData Category/Identifier;
 *   - a box is 8 points / 6 quads; a source polygon is n points / n indices;
 *   - an unmeasured wall gets the 0.16 m default and is flagged assumed;
 *   - no NaN/Infinity anywhere, no comma decimals, 6 fixed decimals;
 *   - the output is byte-identical across two runs (fixed DOS timestamp);
 *   - the CLI writes <name>.usdz and exits 0, and refuses to clobber it without
 *     --force, and refuses an output that aliases the input.
 */
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const { crc32, buildUsdz, writeUsdz } = require(path.join(LIB, 'usdz-writer'));
const { buildUsda, sanitizeIdentifier } = require(path.join(LIB, 'usda-export'));
const { decode } = require(path.join(LIB, 'decode-raw'));

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

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'usdz-test-'));

/**
 * No shipped fixtures: the suite generates its inputs (same rule as
 * tests/selftest.py). This is a raw Apple-shaped CapturedRoom: 4 walls around
 * a 6 x 4 m room, one floor, one door, one window and two objects.
 */
const I4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const T = (x, y, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1];
const rotY90 = [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1.25, 2, 1];
function rawCapture() {
  const el = (identifier, kind, dims, transform, extra) => Object.assign({
    identifier,
    category: { [kind]: {} },
    confidence: { high: {} },
    dimensions: dims,
    transform,
    story: 0,
  }, extra || {});
  return {
    rooms: [{
      walls: [
        el('W-A', 'wall', [6, 2.5, 0], T(3, 1.25, 0)),
        el('W-B', 'wall', [6, 2.5, 0], T(3, 1.25, 4)),
        el('W-C', 'wall', [4, 2.5, 0], rotY90),
        el('W-D', 'wall', [4, 2.5, 0], [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 6, 1.25, 2, 1]),
      ],
      floors: [el('F-1', 'floor', [6, 4, 0], T(3, 0, 2))],
      doors: [el('D-1', 'door', [1, 2, 0], T(1.5, 1, 0), { parentIdentifier: 'W-A' })],
      windows: [el('N-1', 'window', [1.2, 1.2, 0], T(3, 1.6, 4), { parentIdentifier: 'W-B' })],
      objects: [
        el('OBJ-1', 'sofa', [2, 0.8, 0.9], T(1.5, 0.4, 1)),
        el('OBJ-2', 'table', [1.2, 0.75, 0.7], T(4.5, 0.375, 2.5)),
      ],
      referenceOriginTransform: I4,
    }],
  };
}
/** Same 6 x 4 m room in the optimized v1 dialect: one labelled room, 2 walls. */
function optimizedCapture() {
  return {
    format_version: 1,
    source: { generator: 'synthetic' },
    walls: [
      { identifier: 'W1', category: { wall: {} }, confidence: { high: {} }, dimensions: [6, 2.5, 0], transform: T(3, 1.25, 0), story: 0 },
      { identifier: 'W2', category: { wall: {} }, confidence: { high: {} }, dimensions: [6, 2.5, 0], transform: T(3, 1.25, 4), story: 0 },
    ],
    rooms: [{ id: 'R1', label_automated: 'Kuhinja', category: 'kitchen', story: 0, area: 24, center_xz: [3, 2], floor_height: 0, vertices_x: [0, 6, 6, 0], vertices_z: [0, 0, 4, 4] }],
    doors: [], windows: [], objects: [],
    floors: [{ identifier: 'F1', category: { floor: {} }, confidence: { high: {} }, dimensions: [6, 4, 0], transform: T(3, 0, 2), polygonCorners: [[-3, 0, -2], [3, 0, -2], [3, 0, 2], [-3, 0, 2]], story: 0 }],
    alignment_transform: I4,
    latLonAlt: { latitude: 45.8, longitude: 15.9, altitude: 120 },
    orientation: { degrees: 0, confidence: 0.9 },
  };
}

const FIXTURE = path.join(TMP, 'scan.json');
fs.writeFileSync(FIXTURE, JSON.stringify(rawCapture()));
const OPT_FIXTURE = path.join(TMP, 'opt.json');
fs.writeFileSync(OPT_FIXTURE, JSON.stringify(optimizedCapture()));

// 1) The raw capture: 4 walls, 1 floor, 1 door, 1 window, 2 objects -> 9 boxes.
const fixtureCapture = decode(fs.readFileSync(FIXTURE, 'utf8'));

// 2) A hand-made capture with one POLYGON wall (5 local corners, metric) plus a
//    room label, so both geometry paths and the section naming are exercised.
const POLY = [
  { x: -2, y: 0, z: 0 }, { x: 2, y: 0, z: 0 }, { x: 2, y: 2.5, z: 0 },
  { x: 0, y: 2.5, z: 0 }, { x: -2, y: 2.5, z: 0 },
];
const polyCapture = {
  kind: 'optimized',
  surfaces: [
    { identifier: 'W-POLY', kind: 'wall', story: 0, dimensions: { x: 4, y: 2.5, z: 0 }, transform: I4, polygonCorners: POLY },
    // no thickness -> must fall back to 0.16 and say so
    { identifier: 'W-THIN', kind: 'wall', story: 0, dimensions: { x: 3, y: 2.5, z: 0 }, transform: [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 1.25, 3, 1] },
    { identifier: 'F-1', kind: 'floor', story: 0, dimensions: { x: 4, y: 4, z: 0.05 }, transform: I4 },
    { identifier: 'D-1', kind: 'door', story: 0, dimensions: { x: 0.9, y: 2.1, z: 0.04 }, transform: I4, parentIdentifier: 'W-POLY' },
  ],
  objects: [{ identifier: 'O-1', category: 'sofa', dimensions: { x: 2, y: 0.8, z: 0.9 }, transform: I4 }],
  rooms: [{ identifier: 'R-1', label: 'Kuhinja/dnevni', story: 0, vertices: [{ x: 0, z: 0 }, { x: 4, z: 0 }, { x: 4, z: 4 }] }],
};

const fxUsda = buildUsda(fixtureCapture, {});
const polyUsda = buildUsda(polyCapture, {});
const fxText = fxUsda.text;
const polyText = polyUsda.text;
const usdzPath = path.join(TMP, 'fixture.usdz');
writeUsdz(usdzPath, Object.entries(fxUsda.files).map(([name, data]) => ({ name, data })));

/**
 * Minimal, independent parse of the archive layout: no zipfile, no library.
 * Reads the EOCD, walks the central directory and returns the payloads so the
 * offsets/CRCs on disk can be checked against what we think we wrote.
 */
function entryRanges(buf) {
  const entries = [];
  const eocd = buf.length - 22;
  assert.strictEqual(buf.readUInt32LE(eocd), 0x06054b50, 'EOCD signature missing at end of file');
  const count = buf.readUInt16LE(eocd + 10);
  let ptr = buf.readUInt32LE(eocd + 16);
  for (let i = 0; i < count; i += 1) {
    assert.strictEqual(buf.readUInt32LE(ptr), 0x02014b50, 'central directory signature missing');
    const method = buf.readUInt16LE(ptr + 10);
    const crc = buf.readUInt32LE(ptr + 16);
    const size = buf.readUInt32LE(ptr + 20);
    const nameLen = buf.readUInt16LE(ptr + 28);
    const extraLen = buf.readUInt16LE(ptr + 30);
    const local = buf.readUInt32LE(ptr + 42);
    const name = buf.slice(ptr + 46, ptr + 46 + nameLen).toString('utf8');
    const lNameLen = buf.readUInt16LE(local + 26);
    const lExtraLen = buf.readUInt16LE(local + 28);
    const dataOffset = local + 30 + lNameLen + lExtraLen;
    entries.push({ name, method, crc, size, dataOffset, local, data: buf.slice(dataOffset, dataOffset + size) });
    ptr += 46 + nameLen + extraLen;
  }
  return entries;
}

/* --------------------------------------------------------------- ZIP -- */

const zipBytes = fs.readFileSync(usdzPath);
const entries = entryRanges(zipBytes);

check('archive has exactly one entry: room.usda', () => {
  assert.deepStrictEqual(entries.map((e) => e.name), ['room.usda']);
});
check('every entry is STORED (method 0, no compression)', () => {
  for (const e of entries) assert.strictEqual(e.method, 0, `${e.name} uses method ${e.method}`);
});
check('every payload starts on a 64-byte boundary', () => {
  for (const e of entries) assert.strictEqual(e.dataOffset % 64, 0, `${e.name} data at ${e.dataOffset}`);
});
check('local CRC-32 matches our own crc32() and the payload bytes', () => {
  for (const e of entries) {
    assert.strictEqual(e.crc, crc32(e.data), `${e.name} CRC mismatch`);
    assert.strictEqual(e.data.length, e.size);
  }
});
check('crc32() matches known vectors', () => {
  assert.strictEqual(crc32(Buffer.from('')), 0);
  assert.strictEqual(crc32(Buffer.from('123456789')), 0xcbf43926);
  assert.strictEqual(crc32(Buffer.from('The quick brown fox jumps over the lazy dog')), 0x414fa339);
});
check('no Zip64 marker and no 4 GiB overflow', () => {
  assert(zipBytes.length < 0xffffffff);
  assert(!zipBytes.includes(Buffer.from([0x50, 0x4b, 0x06, 0x06])), 'Zip64 EOCD present');
});
check('an oversized entry is refused with a clear message', () => {
  // A 4 GiB+ payload must never be attempted: the guard is on the declared size.
  const fake = { name: 'big.usda', data: Buffer.alloc(0) };
  Object.defineProperty(fake.data, 'length', { value: 0x100000000 });
  assert.throws(() => buildUsdz([fake]), /4 GiB|Zip64/);
});
check('deterministic: two builds are byte-identical', () => {
  const a = buildUsdz(Object.entries(fxUsda.files).map(([name, data]) => ({ name, data })));
  const b = buildUsdz(Object.entries(buildUsda(decode(fs.readFileSync(FIXTURE, 'utf8')), {}).files).map(([name, data]) => ({ name, data })));
  assert(a.equals(b), 'HZIP differs between runs (timestamp not fixed?)');
});
check('DOS timestamp is fixed at 1980-01-01', () => {
  assert.strictEqual(zipBytes.readUInt16LE(entries[0].local + 10), 0, 'DOS time not zero');
  assert.strictEqual(zipBytes.readUInt16LE(entries[0].local + 12), 0x0021, 'DOS date not 1980-01-01');
});

/* -------------------------------------------------------- python zipfile -- */

const py = spawnSync('python3', ['-c', `
import json,sys,zipfile
p = sys.argv[1]
z = zipfile.ZipFile(p)
info = z.infolist()
out = {
  "namelist": z.namelist(),
  "testzip": z.testzip(),
  "methods": sorted({i.compress_type for i in info}),
  "date_time": [list(i.date_time) for i in info],
}
out["usda"] = z.read("room.usda").decode("utf-8")
print(json.dumps(out))
`, usdzPath], { encoding: 'utf8' });

let pyOut = null;
check('python3 zipfile opens the archive', () => {
  assert.strictEqual(py.status, 0, `python3 exited ${py.status}: ${py.stderr}`);
  pyOut = JSON.parse(py.stdout);
});
check('python zipfile lists room.usda', () => {
  assert.deepStrictEqual(pyOut.namelist, ['room.usda']);
});
check('python zipfile testzip() returns None (all CRCs valid)', () => {
  assert.strictEqual(pyOut.testzip, null, `testzip reported ${pyOut.testzip}`);
});
check('python sees STORE only and the 1980-01-01 timestamp', () => {
  assert.deepStrictEqual(pyOut.methods, [0]);
  for (const dt of pyOut.date_time) assert.deepStrictEqual(dt, [1980, 1, 1, 0, 0, 0]);
});
check('python reads back exactly the bytes we wrote', () => {
  assert.strictEqual(pyOut.usda, fxText);
});

/* ---------------------------------------------------------------- USDA -- */

check('layer starts with #usda 1.0', () => assert(/^#usda 1\.0\n/.test(fxText), fxText.slice(0, 20)));
check('metadata: defaultPrim room, metersPerUnit 1, upAxis Y', () => {
  assert(fxText.includes('defaultPrim = "room"'), 'defaultPrim');
  assert(fxText.includes('metersPerUnit = 1'), 'metersPerUnit');
  assert(fxText.includes('upAxis = "Y"'), 'upAxis');
});
check('scene tree: room > Section_grp + Mesh_grp', () => {
  assert(fxText.includes('def Xform "room"'));
  assert(fxText.includes('def Xform "Section_grp"'));
  assert(fxText.includes('def Xform "Mesh_grp"'));
  assert(fxText.indexOf('Section_grp') < fxText.indexOf('Mesh_grp'), 'section group must precede the mesh group');
});
check('one Section Xform per room, sanitised name, label kept in customData', () => {
  assert(polyText.includes('def Xform "Kuhinja_dnevni"'), 'room label not sanitised into an identifier');
  assert(polyText.includes('string Label = "Kuhinja/dnevni"'), 'original label lost');
  assert(fxText.includes('def Xform "room_1"'), 'raw capture without room records must still get a section stub');
});
check('sanitizeIdentifier keeps USD identifiers legal', () => {
  assert.strictEqual(sanitizeIdentifier('Kuhinja/dnevni', 'x'), 'Kuhinja_dnevni');
  assert.strictEqual(sanitizeIdentifier('1. kat', 'x'), 'r_1_kat');
  assert.strictEqual(sanitizeIdentifier('', 'room_2'), 'room_2');
});

const meshNames = (t) => [...t.matchAll(/def Mesh "([^"]+)"/g)].map((m) => m[1]);
check('fixture: 7 mesh prims (4 walls, 1 floor, 2 objects) + 2 empty opening Xforms', () => {
  // Openings carry NO mesh on purpose: a plate across a door or window hid the
  // hole the wall was cut for. They stay named, sized Xforms instead.
  assert.deepStrictEqual(meshNames(fxText).sort(), [
    'Floor_1', 'Object_1', 'Object_2', 'Wall_1', 'Wall_2', 'Wall_3', 'Wall_4',
  ]);
  assert(/def Xform "Door_1"/.test(fxText) && /def Xform "Window_1"/.test(fxText), 'opening prims must still exist');
  for (const name of ['Door_1', 'Window_1']) {
    const i = fxText.indexOf(`def Xform "${name}"`);
    const chunk = fxText.slice(i, fxText.indexOf('\n        }', i));
    assert(!/def Mesh/.test(chunk), `${name} must not carry a mesh (it would fill the opening)`);
  }
  assert.deepStrictEqual(fxUsda.summary.byCategory, {
    Room: 1, Wall: 4, Floor: 1, Door: 1, Window: 1, sofa: 1, table: 1,
  });
  assert.strictEqual(fxUsda.primCount, 9);
});
check('each element is a kind="component" Xform carrying customData Category + Identifier', () => {
  // Apple's shape: the leaf is an Xform (kind = "component") holding the Mesh
  // and its Material; customData sits in the prim's metadata block, never in
  // the body.
  // scan the layer line by line: a leaf is `        def Xform "X" (` …
  const lineArr = fxText.split('\n');
  const leaves = [];
  for (let i = 0; i < lineArr.length; i += 1) {
    const m = /^ {8}def Xform "(\w+)" \($/.exec(lineArr[i]);
    if (!m) continue;
    let j = i + 1;
    let meta = '';
    while (j < lineArr.length && lineArr[j] !== '        )') { meta += `${lineArr[j]}\n`; j += 1; }
    if (/kind = "component"/.test(meta)) leaves.push([null, m[1], meta]);
  }
  assert.strictEqual(leaves.length, 9, `expected 9 component Xforms, got ${leaves.length}`);
  const openings = new Set(['Door_1', 'Window_1']);
  for (const [, name, meta] of leaves) {
    assert(/string Category = "[^"]+"/.test(meta), `${name} has no Category`);
    assert(/string Identifier = "[^"]+"/.test(meta), `${name} has no Identifier`);
    if (openings.has(name)) {
      // An OPENING is a hole: named, sized, and deliberately free of geometry.
      assert(/string Role = "opening"/.test(meta), `${name} must declare Role = "opening"`);
      assert(/double Width = [\d.]+/.test(meta) && /double Height = [\d.]+/.test(meta), `${name} must carry Width and Height`);
      assert(!fxText.includes(`def Mesh "${name}"`), `${name} must not fill its own opening`);
      continue;
    }
    assert(`def Mesh "${name}"`.length && fxText.includes(`def Mesh "${name}"`), `${name} has no Mesh`);
    assert(fxText.includes(`def Material "${name}_color"`), `${name} has no Material`);
    assert(fxText.includes(`rel material:binding = </room/Mesh_grp/${name}/${name}_color>`), `${name} is not bound to its material`);
  }
  assert(fxText.includes('string Category = "Wall"') && fxText.includes('string Identifier = "W-A"'));
  // kind coverage, as Apple has it: root assembly, groups, leaf components
  assert(/def Xform "room" \(\n {4}kind = "assembly"/.test(fxText), 'root prim must be kind = "assembly"');
  assert(/def Xform "Section_grp" \(\n {8}kind = "group"/.test(fxText), 'Section_grp must be kind = "group"');
  assert(/def Xform "Mesh_grp" \(\n {8}kind = "group"/.test(fxText), 'Mesh_grp must be kind = "group"');
});
check('a box is 12 triangles over 36 split vertices (Apple triangulates, never quads)', () => {
  // W-C has no door or window pointing at it, so it stays a plain box; W-A and
  // W-B are cut by the fixture's door and window (see tests/test_wall_holes.js).
  const box = fxText.slice(fxText.indexOf('def Mesh "Wall_3"'));
  const body = box.slice(0, box.indexOf('def Mesh "Wall_4"'));
  const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1].split(',').map((s) => s.trim());
  assert.strictEqual(counts.length, 12, `expected 12 faces, got ${counts.length}`);
  assert(counts.every((c) => c === '3'), 'every face must be a triangle');
  const idx = /int\[\] faceVertexIndices = \[([\s\S]*?)\]/.exec(body)[1].split(',').map((s) => Number(s.trim()));
  assert.strictEqual(idx.length, 36, 'box indices');
  assert.deepStrictEqual(idx, [...Array(36).keys()], 'split vertices are indexed 0..35 in order');
  const pts = /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(/g);
  assert.strictEqual(pts.length, 36, `expected 36 points, got ${pts.length}`);
});
check('a wall with openings is cut, not a box: more faces, still all triangles', () => {
  for (const name of ['Wall_1', 'Wall_2']) {
    const body = fxText.slice(fxText.indexOf(`def Mesh "${name}"`));
    const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1].split(',').map((s) => Number(s.trim()));
    assert(counts.length > 12, `${name}: expected more than a box's 12 faces, got ${counts.length}`);
    assert(counts.every((c) => c === 3), `${name}: every face must be a triangle`);
    const idx = /int\[\] faceVertexIndices = \[([\s\S]*?)\]/.exec(body)[1].split(',').map((s) => Number(s.trim()));
    assert.deepStrictEqual(idx, [...Array(idx.length).keys()], 'split vertices are indexed in order');
  }
});
check('a polygonCorners WALL is a solid prism, not a paper sheet', () => {
  // A flat sheet disappears under backface culling as soon as you stand on the
  // other side of it, so a plan polygon is extruded through the thickness:
  // 2 cap faces + one side quad per polygon edge.
  const body = polyText.slice(polyText.indexOf('def Mesh "Wall_1"'));
  const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1].split(',').map((s) => Number(s.trim()));
  // 5 corners -> 3 cap triangles per side + 5 side quads, each quad split into
  // 2 triangles by the triangulator: 2*(n-2) + 2*n triangles in the file.
  assert.strictEqual(counts.length, 2 * (POLY.length - 2) + 2 * POLY.length, `faces ${counts.length}`);
  assert(counts.every((c) => c === 3), 'every emitted face is a triangle');
  assert(polyText.includes('string Geometry = "polygonCorners extruded through the thickness (prism)"'));
  assert(polyText.includes('double Volume = '), 'prism must report its volume');
});
check('a polygonCorners FLOOR stays a flat fan of n-2 triangles', () => {
  const flat = {
    surfaces: [{ identifier: 'F-P', kind: 'floor', story: 0, dimensions: { x: 4, y: 3, z: 0 }, transform: I4, polygonCorners: [[0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0]] }],
    objects: [],
    rooms: [],
  };
  const res = buildUsda(flat, {});
  const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(res.text)[1].split(',').map((s) => Number(s.trim()));
  assert.strictEqual(counts.length, 2, 'a floor polygon is not extruded');
  assert(res.text.includes('string Geometry = "source polygonCorners"'));
  assert.strictEqual(res.summary.prisms.walls, 0);
});
check('polygon corners are transformed to world space', () => {
  // shift the polygon wall by +10 in x and check the emitted points moved
  const shifted = JSON.parse(JSON.stringify(polyCapture));
  shifted.surfaces[0].transform = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 0, 0, 1];
  const t = buildUsda(shifted, {}).text;
  // the prism puts the polygon at z = -0.08 and +0.08, so look for the caps
  assert(t.includes('(8.000000, 0.000000, -0.080000)'), 'world x 2+10 missing on the front cap');
  const body = t.slice(t.indexOf('def Mesh "Wall_1"'));
  const pts = /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(([^)]*)\)/g);
  const xs = pts.map((p) => Number(p.slice(1, -1).split(',')[0]));
  assert.strictEqual(Math.min(...xs), 8, `local x leaked: min x = ${Math.min(...xs)}`);
  assert.strictEqual(Math.max(...xs), 12, `expected +10 shift, max x = ${Math.max(...xs)}`);
});
check('an unmeasured wall gets 0.16 m and is flagged assumed', () => {
  assert(polyText.includes('string Thickness = "assumed"'), 'assumed thickness not flagged');
  assert(polyText.includes('double AssumedThickness = 0.160000'), 'default value not recorded');
  // thickness 0.16 centred on the centreline -> z extent +-0.08
  assert(/-0\.0?80000\).*|0\.080000/.test(polyText), 'box depth does not reflect 0.16 m');
  // a wall that DID carry a thickness must not be flagged
  const withT = buildUsda(fixtureCapture, { thickness: 0.2 }).text;
  assert(withT.includes('string Thickness = "assumed"'), 'fixture walls have z = 0 so they must be assumed');
  assert(withT.includes('double AssumedThickness = 0.200000'), 'thickness option ignored');
});
check('numbers: fixed 6 decimals, dot separator, no NaN/Infinity', () => {
  for (const [label, text] of [['fixture', fxText], ['polygon', polyText]]) {
    assert(!/NaN|Infinity|null/.test(text.replace(/"(?:[^"\\]|\\.)*"/g, '""')), `${label}: non-finite token in layer`);
    // "#usda 1.0" is the format version, not a geometric number. Quoted
    // customData strings are labels (e.g. string Height = "2.50"), not
    // geometry: strip them before the number scan, after the NaN scan above.
    const body = text.replace(/^#usda 1\.0/, '#usda').replace(/"(?:[^"\\]|\\.)*"/g, '""');
    const nums = body.match(/[-\d]*\.[\d]+/g) || [];
    assert(nums.length > 0);
    for (const n of nums) assert(/^-?\d+\.\d{6}$/.test(n), `${label}: ${n} is not 6-decimal`);
  }
  assert(!/,\d{1,6}\s*[,)]/.test(''), 'noop');
  assert(!/\d,\d{3}/.test(fxText.replace(/"(?:[^"\\]|\\.)*"/g, '""')), 'comma decimal separator found');
});
check('a primitive with a bad transform is skipped with a warning, not written as NaN', () => {
  const broken = JSON.parse(JSON.stringify(polyCapture));
  broken.surfaces[1].transform = [1, 0, 0, 0, 0, Number.NaN, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const res = buildUsda(broken, {});
  // No covering measured polygon/supplied datum: no invented ceiling at stage 0.
  assert.strictEqual(res.primCount, 4, 'broken wall and undatumed reconstructed ceiling omitted');
  const skipped = res.warnings.filter((w) => w.code === 'usdz.skipped-non-rigid');
  assert.strictEqual(skipped.length, 1);
  // the polygon wall the door names cannot be cut either, and says so
  assert(res.warnings.every((w) => ['usdz.skipped-non-rigid', 'usdz.opening-not-cut', 'usdz.opening-hole-only', 'usdz.ceiling-height-unknown'].includes(w.code)),
    JSON.stringify(res.warnings.map((w) => w.code)));
  assert(!/NaN/.test(res.text));
});
check('a surface with no geometry at all is skipped with a warning', () => {
  const empty = JSON.parse(JSON.stringify(polyCapture));
  empty.surfaces[2] = { identifier: 'F-BAD', kind: 'floor', story: 0, dimensions: { x: 0, y: 0, z: 0 }, transform: I4 };
  const res = buildUsda(empty, {});
  assert(res.warnings.some((w) => w.code === 'usdz.skipped-no-geometry'));
  assert(res.warnings.some((w) => w.code === 'usdz.ceiling-height-unknown'));
  assert.strictEqual(res.primCount, 4);
});
check('normals: one per point, no interpolation metadata (Apple shape)', () => {
  // Apple writes a normal for every point and relies on USD's default
  // "vertex" interpolation; "interpolation = faceVarying" appears in none of
  // the 105 reference layers, so we do not write it either.
  assert(!/interpolation/.test(fxText), 'no attribute metadata is emitted');
  for (const name of ['Wall_1', 'Wall_2', 'Floor_1']) {
    const body = fxText.slice(fxText.indexOf(`def Mesh "${name}"`));
    const normals = /normal3f\[\] normals = \[([\s\S]*?)\]\n/.exec(body);
    assert(normals, `${name}: no normals`);
    const points = /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body);
    assert.strictEqual(normals[1].match(/\(/g).length, points[1].match(/\(/g).length, `${name}: normals/points count mismatch`);
  }
});

check('the layer passes usda-lint: grammar + semantics, zero warnings', () => {
  const { lint } = require(path.join(__dirname, 'lib', 'usda-lint'));
  for (const [label, text] of [['fixture', fxText], ['polygon', polyText]]) {
    const r = lint(text, { name: `${label}.usda` });
    assert.deepStrictEqual(r.errors, [], `${label}: ${JSON.stringify(r.errors, null, 2)}`);
    assert.deepStrictEqual(r.warnings, [], `${label}: ${JSON.stringify(r.warnings, null, 2)}`);
    assert.strictEqual(r.header.defaultPrim, 'room');
    assert.strictEqual(r.header.metersPerUnit, 1);
    assert.strictEqual(r.header.upAxis, 'Y');
    assert.strictEqual(r.stats.meshes, r.stats.materials, 'every mesh needs its own Material');
  }
});

check('usda-lint rejects the shapes Apple never writes', () => {
  const { lint } = require(path.join(__dirname, 'lib', 'usda-lint'));
  const good = fxText;
  const bad = (mutate) => {
    const r = lint(mutate(good), { name: 'bad.usda' });
    assert(!r.ok || r.warnings.length > 0, 'mutated layer passed cleanly');
    return r;
  };
  // interpolation on a scalar attribute is a scope error
  assert(bad((t) => t.replace('uniform token subdivisionScheme = "none"', 'uniform token subdivisionScheme ( interpolation = "vertex" ) = "none"')).errors.some((e) => e.code === 'META_INTERPOLATION_SCOPE'));
  // a normals array whose length contradicts the points array
  assert(bad((t) => t.replace('normal3f[] normals = [(', 'normal3f[] normals = [(1, 1, 1), (')).errors.some((e) => e.code === 'MESH_NORMALS_LENGTH'));
  // index out of range is an error, never a warning
  assert(bad((t) => t.replace('int[] faceVertexIndices = [0, 1, 2', 'int[] faceVertexIndices = [99999, 1, 2')).errors.some((e) => e.code === 'MESH_INDEX_RANGE'));
  // defaultPrim that names nothing
  assert(bad((t) => t.replace('defaultPrim = "room"', 'defaultPrim = "nope"')).errors.some((e) => e.code === 'META_DEFAULTPRIM_MISSING'));
  // an unresolved material binding
  assert(bad((t) => t.replace('rel material:binding = </room/Mesh_grp/Wall_1/Wall_1_color>', 'rel material:binding = </room/Mesh_grp/Wall_1/ghost>')).errors.some((e) => e.code === 'REL_UNRESOLVED'));
  // duplicate sibling prim names
  assert(bad((t) => t.replace('def Xform "Wall_2" (', 'def Xform "Wall_1" (')).errors.some((e) => e.code === 'PRIM_DUPLICATE_SIBLING'));
  // a truncated array must be a syntax error with a line number
  const broken = lint(fxText.replace('int[] faceVertexCounts = [3, 3', 'int[] faceVertexCounts = [3, 3, , 3'), { name: 'broken.usda' });
  assert(!broken.ok);
  for (const e of broken.errors) assert(e.line > 0, 'every error must carry a line number');
});

/* ----------------------------------------------------------------- CLI -- */

const outDir = path.join(TMP, 'cli');
const cli = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, outDir, '--usdz', '--usdz-ceilings', '--no-place-lookup'], { encoding: 'utf8' });
check('CLI: --usdz writes <name>.usdz and exits 0', () => {
  assert.strictEqual(cli.status, 0, `exit ${cli.status}: ${cli.stderr}`);
  assert(fs.existsSync(path.join(outDir, 'scan.usdz')), 'file missing');
  assert(/USDZ written: .*scan\.usdz \(9 prims\)/.test(cli.stdout), cli.stdout);
});
check('CLI: the room.usda inside the written archive passes usda-lint', () => {
  const buf = fs.readFileSync(path.join(outDir, 'scan.usdz'));
  const es = entryRanges(buf);
  const entry = es.find((e) => e.name === 'room.usda');
  const text = buf.slice(entry.dataOffset, entry.dataOffset + entry.size).toString('utf8');
  const { lint } = require(path.join(__dirname, 'lib', 'usda-lint'));
  const r = lint(text, { name: 'room.usda' });
  assert.deepStrictEqual(r.errors, []);
  assert.deepStrictEqual(r.warnings, []);
});
check('CLI: the written .usdz is a valid ZIP with room.usda', () => {
  const buf = fs.readFileSync(path.join(outDir, 'scan.usdz'));
  const es = entryRanges(buf);
  assert.deepStrictEqual(es.map((e) => e.name), ['room.usda']);
  assert.strictEqual(es[0].dataOffset % 64, 0);
  assert.strictEqual(es[0].crc, crc32(es[0].data));
});
check('CLI: --usdz works on its own and is idempotent on a forced second run', () => {
  const before = fs.readFileSync(path.join(outDir, 'scan.usdz'));
  const again = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, outDir, '--usdz', '--usdz-ceilings', '--no-place-lookup', '--force'], { encoding: 'utf8' });
  assert.strictEqual(again.status, 0, again.stderr);
  const after = fs.readFileSync(path.join(outDir, 'scan.usdz'));
  assert.strictEqual(after.length, before.length);
  assert(after.equals(before), 'output changed between identical runs');
});
check('CLI: overwrite protection covers the .usdz', () => {
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, outDir, '--usdz', '--usdz-ceilings', '--no-place-lookup'], { encoding: 'utf8' });
  // The second run without --force must refuse for every target, .usdz included.
  assert.notStrictEqual(res.status, 0, 'a second run without --force overwrote outputs');
  assert(/Refusing to overwrite/.test(res.stderr + res.stdout), `unexpected error: ${res.stderr}`);
});
check('CLI: --usdz combined with --report/--md writes all four outputs', () => {
  const dir = path.join(TMP, 'cli-all');
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, dir, '--usdz', '--usdz-ceilings', '--no-place-lookup', '--md'], { encoding: 'utf8' });
  assert.strictEqual(res.status, 0, res.stderr);
  for (const f of ['scan.dxf', 'scan.roomplan.json', 'scan.report.json', 'scan.md', 'scan.usdz']) {
    assert(fs.existsSync(path.join(dir, f)), `${f} missing`);
  }
});
check('CLI: skipped prims reach the manifest warnings', () => {
  // A zero-width wall decodes fine (it is present in the capture) but cannot be
  // turned into geometry; the export must say so in the manifest, not silently drop it.
  const opt = optimizedCapture();
  opt.walls[0].dimensions = [0, 2.5, 0.1];
  const broken = path.join(TMP, 'zero.json');
  fs.writeFileSync(broken, JSON.stringify(opt));
  const dir = path.join(TMP, 'cli-zero');
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), broken, dir, '--usdz', '--usdz-ceilings', '--no-place-lookup'], { encoding: 'utf8' });
  assert.strictEqual(res.status, 0, res.stderr);
  const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'zero.roomplan.json'), 'utf8'));
  assert((manifest.warnings || []).some((w) => w.code === 'usdz.skipped-no-geometry'), 'warning not recorded in the manifest');
});
check('CLI: optimized capture -> one Section Xform per room label', () => {
  // USDZ ceilings are OFF by default: 2 walls + 1 floor = 3 meshes, no ceiling.
  const dir = path.join(TMP, 'cli-opt-default');
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), OPT_FIXTURE, dir, '--usdz', '--no-place-lookup'], { encoding: 'utf8' });
  assert.strictEqual(res.status, 0, res.stderr);
  const text = entryRanges(fs.readFileSync(path.join(dir, 'opt.usdz')))[0].data.toString('utf8');
  assert(text.includes('def Xform "Kuhinja"'), 'room label missing as a section');
  assert(text.includes('string Label = "Kuhinja"'), 'source label must survive sanitising');
  assert.strictEqual((text.match(/def Mesh /g) || []).length, 3, 'default USDZ must not emit a ceiling mesh');
  assert(!text.includes('Category = "Ceiling"'), 'USDZ ceiling default must be OFF');
  assert(text.includes('string Geometry = "source polygonCorners"'), 'optimized floor polygon not exported');
});
check('CLI: --usdz-ceilings opts the optimized room ceiling back in', () => {
  const dir = path.join(TMP, 'cli-opt-ceilings');
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), OPT_FIXTURE, dir, '--usdz', '--usdz-ceilings', '--no-place-lookup'], { encoding: 'utf8' });
  assert.strictEqual(res.status, 0, res.stderr);
  const text = entryRanges(fs.readFileSync(path.join(dir, 'opt.usdz')))[0].data.toString('utf8');
  // 2 walls + 1 floor + 1 ceiling mesh
  assert.strictEqual((text.match(/def Mesh /g) || []).length, 4, 'opt-in must add exactly the ceiling mesh');
  assert(text.includes('Category = "Ceiling"'), 'the opt-in ceiling must be in the USDZ');
});

fs.rmSync(TMP, { recursive: true, force: true });
console.log(`usdz: ${checks} checks passed`);
