'use strict';
/**
 * tests/test_wall_holes.js — real door/window holes in the USDZ export.
 *
 * The wall is a box in its own local space (u = 0..L along the wall, v = 0..H
 * up, w = -T/2..+T/2 through the thickness). Every opening that names the wall
 * (`parentIdentifier`) becomes a rectangle in (u, v); a grid over all u/v
 * boundaries marks cells void or solid; only solid cells are emitted, so the
 * front and back faces have actual holes and the opening edges become reveal
 * faces. No CSG library is involved — this suite proves that arithmetic alone
 * produces a watertight, correctly oriented solid.
 *
 * Measured here, always FROM THE EMITTED TRIANGLES (not from a formula the
 * exporter uses itself), so a mis-wound or missing face cannot pass:
 *   - front-face area = L*H - sum(opening areas);
 *   - signed volume from the winding = L*H*T - sum(opening areas)*T;
 *   - every directed edge appears exactly once and its twin exactly once
 *     (watertight + consistent orientation);
 *   - every emitted normal agrees with the winding and points outward.
 */
const assert = require('assert');
const path = require('path');

const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const { buildUsda } = require(path.join(LIB, 'usda-export'));
const { buildWallWithHoles, placeOpening, wallFrame } = require(path.join(LIB, 'wall-holes'));
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

/* ---------------------------------------------------------- text parsing -- */

/** Split an emitted layer into { primName: { points, normals, counts, indices } }. */
function meshes(text) {
  const out = {};
  const chunks = text.split('def Mesh "').slice(1);
  for (const chunk of chunks) {
    const name = /^([^"]+)"/.exec(chunk)[1];
    // Stop at the end of this Mesh prim's attribute block.
    const body = chunk.slice(0, chunk.indexOf('uniform token subdivisionScheme'));
    const points = /point3f\[\] points = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(([^)]*)\)/g)
      .map((p) => p.slice(1, -1).split(',').map(Number));
    const normals = /normal3f\[\] normals = \[([\s\S]*?)\]\n/.exec(body)[1].match(/\(([^)]*)\)/g)
      .map((p) => p.slice(1, -1).split(',').map(Number));
    const counts = /int\[\] faceVertexCounts = \[([^\]]+)\]/.exec(body)[1]
      .split(',').map((s) => Number(s.trim()));
    const indices = /int\[\] faceVertexIndices = \[([\s\S]*?)\]/.exec(body)[1]
      .split(',').map((s) => Number(s.trim()));
    out[name] = { points, normals, counts, indices };
  }
  return out;
}

/** Triangles of one mesh as [p0, p1, p2] world triples. */
function triangles(mesh) {
  const tris = [];
  let base = 0;
  for (const count of mesh.counts) {
    const idx = mesh.indices.slice(base, base + count);
    base += count;
    for (let i = 1; i < idx.length - 1; i += 1) {
      tris.push([mesh.points[idx[0]], mesh.points[idx[i]], mesh.points[idx[i + 1]]]);
    }
  }
  return tris;
}

const cross = (a, b) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const norm = (a) => Math.hypot(a[0], a[1], a[2]);

function triArea(t) {
  return norm(cross(sub(t[1], t[0]), sub(t[2], t[0]))) / 2;
}
function triNormal(t) {
  const c = cross(sub(t[1], t[0]), sub(t[2], t[0]));
  const l = norm(c);
  return l > 0 ? [c[0] / l, c[1] / l, c[2] / l] : [0, 0, 0];
}

/** Area of the face lying in the plane z = planeZ (the wall's front face). */
function planeArea(mesh, planeZ) {
  let area = 0;
  for (const t of triangles(mesh)) {
    if (t.every((p) => Math.abs(p[2] - planeZ) < 1e-9)) area += triArea(t);
  }
  return area;
}

/** Signed volume from the winding (positive when normals point outward). */
function signedVolume(mesh) {
  let v = 0;
  for (const t of triangles(mesh)) v += dot(t[0], cross(t[1], t[2])) / 6;
  return v;
}

/** Watertight + consistently oriented: every directed edge occurs exactly once.
 *  Vertices are split per face-vertex in the file (Apple's shape), so they are
 *  welded back by position before the topology is audited. */
