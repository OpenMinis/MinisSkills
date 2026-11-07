'use strict';
/**
 * usda-export.js — writes a Universal Scene Description ASCII layer (.usda)
 * from the decoded RoomPlan capture, with no Apple SDK and no npm package.
 *
 * Why ASCII: a .usdz is a ZIP of .usda text files. Text can be produced by
 * calculation here, checked by eye, and diffed in git — a binary .usdc crate
 * cannot. QuickLook/USD parses ASCII natively, so nothing is lost.
 *
 * Coordinate system: RoomPlan/ARKit already use metres, Y up, Z forward. USD
 * wants metres, Y up, so points are used verbatim in SOURCE space (the DXF
 * sheet rotation from align.js is a drawing-only transform and is deliberately
 * NOT applied here — the 3D model stays true to the capture).
 *
 * Scene shape (matches Apple's own RoomPlan export):
 *
 *   #usda 1.0 ( defaultPrim = "room" metersPerUnit = 1 upAxis = "Y" )
 *   def Xform "room"
 *   {
 *       def Xform "Section_grp"        # one empty Xform per captured room
 *       { def Xform "Kuhinja" { customData = {...} } }
 *       def Xform "Mesh_grp"           # every mesh, flat
 *       {
 *           def Mesh "Wall_1"  { customData = { Category="Wall" Identifier="W-A" } }
 *           def Mesh "Floor_1" ...
 *           def Mesh "Door_1" / "Window_1" / "Opening_1" / "Object_1" ...
 *       }
 *   }
 *
 * Geometry: a surface with 3D `polygonCorners` becomes that polygon (fan
 * triangulated by the renderer via faceVertexCounts/faceVertexIndices); any
 * other surface becomes an oriented box built from `dimensions` (x = length,
 * y = height, z = thickness) and placed by its 4x4 transform. A wall with no
 * measured thickness gets the Apple default of 0.16 m and is flagged
 * `string Thickness = "assumed"` so a reader is never misled.
 *
 * Not exported: textures, UVs, materials, cameras, lights, semantics/panels.
 * An untextured, un-UV'd mesh is exactly what AR Quick Look needs to render
 * solid geometry, but it is not a photogrammetric reconstruction.
 *
 * API: buildUsda(capture, options) -> { files, text, summary, warnings, primCount }
 */
const DEFAULT_THICKNESS = 0.16; // metres, Apple's assumed wall thickness
const EPS = 1e-9;

/* --------------------------------------------------------------- helpers -- */

/** Fixed 6-decimal formatting, always a '.' decimal separator, never "-0". */
function num(v) {
  if (!Number.isFinite(v)) return null;
  const s = v.toFixed(6);
  return s === '-0.000000' ? '0.000000' : s;
}

function vec3(p) {
  const a = num(p[0]);
  const b = num(p[1]);
  const c = num(p[2]);
  if (a === null || b === null || c === null) return null;
  return `(${a}, ${b}, ${c})`;
}

const finiteVec = (v) => Array.isArray(v) && v.length >= 3 && [0, 1, 2].every((i) => Number.isFinite(v[i]));

/** Column-major 4x4 (ARKit/simd_float4x4) applied to a point. */
function world(p, m) {
  return [
    m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
    m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
    m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14],
  ];
}

const isRigid = (m) => Array.isArray(m) && m.length === 16 && m.every(Number.isFinite);

function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function unit(a) {
  const l = Math.hypot(a[0], a[1], a[2]);
  if (!(l > EPS)) return null;
  return [a[0] / l, a[1] / l, a[2] / l];
}

/** Newell normal of a polygon (robust for n > 3 and slightly non-planar input). */
function polygonNormal(points) {
  const n = [0, 0, 0];
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    n[0] += (a[1] - b[1]) * (a[2] + b[2]);
    n[1] += (a[2] - b[2]) * (a[0] + b[0]);
    n[2] += (a[0] - b[0]) * (a[1] + b[1]);
  }
  return unit(n);
}

/**
 * USD identifiers: [A-Za-z_][A-Za-z0-9_]*, ASCII only. A Croatian room label
 * ("Soba 1", "Kuhinja/dnevni") becomes Soba_1 / Kuhinja_dnevni; nothing is
 * transliterated, characters are replaced so the mapping stays reversible by
 * eye against customData.Label.
 */
function sanitizeIdentifier(raw, fallback) {
  let s = String(raw == null ? '' : raw).trim();
  s = s.replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
  s = s.replace(/_+/g, '_');
  if (!s) s = fallback;
  if (!/^[A-Za-z_]/.test(s)) s = `r_${s}`;
  return s;
}

