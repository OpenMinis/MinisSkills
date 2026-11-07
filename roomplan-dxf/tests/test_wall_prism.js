'use strict';
/**
 * tests/test_wall_prism.js — a wall given as `polygonCorners` is a SOLID, not a
 * sheet.
 *
 * RoomPlan/Polycam describe some walls only by their plan outline: a flat,
 * closed polygon in the surface's local plane (z = 0, 4-7 corners). Emitting
 * that as one flat face makes the wall look like paper — and because USD/Reality
 * Kit cull backfaces, the wall is INVISIBLE from the far side, which is exactly
 * the "two pieces of wall are missing from outside" a client sees in AR Quick
 * Look. So the polygon is extruded along the surface's local +Z through the
 * thickness: two caps plus one quad per polygon edge.
 *
 * Everything here is measured from the emitted triangles:
 *   - surface area = 2*area(polygon) + perimeter*thickness (1e-4);
 *   - signed volume from the winding = area(polygon)*thickness (> 0);
 *   - every directed edge appears once with its twin (closed, consistently
 *     oriented), so no face can be inside out or missing;
 *   - a concave (L-shaped) plan polygon must be ear-clipped: a fan would give a
 *     wrong area and overlap itself.
 */
const assert = require('assert');
const path = require('path');

const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const { buildUsda } = require(path.join(LIB, 'usda-export'));
const { prismGeometry, polygonArea2D, earClip } = require(path.join(LIB, 'polygon-prism'));
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

const I4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const T = (x, y, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1];

function meshes(text) {
  const out = {};
  for (const chunk of text.split('def Mesh "').slice(1)) {
    const name = /^([^"]+)"/.exec(chunk)[1];
    const body = chunk.slice(0, chunk.indexOf('uniform token subdivisionScheme'));
    out[name] = {
      points: /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(([^)]*)\)/g)
        .map((p) => p.slice(1, -1).split(',').map(Number)),
      normals: /normal3f\[\] normals = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(([^)]*)\)/g)
        .map((p) => p.slice(1, -1).split(',').map(Number)),
      counts: /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1].split(',').map((s) => Number(s.trim())),
      indices: /int\[\] faceVertexIndices = \[([\s\S]*?)\]/.exec(body)[1].split(',').map((s) => Number(s.trim())),
    };
  }
  return out;
}
function triangles(mesh) {
  const tris = [];
  let base = 0;
  for (const count of mesh.counts) {
    const idx = mesh.indices.slice(base, base + count);
    base += count;
    for (let i = 1; i < idx.length - 1; i += 1) tris.push([mesh.points[idx[0]], mesh.points[idx[i]], mesh.points[idx[i + 1]]]);
  }
  return tris;
}
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const norm = (a) => Math.hypot(a[0], a[1], a[2]);

function totalArea(mesh) {
  let a = 0;
  for (const t of triangles(mesh)) a += norm(cross(sub(t[1], t[0]), sub(t[2], t[0]))) / 2;
  return a;
}
function signedVolume(mesh) {
  let v = 0;
  for (const t of triangles(mesh)) v += dot(t[0], cross(t[1], t[2])) / 6;
  return v;
}
function edgeAudit(mesh) {
  const ids = new Map();
  const welded = mesh.points.map((p) => {
    const k = p.map((v) => v.toFixed(6)).join(',');
    if (!ids.has(k)) ids.set(k, ids.size);
    return ids.get(k);
  });
  const seen = new Map();
  let base = 0;
  for (const count of mesh.counts) {
    const idx = mesh.indices.slice(base, base + count).map((i) => welded[i]);
    base += count;
    for (let i = 0; i < idx.length; i += 1) {
      const k = `${idx[i]}>${idx[(i + 1) % idx.length]}`;
      seen.set(k, (seen.get(k) || 0) + 1);
    }
  }
  for (const [k, n] of seen) {
    assert.strictEqual(n, 1, `directed edge ${k} appears ${n}x`);
    const [a, b] = k.split('>');
    assert(seen.has(`${b}>${a}`), `open boundary edge ${k}`);
  }
}
function perimeter(poly) {
  let p = 0;
  for (let i = 0; i < poly.length; i += 1) {
    const a = poly[i];
    const b = poly[(i + 1) % poly.length];
    p += Math.hypot(b[0] - a[0], b[1] - a[1]);
  }
  return p;
}