function edgeAudit(mesh) {
  const key = (p) => p.map((v) => v.toFixed(7)).join(',');
  const ids = new Map();
  const welded = mesh.points.map((p) => {
    const k = key(p);
    if (!ids.has(k)) ids.set(k, ids.size);
    return ids.get(k);
  });
  const seen = new Map();
  let base = 0;
  for (const count of mesh.counts) {
    const idx = mesh.indices.slice(base, base + count).map((i) => welded[i]);
    base += count;
    for (let i = 0; i < idx.length; i += 1) {
      const a = idx[i];
      const b = idx[(i + 1) % idx.length];
      const k = `${a}>${b}`;
      seen.set(k, (seen.get(k) || 0) + 1);
    }
  }
  const dup = [...seen.entries()].filter(([, n]) => n !== 1);
  assert.strictEqual(dup.length, 0, `directed edge repeated ${dup.length}x (e.g. ${dup[0] && dup[0][0]})`);
  const open = [...seen.keys()].filter((k) => {
    const [a, b] = k.split('>');
    return !seen.has(`${b}>${a}`);
  });
  assert.strictEqual(open.length, 0, `open boundary edge ${open[0]} (mesh is not closed)`);
}

/* --------------------------------------------------------- fixtures ------ */

const WALL_L = 4;
const WALL_H = 2.5;
const WALL_T = 0.16;

/** 4 x 2.5 x 0.16 wall, centred on origin, along +X, front face at z = -T/2. */
function wall(extra) {
  return Object.assign({
    identifier: 'W-1',
    kind: 'wall',
    story: 0,
    dimensions: { x: WALL_L, y: WALL_H, z: WALL_T },
    transform: T(WALL_L / 2, WALL_H / 2, 0),
  }, extra || {});
}
function opening(identifier, kind, w, h, u, bottom, extra) {
  // u = centre along the wall, measured from the wall start; bottom = sill height
  return Object.assign({
    identifier,
    kind,
    story: 0,
    parentIdentifier: 'W-1',
    dimensions: { x: w, y: h, z: 0.04 },
    transform: T(u, bottom + h / 2, 0),
  }, extra || {});
}
function capture(surfaces) {
  return { surfaces, objects: [], rooms: [] };
}
function layer(surfaces, options) {
  const res = buildUsda(capture(surfaces), options || {});
  const m = meshes(res.text);
  return { res, text: res.text, m, warnings: res.warnings };
}

/* ------------------------------------------------------------- 1: door --- */

check('door 0.9 x 2.1 at u = 1.5 cuts 1.89 m2 out of a 4 x 2.5 wall (front area 8.11)', () => {
  const { m, warnings } = layer([
    wall(),
    opening('D-1', 'door', 0.9, 2.1, 1.5, 0),
  ]);
  assert.deepStrictEqual(warnings.filter((w) => !/^usdz\.ceiling-/.test(w.code) && w.code !== 'usdz.opening-hole-only'), []);
  const front = planeArea(m.Wall_1, -WALL_T / 2);
  assert(Math.abs(front - 8.11) < 1e-6, `front area ${front} != 8.11`);
  const back = planeArea(m.Wall_1, WALL_T / 2);
  assert(Math.abs(back - 8.11) < 1e-6, `back area ${back} != 8.11`);
  // the hole really is open: nothing is emitted inside the door rectangle on
  // the front plane
  for (const t of triangles(m.Wall_1)) {
    if (!t.every((p) => Math.abs(p[2] + WALL_T / 2) < 1e-9)) continue;
    const cx = (t[0][0] + t[1][0] + t[2][0]) / 3;
    const cy = (t[0][1] + t[1][1] + t[2][1]) / 3;
    assert(!(cx > 1.05 && cx < 1.95 && cy > 0 && cy < 2.1), `face still covers the doorway at (${cx}, ${cy})`);
  }
});