/** Predicate: does this surface have a usable 3D polygon? */
function polygonOf(surface) {
  const corners = Array.isArray(surface.polygonCorners) ? surface.polygonCorners : null;
  if (!corners || corners.length < 3) return null;
  const pts = corners.map((c) => (Array.isArray(c) ? c.slice(0, 3) : [c && c.x, c && c.y, c && c.z]));
  let list = pts.filter(finiteVec);
  if (list.length !== pts.length) return null;
  // Drop a duplicated closing vertex (some producers repeat the first point).
  if (list.length > 3) {
    const a = list[0];
    const b = list[list.length - 1];
    if (Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) < 1e-7) list = list.slice(0, -1);
  }
  if (list.length < 3) return null;
  // Reject a degenerate (zero-area) polygon: USD would render nothing.
  if (!polygonNormal(list)) return null;
  return list;
}

/** 8 corners + 6 quads of an oriented box, in world space. */
const BOX_FACES = [
  { idx: [0, 3, 2, 1] }, // -Z
  { idx: [4, 5, 6, 7] }, // +Z
  { idx: [0, 1, 5, 4] }, // -Y
  { idx: [3, 7, 6, 2] }, // +Y
  { idx: [0, 4, 7, 3] }, // -X
  { idx: [1, 2, 6, 5] }, // +X
];