/* ---------------------------------------------------------- fixtures ---- */

/** 4 x 2.5 rectangle wall outline, 5 corners, thickness 0.2. */
const RECT = [[-2, 0, 0], [2, 0, 0], [2, 2.5, 0], [-2, 2.5, 0]];

/** Concave L-shaped wall outline (6 corners), area 6.0 m2, perimeter 13 m. */
const LSHAPE = [
  [0, 0, 0], [3, 0, 0], [3, 1, 0], [1.5, 1, 0], [1.5, 3, 0], [0, 3, 0],
];

function wallPolygon(corners, extra) {
  return Object.assign({
    identifier: 'W-P',
    kind: 'wall',
    story: 0,
    dimensions: { x: 4, y: 2.5, z: 0 },
    transform: I4,
    wallThickness: 0.2,
    polygonCorners: corners,
  }, extra || {});
}
function layer(surfaces, options) {
  const res = buildUsda({ surfaces, objects: [], rooms: [] }, options || {});
  return { res, text: res.text, m: meshes(res.text) };
}

/* ------------------------------------------------------------ 1: area --- */

check('a rectangular polygon wall is a prism: area = 2A + P*T, volume = A*T', () => {
  const { res, text, m } = layer([wallPolygon(RECT)]);
  assert.deepStrictEqual(res.warnings, []);
  const T0 = 0.2;
  const A = polygonArea2D(RECT.map((p) => [p[0], p[1]]));
  const P = perimeter(RECT);
  assert(Math.abs(A - 10) < 1e-12);
  assert(Math.abs(P - 13) < 1e-12);
  const area = totalArea(m.Wall_1);
  assert(Math.abs(area - (2 * A + P * T0)) < 1e-4, `surface area ${area} != ${2 * A + P * T0}`);
  const vol = signedVolume(m.Wall_1);
  assert(Math.abs(vol - A * T0) < 1e-6, `signed volume ${vol} != ${A * T0}`);
  assert(vol > 0, 'volume must be positive: normals point out, not in');
  edgeAudit(m.Wall_1);
  // 4 caps triangles (2 per side) + 4 side quads -> 4 + 8 triangles in the file
  assert.strictEqual(m.Wall_1.counts.length, 2 * (RECT.length - 2) + 2 * RECT.length);
  assert(text.includes('string Geometry = "polygonCorners extruded through the thickness (prism)"'));
  assert(text.includes(`double Volume = ${(A * T0).toFixed(6)}`), 'volume not reported in customData');
  assert(text.includes(`double SurfaceArea = ${(2 * A + P * T0).toFixed(6)}`), 'surface area not reported');
});

check('a concave L-shaped wall is ear-clipped, not fanned: area and volume stay right', () => {
  const { m } = layer([wallPolygon(LSHAPE)]);
  const A = polygonArea2D(LSHAPE.map((p) => [p[0], p[1]]));
  const P = perimeter(LSHAPE);
  assert(Math.abs(A - 6) < 1e-12, `polygon area ${A}`);
  assert(Math.abs(totalArea(m.Wall_1) - (2 * A + P * 0.2)) < 1e-4, `surface area ${totalArea(m.Wall_1)}`);
  // a fan over this 6-gon would give 2*? -> prove the volume is the polygon's
  assert(Math.abs(signedVolume(m.Wall_1) - A * 0.2) < 1e-6, `volume ${signedVolume(m.Wall_1)}`);
  edgeAudit(m.Wall_1);
  // no triangle may sit outside the polygon footprint
  for (const t of triangles(m.Wall_1)) {
    for (const p of t) {
      assert(p[0] >= -1e-9 && p[0] <= 3 + 1e-9 && p[1] >= -1e-9 && p[1] <= 3 + 1e-9, `point outside the plan: ${p}`);
    }
  }
});