check('the door prim survives as a NAMED, SIZED component with NO geometry (a hole, not a plate)', () => {
  const { text } = layer([wall(), opening('D-1', 'door', 0.9, 2.1, 1.5, 0)]);
  assert(text.includes('def Xform "Door_1"'), 'Door_1 missing: openings stay separate prims like Apple Window0.units');
  assert(text.includes('string Role = "opening"'), 'Role = "opening" missing from customData');
  assert(/def Xform "Door_1" \([\s\S]{0,900}?string Role = "opening"/.test(text), 'Role is not on the Door prim');
  // the measured size travels with the prim, so a reader still knows the hole
  assert(/def Xform "Door_1" \([\s\S]{0,900}?double Width = 0\.900000/.test(text), 'Width missing');
  assert(/def Xform "Door_1" \([\s\S]{0,900}?double Height = 2\.100000/.test(text), 'Height missing');
  // ... and NOTHING is drawn across it. This is the regression the whole file
  // exists for: 7 solid plates used to fill the 7 cut openings.
  const doorBlock = text.slice(text.indexOf('def Xform "Door_1"'), text.indexOf('def Xform "Door_1"') + 1200);
  assert(!/def Mesh/.test(doorBlock), 'the door prim must not carry a mesh');
  // the WALL is still a real cut: front area, cut area and exposed area
  assert(text.includes('string Geometry = "box with openings cut out (grid decomposition)"'));
  assert(text.includes('int Openings = 1'));
  assert(text.includes('double CutArea = 1.890000'));
  assert(text.includes('double ExposedArea = 8.110000'));
});

check('reveal faces close the solid: the cut wall is watertight and outward-facing', () => {
  const { m } = layer([wall(), opening('D-1', 'door', 0.9, 2.1, 1.5, 0)]);
  edgeAudit(m.Wall_1);
  const vol = signedVolume(m.Wall_1);
  const expected = WALL_L * WALL_H * WALL_T - 0.9 * 2.1 * WALL_T;
  assert(Math.abs(vol - expected) < 1e-9, `signed volume ${vol} != ${expected}`);
});

check('every emitted normal agrees with its triangle winding and points outward', () => {
  const { m } = layer([wall(), opening('D-1', 'door', 0.9, 2.1, 1.5, 0)]);
  const mesh = m.Wall_1;
  const tris = triangles(mesh);
  // normals are split per face-vertex, three identical entries per triangle
  assert.strictEqual(mesh.normals.length, mesh.points.length, 'normals must be one per point');
  for (let i = 0; i < tris.length; i += 1) {
    const n = triNormal(tris[i]);
    const stored = mesh.normals[i * 3];
    for (let k = 0; k < 3; k += 1) {
      const s = mesh.normals[i * 3 + k];
      assert(Math.abs(dot(s, n) - 1) < 1e-9, `triangle ${i} normal ${s} disagrees with winding ${n}`);
    }
    // outward check 1: faces on the front plane point -Z, faces on the back +Z.
    // (Reveal faces necessarily point INTO the hole; their orientation is
    // proven by the signed volume and the watertight edge audit below.)
    if (tris[i].every((p) => Math.abs(p[2] + WALL_T / 2) < 1e-9)) {
      assert(Math.abs(n[2] + 1) < 1e-9, `front triangle ${i} points ${n}`);
    }
    if (tris[i].every((p) => Math.abs(p[2] - WALL_T / 2) < 1e-9)) {
      assert(Math.abs(n[2] - 1) < 1e-9, `back triangle ${i} points ${n}`);
    }
    assert(stored.length === 3);
  }
});

/* ---------------------------------------------------------- 2: windows --- */

check('two windows 1.2 x 1.35: front area = 10 - 2*(1.2*1.35)', () => {
  const { m, warnings } = layer([
    wall(),
    opening('N-1', 'window', 1.2, 1.35, 1.0, 0.9),
    opening('N-2', 'window', 1.2, 1.35, 3.0, 0.9),
  ]);
  assert.deepStrictEqual(warnings.filter((w) => !/^usdz\.ceiling-/.test(w.code) && w.code !== 'usdz.opening-hole-only'), []);
  const expected = 10 - 2 * (1.2 * 1.35);
  const front = planeArea(m.Wall_1, -WALL_T / 2);
  assert(Math.abs(front - expected) < 1e-6, `front area ${front} != ${expected}`);
  assert(Math.abs(front - 6.76) < 1e-12);
  edgeAudit(m.Wall_1);
  assert(Math.abs(signedVolume(m.Wall_1) - (10 - 3.24) * WALL_T) < 1e-9);
});

check('overlapping openings are cut once (union), never twice', () => {
  // two 1.0 m wide windows whose middle 0.5 m overlaps
  const { m } = layer([
    wall(),
    opening('N-1', 'window', 1.0, 1.2, 1.0, 1.0),
    opening('N-2', 'window', 1.0, 1.2, 1.5, 1.0),
  ]);
  // union spans u = 0.5..2.0 => 1.5 m wide, 1.2 m tall
  const expected = 10 - 1.5 * 1.2;
  assert(Math.abs(planeArea(m.Wall_1, -WALL_T / 2) - expected) < 1e-6, 'overlap handled as a union');
  edgeAudit(m.Wall_1); // a double cut would leave an internal, doubled face
});

/* ------------------------------------------------- 3: refuse to cut ------ */

check('an opening outside the wall leaves it solid and warns usdz.opening-not-cut', () => {
  const { m, warnings } = layer([
    wall(),
    opening('D-FAR', 'door', 0.9, 2.1, 9.0, 0), // u = 9 on a 4 m wall
  ]);
  assert(Math.abs(planeArea(m.Wall_1, -WALL_T / 2) - 10) < 1e-9, 'wall must stay solid');
  assert(Math.abs(planeArea(m.Wall_1, WALL_T / 2) - 10) < 1e-9);
  assert.strictEqual(m.Wall_1.counts.length, 12, 'an uncut wall stays the plain 12-triangle box');
  assert(warnings.some((w) => w.code === 'usdz.opening-not-cut'), 'missing usdz.opening-not-cut');
  assert(warnings.every((w) => w.code !== 'usdz.opening-na' && w.message), 'warning needs a message');
  assert(/lies outside the wall length/.test(warnings.find((w) => w.code === 'usdz.opening-not-cut').message));
});

check('an opening above the wall (door sill too high) also refuses to cut', () => {
  const { m, warnings } = layer([wall(), opening('N-HIGH', 'window', 1, 1, 2, 5)]);
  assert(Math.abs(planeArea(m.Wall_1, -WALL_T / 2) - 10) < 1e-9);
  assert(warnings.some((w) => w.code === 'usdz.opening-not-cut'));
});

check('an opening without parentIdentifier does not cut anything', () => {
  const door = opening('D-ORPHAN', 'door', 0.9, 2.1, 1.5, 0);
  delete door.parentIdentifier;
  const { m, res } = layer([wall(), door]);
  assert(Math.abs(planeArea(m.Wall_1, -WALL_T / 2) - 10) < 1e-9, 'wall without a named child must stay solid');
  assert.strictEqual(res.summary.holes.openingsCut, 0);
  assert(res.text.includes('def Xform "Door_1"'), 'the orphan door is still exported as its own prim');
  assert(res.summary.prims.find((p) => p.name === 'Door_1').emptyXform, 'an opening prim carries no geometry');
});

check('an opening without a transform is never guessed into a hole', () => {
  const door = opening('D-NOTRANSFORM', 'door', 0.9, 2.1, 1.5, 0);
  door.transform = null;
  const { m, warnings } = layer([wall(), door]);
  assert(Math.abs(planeArea(m.Wall_1, -WALL_T / 2) - 10) < 1e-9);
  assert(warnings.some((w) => w.code === 'usdz.opening-not-cut'));
});

check('a wall with no openings is the untouched box (12 triangles, 36 points)', () => {
  const { m, res } = layer([wall()]);
  assert.strictEqual(m.Wall_1.counts.length, 12);
  assert.strictEqual(m.Wall_1.points.length, 36);
  assert.strictEqual(m.Wall_1.indices.length, 36);
  assert(Math.abs(planeArea(m.Wall_1, -WALL_T / 2) - 10) < 1e-12);
  assert.strictEqual(res.summary.holes.wallsCut, 0);
});

/* ------------------------------------------------- 4: placement maths ---- */

check('placeOpening projects on the wall axes even when the wall is rotated', () => {
  // wall along +Z (rotY90), 4 m long, opening 1 m wide centred 1 m from its start
  const rotY90 = [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1.25, 0, 1];
  const w = { identifier: 'W-R', kind: 'wall', dimensions: { x: 4, y: 2.5, z: 0.16 }, transform: rotY90 };
  const frame = wallFrame(w, w.dimensions, 0.16);
  // The wall's u axis is (0, 0, -1), so u = 1 is world z = +1 for a wall centred
  // on the origin: the projection must follow the wall, not the world axes.
  const d = { identifier: 'D-R', kind: 'door', dimensions: { x: 1, y: 2.1, z: 0.04 }, transform: [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1.05, 1, 1] };
  const placed = placeOpening(frame, d);
  assert(placed.ok, placed.reason);
  assert(Math.abs(placed.u0 - 0.5) < 1e-9 && Math.abs(placed.u1 - 1.5) < 1e-9, `u ${placed.u0}..${placed.u1}`);
  assert(Math.abs(placed.v0 - 0) < 1e-9 && Math.abs(placed.v1 - 2.1) < 1e-9);
  const cut = buildWallWithHoles({ wall: w, dimensions: w.dimensions, thickness: 0.16, openings: [d] });
  assert(cut.cut, 'rotated wall not cut');
  assert(Math.abs(cut.cutArea - 1 * 2.1) < 1e-9, `cutArea ${cut.cutArea}`);
  assert(Math.abs(cut.frontArea - (10 - 2.1)) < 1e-9);
});

check('an opening that runs past the wall end is clamped and reported, never silently oversized', () => {
  // door exactly flush with the right wall end: u = 3.55 + 0.45 = 4.00
  const flush = layer([wall(), opening('D-EDGE', 'door', 0.9, 2.1, 3.55, 0)]);
  assert.deepStrictEqual(flush.warnings.filter((w) => !/^usdz\.ceiling-/.test(w.code) && w.code !== 'usdz.opening-hole-only'), []);
  assert(Math.abs(planeArea(flush.m.Wall_1, -WALL_T / 2) - (10 - 0.9 * 2.1)) < 1e-9, 'a flush door must cut fully');
  edgeAudit(flush.m.Wall_1);

  // 10 mm past the end: clamped to the wall, hole is 0.89 wide, reported
  const clamp = layer([wall(), opening('D-EDGE2', 'door', 0.9, 2.1, 3.56, 0)]);
  assert(clamp.warnings.some((w) => w.code === 'usdz.opening-clamped'), 'clamp must be reported');
  assert(Math.abs(planeArea(clamp.m.Wall_1, -WALL_T / 2) - (10 - 0.89 * 2.1)) < 1e-9, `clamped front area ${planeArea(clamp.m.Wall_1, -WALL_T / 2)}`);
  edgeAudit(clamp.m.Wall_1);

  // 43 cm past the end: still on the wall, so it is cut (clamped) and reported,
  // never refused and never allowed to eat beyond the wall.
  const over = layer([wall(), opening('D-EDGE3', 'door', 0.9, 2.1, 3.98, 0)]);
  assert(over.warnings.some((w) => w.code === 'usdz.opening-clamped'));
  assert(Math.abs(planeArea(over.m.Wall_1, -WALL_T / 2) - (10 - 0.47 * 2.1)) < 1e-9);
  edgeAudit(over.m.Wall_1);
});

/* ------------------------------------------------------------ 5: lint ---- */

check('every generated layer passes usda-lint with zero errors and zero warnings', () => {
  const cases = {
    door: [wall(), opening('D-1', 'door', 0.9, 2.1, 1.5, 0)],
    windows: [wall(), opening('N-1', 'window', 1.2, 1.35, 1.0, 0.9), opening('N-2', 'window', 1.2, 1.35, 3.0, 0.9)],
    overlap: [wall(), opening('N-1', 'window', 1.0, 1.2, 1.0, 1.0), opening('N-2', 'window', 1.0, 1.2, 1.5, 1.0)],
    refused: [wall(), opening('D-FAR', 'door', 0.9, 2.1, 9, 0)],
    plain: [wall()],
  };
  for (const [label, surfaces] of Object.entries(cases)) {
    const res = buildUsda(capture(surfaces), {});
    const r = lint(res.text, { name: `${label}.usda` });
    assert.deepStrictEqual(r.errors, [], `${label}: ${JSON.stringify(r.errors.slice(0, 2))}`);
    // A capture without a room/floor polygon legitimately reports
    // usdz.ceiling-no-polygon (no ceiling is invented); that is not a defect.
    assert.deepStrictEqual(r.warnings.filter((w) => !/^usdz\.ceiling-/.test(w.code)), [], `${label}: ${JSON.stringify(r.warnings.slice(0, 2))}`);
    assert(r.header.defaultPrim === 'room' && r.header.metersPerUnit === 1 && r.header.upAxis === 'Y');
  }
});

check('summary reports the holes it cut, per wall', () => {
  const res = buildUsda(capture([
    wall(),
    opening('D-1', 'door', 0.9, 2.1, 1.5, 0),
    opening('N-1', 'window', 1.2, 1.35, 3.0, 0.9),
    { identifier: 'W-2', kind: 'wall', story: 0, dimensions: { x: 3, y: 2.5, z: 0.12 }, transform: T(1.5, 1.25, 5) },
  ]), {});
  assert.strictEqual(res.summary.holes.wallsCut, 1, 'only the wall with children is cut');
  assert.strictEqual(res.summary.holes.openingsCut, 2);
  assert(Math.abs(res.summary.holes.cutArea - (1.89 + 1.62)) < 1e-9, `cutArea ${res.summary.holes.cutArea}`);
  const cutWall = res.summary.prims.find((p) => p.identifier === 'W-1');
  assert.strictEqual(cutWall.cut, 2);
  const plainWall = res.summary.prims.find((p) => p.identifier === 'W-2');
  assert.strictEqual(plainWall.cut, 0);
  assert.strictEqual(plainWall.faces, 12, 'a wall without openings stays a box');
});

check('determinism: cutting twice gives identical text', () => {
  const surfaces = [wall(), opening('D-1', 'door', 0.9, 2.1, 1.5, 0)];
  assert.strictEqual(buildUsda(capture(surfaces), {}).text, buildUsda(capture(surfaces), {}).text);
});

console.log(`wall-holes: ${checks} checks passed`);