function boxGeometry(dx, dy, dz, m) {
  const hx = dx / 2;
  const hy = dy / 2;
  const hz = dz / 2;
  const local = [
    [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
    [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
  ];
  const points = local.map((p) => world(p, m));
  return {
    points,
    counts: BOX_FACES.map(() => 4),
    indices: BOX_FACES.map((f) => f.idx),
    kind: 'box',
  };
}

function polygonGeometry(cornersWorld) {
  return {
    points: cornersWorld,
    counts: [cornersWorld.length],
    indices: [cornersWorld.map((_, i) => i)],
    kind: 'polygon',
  };
}

/* ------------------------------------------------------------- emit text -- */

function attributeLines(geometry, indent) {
  const pad = ' '.repeat(indent);
  const flat = [].concat(...geometry.indices);
  // Face-varying normals: one normal per face-vertex, so an 8-vertex box can
  // still shade flat. If anything is degenerate we simply omit the attribute
  // (USD computes what it can) rather than emit a NaN.
  const normals = [];
  let normalsOk = true;
  let cursor = 0;
  for (const face of geometry.indices) {
    const pts = face.map((i) => geometry.points[i]);
    const n = polygonNormal(pts);
    if (!n) { normalsOk = false; break; }
    for (let i = 0; i < face.length; i += 1) normals.push(n);
    cursor += face.length;
  }
  if (cursor !== flat.length) normalsOk = false;

  const xs = geometry.points.map((p) => p[0]);
  const ys = geometry.points.map((p) => p[1]);
  const zs = geometry.points.map((p) => p[2]);
  const extent = [
    `(${num(Math.min(...xs))}, ${num(Math.min(...ys))}, ${num(Math.min(...zs))})`,
    `(${num(Math.max(...xs))}, ${num(Math.max(...ys))}, ${num(Math.max(...zs))})`,
  ];

  const out = [];
  out.push(`${pad}float3[] extent = [${extent.join(', ')}]`);
  out.push(`${pad}int[] faceVertexCounts = [${geometry.counts.join(', ')}]`);
  // Indices are wrapped so a long wall never produces a 10 000-character line.
  out.push(`${pad}int[] faceVertexIndices = [${wrapNumbers(flat, pad)}]`);
  if (normalsOk && normals.length) {
    out.push(`${pad}normal3f[] normals = [${wrapVectors(normals, pad)}] (`);
    out.push(`${pad}    interpolation = "faceVarying"`);
    out.push(`${pad})`);
  }
  out.push(`${pad}point3f[] points = [${wrapVectors(geometry.points, pad)}]`);
  out.push(`${pad}uniform token subdivisionScheme = "none"`);
  return out;
}

function wrapNumbers(values, indent) {
  return wrapTokens(values.map((v) => String(v)), indent);
}

function wrapVectors(points, indent) {
  const parts = points.map((p) => vec3(p));
  if (parts.some((p) => p === null)) throw new Error('usda: non-finite point reached the writer');
  return wrapTokens(parts, indent);
}

/**
 * Break a long array over continuation lines. USDA does not care about line
 * length; long single lines are legal but unreadable and undiffable, so arrays
 * wrap at ~100 characters with the element indent preserved.
 */
function wrapTokens(tokens, indent) {
  const limit = 100;
  const pad = `${' '.repeat(4)}${indent}`;
  const lines = [];
  let line = '';
  for (const token of tokens) {
    const candidate = line ? `${line}, ${token}` : token;
    if (line && indent.length + candidate.length > limit) {
      lines.push(`${line},`);
      line = token;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines.join('\n' + pad);
}

/* ----------------------------------------------------------------- build -- */

/**
 * @param {object} capture decoded capture model (model.js): { surfaces, objects, rooms }
 * @param {object} [options]
 * @param {number} [options.thickness=0.16] assumed wall thickness, metres
 * @param {string} [options.fileName='room.usda'] root layer name inside the archive
 * @param {string} [options.doc] optional `doc` metadata string
 * @returns {{files:Object<string,Buffer>, text:string, summary:object, warnings:object[], primCount:number}}
 */
function buildUsda(capture, options) {
  const opts = options || {};
  const assumedThickness = Number.isFinite(opts.thickness) && opts.thickness > 0 ? opts.thickness : DEFAULT_THICKNESS;
  const fileName = opts.fileName || 'room.usda';
  const warnings = [];
  const surfaces = Array.isArray(capture && capture.surfaces) ? capture.surfaces : [];
  const objects = Array.isArray(capture && capture.objects) ? capture.objects : [];

  const byCategory = {};
  const bump = (key) => { byCategory[key] = (byCategory[key] || 0) + 1; };

  /* ---- sections: one Xform per captured room ---------------------------- */
  const rooms = Array.isArray(capture && capture.rooms) ? capture.rooms : [];
  const sectionNames = [];
  const usedNames = new Set();
  const unique = (base) => {
    let name = base;
    let n = 2;
    while (usedNames.has(name)) { name = `${base}_${n}`; n += 1; }
    usedNames.add(name);
    return name;
  };
  if (rooms.length) {
    rooms.forEach((room, i) => {
      const label = room && (room.label || room.category || null);
      sectionNames.push({
        name: unique(sanitizeIdentifier(label, `room_${i + 1}`)),
        label: label == null ? null : String(label),
        identifier: room && room.identifier != null ? String(room.identifier) : null,
        story: room && Number.isFinite(room.story) ? room.story : null,
      });
    });
  } else {
    // Raw captures carry no room records: reconstruct section stubs from each
    // surface's source room index so the tree still shows one node per room.
    const indices = new Set();
    for (const s of surfaces.concat(objects)) {
      const idx = s && Number.isFinite(s.sourceRoomIndex) ? s.sourceRoomIndex : 0;
      indices.add(idx);
    }
    [...indices].sort((a, b) => a - b).forEach((idx) => {
      sectionNames.push({ name: unique(`room_${idx + 1}`), label: null, identifier: null, story: idx });
    });
  }
  for (const s of sectionNames) bump('Room');

  /* ---- meshes ----------------------------------------------------------- */
  const prims = [];
  const counters = {};
  const nextName = (prefix) => {
    counters[prefix] = (counters[prefix] || 0) + 1;
    return `${prefix}_${counters[prefix]}`;
  };

  const addPrim = (prefix, category, identifier, geometry, element, extra) => {
    prims.push({ name: nextName(prefix), category, identifier, geometry, element, extra: extra || {} });
    bump(category);
  };

  const buildOne = (s, prefix, category, extra) => {
    const transform = s && s.transform;
    const dims = (s && s.dimensions) || {};
    const identifier = s && s.identifier != null ? String(s.identifier) : null;

    if (!isRigid(transform)) {
      warnings.push({ code: 'usdz.skipped-non-rigid', message: `Skipped ${category} "${identifier || 'anonymous'}" (USDZ): missing or non-finite 4x4 transform, so it has no place in world space.` });
      return;
    }

    const poly = polygonOf(s);
    if (poly) {
      addPrim(prefix, category, identifier, polygonGeometry(poly.map((p) => world(p, transform))), { dims, poly: true }, extra);
      return;
    }

    const dx = Number.isFinite(dims.x) ? dims.x : NaN;
    const dy = Number.isFinite(dims.y) ? dims.y : NaN;
    let dz = Number.isFinite(dims.z) ? dims.z : NaN;
    if (!(dx > 0) || !(dy > 0)) {
      warnings.push({ code: 'usdz.skipped-no-geometry', message: `Skipped ${category} "${identifier || 'anonymous'}" (USDZ): no usable polygonCorners and no positive x/y dimensions.` });
      return;
    }
    let thicknessAssumed = false;
    if (!(dz > 0)) {
      // Only walls have a documented Apple default; anything else is a token
      // slab so the prim still exists, always flagged as assumed.
      dz = assumedThickness;
      thicknessAssumed = true;
    }
    const geometry = boxGeometry(dx, dy, dz, transform);
    addPrim(prefix, category, identifier, geometry, { dims, poly: false, thickness: dz, thicknessAssumed }, extra);
  };

  const SURFACE_TARGETS = [
    { kind: 'wall', prefix: 'Wall', category: 'Wall' },
    { kind: 'floor', prefix: 'Floor', category: 'Floor' },
    { kind: 'door', prefix: 'Door', category: 'Door' },
    { kind: 'window', prefix: 'Window', category: 'Window' },
    { kind: 'opening', prefix: 'Opening', category: 'Opening' },
  ];
  for (const target of SURFACE_TARGETS) {
    for (const s of surfaces) if (s && s.kind === target.kind) buildOne(s, target.prefix, target.category);
  }
  // Anything that is neither a known surface kind nor an object is still
  // geometry — emit it rather than drop it silently.
  const known = new Set(SURFACE_TARGETS.map((t) => t.kind));
  for (const s of surfaces) {
    if (!s || known.has(s.kind)) continue;
    const cat = sanitizeIdentifier(s.kind || s.category, 'Other');
    buildOne(s, 'Surface', cat, {});
  }
  for (const o of objects) {
    const cat = sanitizeIdentifier(o && o.category, 'Object');
    buildOne(o, 'Object', o && o.category != null ? String(o.category) : 'Object');
  }

  /* ---- text ------------------------------------------------------------- */
  const lines = [];
  lines.push('#usda 1.0');
  lines.push('(');
  lines.push('    defaultPrim = "room"');
  if (opts.doc) lines.push(`    doc = "${escapeString(opts.doc)}"`);
  lines.push('    metersPerUnit = 1');
  lines.push('    upAxis = "Y"');
  lines.push(')');
  lines.push('');
  lines.push('def Xform "room"');
  lines.push('{');
  lines.push('    def Xform "Section_grp"');
  lines.push('    {');
  sectionNames.forEach((s, i) => {
    lines.push(`        def Xform "${s.name}"`);
    lines.push('        {');
    lines.push('            customData = {');
    lines.push('                string Category = "Room"');
    if (s.label != null) lines.push(`                string Label = "${escapeString(s.label)}"`);
    if (s.identifier != null) lines.push(`                string Identifier = "${escapeString(s.identifier)}"`);
    lines.push(`                int Index = ${i}`);
    if (s.story != null) lines.push(`                int Story = ${Math.trunc(s.story)}`);
    lines.push('            }');
    lines.push('        }');
  });
  lines.push('    }');
  lines.push('');
  lines.push('    def Xform "Mesh_grp"');
  lines.push('    {');
  for (const prim of prims) {
    lines.push(`        def Mesh "${prim.name}"`);
    lines.push('        {');
    for (const line of attributeLines(prim.geometry, 12)) lines.push(line);
    lines.push('            customData = {');
    lines.push(`                string Category = "${escapeString(prim.category)}"`);
    if (prim.identifier != null) lines.push(`                string Identifier = "${escapeString(prim.identifier)}"`);
    if (prim.element.thicknessAssumed) {
      // The spec asks for the assumed flag to be unmistakable in customData.
      lines.push('                string Thickness = "assumed"');
      lines.push(`                double AssumedThickness = ${num(prim.element.thickness)}`);
    } else if (prim.element.thickness != null) {
      lines.push(`                double Thickness = ${num(prim.element.thickness)}`);
    }
    if (prim.element.poly) lines.push('                string Geometry = "source polygonCorners"');
    else lines.push('                string Geometry = "oriented box from dimensions"');
    for (const [k, v] of Object.entries(prim.extra)) lines.push(`                string ${k} = "${escapeString(v)}"`);
    lines.push('            }');
    lines.push('        }');
  }
  lines.push('    }');
  lines.push('}');
  lines.push('');

  const text = lines.join('\n');

  const summary = {
    rootLayer: fileName,
    sections: sectionNames.length,
    meshPrims: prims.length,
    byCategory,
    assumedThickness,
    prims: prims.map((p) => ({ name: p.name, category: p.category, identifier: p.identifier, points: p.geometry.points.length, faces: p.geometry.counts.length })),
  };

  return {
    files: { [fileName]: Buffer.from(text, 'utf8') },
    [fileName]: Buffer.from(text, 'utf8'),
    text,
    summary,
    warnings,
    primCount: prims.length,
  };
}

function escapeString(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/[\r\n\t]+/g, ' ');
}

module.exports = { buildUsda, sanitizeIdentifier, DEFAULT_THICKNESS };