check('ear clipping: every triangle is inside the L-shape (the notch is not filled)', () => {
  const tris = earClip(LSHAPE.map((p) => [p[0], p[1]]));
  assert.strictEqual(tris.length, LSHAPE.length - 2, `expected n-2 ears, got ${tris.length}`);
  let area = 0;
  for (const [a, b, c] of tris) {
    const A = LSHAPE[a];
    const B = LSHAPE[b];
    const C = LSHAPE[c];
    area += Math.abs((B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])) / 2;
    const cx = (A[0] + B[0] + C[0]) / 3;
    const cy = (A[1] + B[1] + C[1]) / 3;
    const inNotch = cx > 1.5 && cy > 1; // the missing corner of the L
    assert(!inNotch, `triangle centroid (${cx}, ${cy}) lies in the notch`);
  }
  assert(Math.abs(area - 6) < 1e-12, `triangulated area ${area}`);
});

check('winding does not matter: a clockwise outline gives the same solid', () => {
  const ccw = layer([wallPolygon(RECT)]);
  const cw = layer([wallPolygon(RECT.slice().reverse())]);
  assert(Math.abs(totalArea(cw.m.Wall_1) - totalArea(ccw.m.Wall_1)) < 1e-4);
  assert(Math.abs(signedVolume(cw.m.Wall_1) - signedVolume(ccw.m.Wall_1)) < 1e-6);
  assert(signedVolume(cw.m.Wall_1) > 0, 'a reversed outline must not turn the solid inside out');
  edgeAudit(cw.m.Wall_1);
});

/* ---------------------------------------------------- 2: thickness ------ */

check('thickness: dimensions.z wins, then wallThickness, then 0.16 assumed', () => {
  const withDim = layer([wallPolygon(RECT, { dimensions: { x: 4, y: 2.5, z: 0.3 } })]);
  assert(Math.abs(signedVolume(withDim.m.Wall_1) - 10 * 0.3) < 1e-6);
  assert(withDim.text.includes('double Thickness = 0.300000'));
  assert(!withDim.text.includes('string Thickness = "assumed"'));

  const withSource = layer([wallPolygon(RECT)]);
  assert(Math.abs(signedVolume(withSource.m.Wall_1) - 10 * 0.2) < 1e-6, 'wallThickness ignored');
  assert(withSource.text.includes('double Thickness = 0.200000'));

  const nothing = layer([wallPolygon(RECT, { wallThickness: null })]);
  assert(Math.abs(signedVolume(nothing.m.Wall_1) - 10 * 0.16) < 1e-6, 'default 0.16 not applied');
  assert(nothing.text.includes('string Thickness = "assumed"'), 'the default must be flagged assumed');
});

/* ------------------------------------------------------- 3: refusals ----- */

check('a polygon that is not a plan outline is left flat, with a warning', () => {
  // a polygon standing in the local XZ plane cannot be extruded along +Z
  const slanted = layer([wallPolygon([[0, 0, 0], [2, 0, 0], [2, 0, 2], [0, 0, 2]])]);
  assert(slanted.res.warnings.some((w) => w.code === 'usdz.polygon-not-extruded'), 'missing usdz.polygon-not-extruded');
  assert(Math.abs(signedVolume(slanted.m.Wall_1)) < 1e-9, 'a refused wall must stay a zero-thickness sheet');
});

