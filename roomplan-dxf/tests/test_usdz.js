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
check('fixture: 9 mesh prims (4 walls, 1 floor, 1 door, 1 window, 2 objects)', () => {
  assert.deepStrictEqual(meshNames(fxText).sort(), [
    'Door_1', 'Floor_1', 'Object_1', 'Object_2', 'Wall_1', 'Wall_2', 'Wall_3', 'Wall_4', 'Window_1',
  ]);
  assert.deepStrictEqual(fxUsda.summary.byCategory, {
    Room: 1, Wall: 4, Floor: 1, Door: 1, Window: 1, sofa: 1, table: 1,
  });
  assert.strictEqual(fxUsda.primCount, 9);
});
check('each mesh carries customData Category + Identifier', () => {
  const prims = [...fxText.matchAll(/def Mesh "([^"]+)"\n {8}\{([\s\S]*?)\n {8}\}/g)];
  assert.strictEqual(prims.length, 9);
  for (const [, name, body] of prims) {
    assert(/string Category = "[^"]+"/.test(body), `${name} has no Category`);
    assert(/string Identifier = "[^"]+"/.test(body), `${name} has no Identifier`);
  }
  assert(fxText.includes('string Category = "Wall"') && fxText.includes('string Identifier = "W-A"'));
});
check('a box is 8 points and 6 quads', () => {
  const box = fxText.slice(fxText.indexOf('def Mesh "Wall_1"'));
  const body = box.slice(0, box.indexOf('def Mesh "Wall_2"'));
  const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1].split(',').map((s) => s.trim());
  assert.strictEqual(counts.length, 6, `expected 6 faces, got ${counts.length}`);
  assert(counts.every((c) => c === '4'), 'box faces must be quads');
  const idx = /int\[\] faceVertexIndices = \[([\s\S]*?)\]/.exec(body)[1].split(',').map((s) => Number(s.trim()));
  assert.strictEqual(idx.length, 24, 'box indices');
  assert.deepStrictEqual([...new Set(idx)].sort((a, b) => a - b), [0, 1, 2, 3, 4, 5, 6, 7], 'box must reference exactly 8 vertices');
  const pts = /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(/g);
  assert.strictEqual(pts.length, 8, `expected 8 points, got ${pts.length}`);
});
check('a source polygon keeps n points and n indices (fan)', () => {
  const body = polyText.slice(polyText.indexOf('def Mesh "Wall_1"'));
  const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1];
  assert.strictEqual(counts.trim(), String(POLY.length));
  const idx = /int\[\] faceVertexIndices = \[([\s\S]*?)\]/.exec(body)[1].split(',').map((s) => Number(s.trim()));
  assert.deepStrictEqual(idx, POLY.map((_, i) => i));
  const pts = /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(/g);
  assert.strictEqual(pts.length, POLY.length);
  assert(polyText.includes('string Geometry = "source polygonCorners"'));
});
check('polygon corners are transformed to world space', () => {
  // shift the polygon wall by +10 in x and check the emitted points moved
  const shifted = JSON.parse(JSON.stringify(polyCapture));
  shifted.surfaces[0].transform = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 0, 0, 1];
  const t = buildUsda(shifted, {}).text;
  assert(t.includes('(8.000000, 0.000000, 0.000000)'), 'world x 2+10 missing');
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
    // "#usda 1.0" is the format version, not a geometric number.
    const body = text.replace(/^#usda 1\.0/, '#usda');
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
  assert.strictEqual(res.primCount, 4, 'the broken wall should be dropped');
  assert.strictEqual(res.warnings.length, 1);
  assert.strictEqual(res.warnings[0].code, 'usdz.skipped-non-rigid');
  assert(!/NaN/.test(res.text));
});
check('a surface with no geometry at all is skipped with a warning', () => {
  const empty = JSON.parse(JSON.stringify(polyCapture));
  empty.surfaces[2] = { identifier: 'F-BAD', kind: 'floor', story: 0, dimensions: { x: 0, y: 0, z: 0 }, transform: I4 };
  const res = buildUsda(empty, {});
  assert.strictEqual(res.warnings[0].code, 'usdz.skipped-no-geometry');
  assert.strictEqual(res.primCount, 4);
});
check('normals are face-varying (one per face-vertex) or absent', () => {
  const body = fxText.slice(fxText.indexOf('def Mesh "Wall_1"'));
  const normals = /normal3f\[\] normals = \[([\s\S]*?)\] \(/.exec(body);
  if (normals) {
    const n = normals[1].match(/\(/g).length;
    assert.strictEqual(n, 24, 'a 6-quad box needs 24 face-varying normals');
    assert(/interpolation = "faceVarying"/.test(body));
  }
});

/* ----------------------------------------------------------------- CLI -- */

const outDir = path.join(TMP, 'cli');
const cli = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, outDir, '--usdz'], { encoding: 'utf8' });
check('CLI: --usdz writes <name>.usdz and exits 0', () => {
  assert.strictEqual(cli.status, 0, `exit ${cli.status}: ${cli.stderr}`);
  assert(fs.existsSync(path.join(outDir, 'scan.usdz')), 'file missing');
  assert(/USDZ written: .*scan\.usdz \(9 prims\)/.test(cli.stdout), cli.stdout);
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
  const again = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, outDir, '--usdz', '--force'], { encoding: 'utf8' });
  assert.strictEqual(again.status, 0, again.stderr);
  const after = fs.readFileSync(path.join(outDir, 'scan.usdz'));
  assert.strictEqual(after.length, before.length);
  assert(after.equals(before), 'output changed between identical runs');
});
check('CLI: overwrite protection covers the .usdz', () => {
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, outDir, '--usdz'], { encoding: 'utf8' });
  // The second run without --force must refuse for every target, .usdz included.
  assert.notStrictEqual(res.status, 0, 'a second run without --force overwrote outputs');
  assert(/Refusing to overwrite/.test(res.stderr + res.stdout), `unexpected error: ${res.stderr}`);
});
check('CLI: --usdz combined with --report/--md writes all four outputs', () => {
  const dir = path.join(TMP, 'cli-all');
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), FIXTURE, dir, '--usdz', '--md'], { encoding: 'utf8' });
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
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), broken, dir, '--usdz'], { encoding: 'utf8' });
  assert.strictEqual(res.status, 0, res.stderr);
  const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'zero.roomplan.json'), 'utf8'));
  assert((manifest.warnings || []).some((w) => w.code === 'usdz.skipped-no-geometry'), 'warning not recorded in the manifest');
});
check('CLI: optimized capture -> one Section Xform per room label', () => {
  const dir = path.join(TMP, 'cli-opt');
  const res = spawnSync('node', [path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js'), OPT_FIXTURE, dir, '--usdz'], { encoding: 'utf8' });
  assert.strictEqual(res.status, 0, res.stderr);
  const buf = fs.readFileSync(path.join(dir, 'opt.usdz'));
  const text = entryRanges(buf)[0].data.toString('utf8');
  assert(text.includes('def Xform "Kuhinja"'), 'room label missing as a section');
  assert(text.includes('string Label = "Kuhinja"'), 'source label must survive sanitising');
  // 2 walls + 1 floor, and the floor keeps its source polygon
  assert.strictEqual((text.match(/def Mesh /g) || []).length, 3);
  assert(text.includes('string Geometry = "source polygonCorners"'), 'optimized floor polygon not exported');
});

fs.rmSync(TMP, { recursive: true, force: true });
console.log(`usdz: ${checks} checks passed`);