check('a floor polygon is NOT extruded (floors have no thickness to give)', () => {
  const { res, m } = layer([{
    identifier: 'F-1', kind: 'floor', story: 0, dimensions: { x: 4, y: 3, z: 0 }, transform: I4,
    polygonCorners: [[0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0]],
  }]);
  assert.strictEqual(res.summary.prisms.walls, 0);
  assert(Math.abs(signedVolume(m.Floor_1)) < 1e-9);
  assert.strictEqual(m.Floor_1.counts.length, 2, 'a floor stays an n-2 fan');
});

/* ------------------------------------------------ 4: whole capture ------ */

check('every wall of a mixed capture has a volume greater than zero', () => {
  const surfaces = [
    wallPolygon(RECT, { identifier: 'W-POLY' }),
    wallPolygon(LSHAPE, { identifier: 'W-L', transform: T(10, 0, 0) }),
    { identifier: 'W-BOX', kind: 'wall', story: 0, dimensions: { x: 5, y: 2.5, z: 0.12 }, transform: T(0, 1.25, 6) },
    { identifier: 'W-NOTHICK', kind: 'wall', story: 0, dimensions: { x: 3, y: 2.5, z: 0 }, transform: T(0, 1.25, 9) },
    { identifier: 'F-1', kind: 'floor', story: 0, dimensions: { x: 8, y: 8, z: 0.05 }, transform: T(0, 0, 3) },
    { identifier: 'D-1', kind: 'door', story: 0, dimensions: { x: 0.9, y: 2.1, z: 0.05 }, transform: T(2.5, 1.05, 6), parentIdentifier: 'W-BOX' },
  ];
  const { res, m } = layer(surfaces);
  const walls = Object.keys(m).filter((n) => /^Wall_/.test(n));
  assert.strictEqual(walls.length, 4);
  for (const name of walls) {
    const v = signedVolume(m[name]);
    assert(v > 0, `${name} has volume ${v}: a wall without volume is invisible from one side`);
    edgeAudit(m[name]);
  }
  assert.strictEqual(res.summary.prisms.walls, 2, 'both polygon walls must be extruded');
  // the box wall was cut by its door, the polygon walls were not (and said so)
  assert.strictEqual(res.summary.holes.wallsCut, 1);
});

check('every generated layer still passes usda-lint with zero errors and warnings', () => {
  const cases = {
    rect: [wallPolygon(RECT)],
    lshape: [wallPolygon(LSHAPE)],
    reversed: [wallPolygon(RECT.slice().reverse())],
    mixed: [
      wallPolygon(RECT),
      { identifier: 'W-BOX', kind: 'wall', story: 0, dimensions: { x: 5, y: 2.5, z: 0.12 }, transform: T(0, 1.25, 6) },
      { identifier: 'D-1', kind: 'door', story: 0, dimensions: { x: 0.9, y: 2.1, z: 0.05 }, transform: T(2.5, 1.05, 6), parentIdentifier: 'W-BOX' },
    ],
  };
  for (const [label, surfaces] of Object.entries(cases)) {
    const res = buildUsda({ surfaces, objects: [], rooms: [] }, {});
    const r = lint(res.text, { name: `${label}.usda` });
    assert.deepStrictEqual(r.errors, [], `${label}: ${JSON.stringify(r.errors.slice(0, 2))}`);
    assert.deepStrictEqual(r.warnings, [], `${label}: ${JSON.stringify(r.warnings.slice(0, 2))}`);
    assert.strictEqual(r.stats.meshes, r.stats.materials);
  }
});

check('prismGeometry refuses degenerate input instead of writing empty geometry', () => {
  assert.strictEqual(prismGeometry([[0, 0, 0], [1, 1, 1]], I4, 0.2), null, 'two corners');
  assert.strictEqual(prismGeometry(RECT, I4, 0), null, 'no thickness');
  assert.strictEqual(prismGeometry(RECT, [1, 0, 0], 0.2), null, 'bad transform');
  assert.strictEqual(prismGeometry([[0, 0, 0], [1, 0, 0], [2, 0, 0]], I4, 0.2), null, 'zero area');
});

console.log(`wall-prism: ${checks} checks passed`);
