'use strict';
/**
 * usda-export.js — writes a Universal Scene Description ASCII layer (.usda)
 * from the decoded RoomPlan capture, with no Apple SDK and no npm package.
 *
 * Why ASCII: a .usdz is a ZIP of .usda text files. Text can be produced by
 * calculation here, checked by eye, and diffed in git — a binary .usdc crate
 * cannot. QuickLook/USD parses ASCII natively, so nothing is lost.
 *
 * GRAMMAR PROVENANCE — every shape below is copied from Apple's own exporter,
 * as found in 105 .usda layers inside four Apple .usdz captures (Project hh,
 * Project Aug 5 2026, Novi, room.usdz):
 *
 *   1. prologue, in this exact order, nothing else:
 *          #usda 1.0
 *          (
 *              defaultPrim = "room"
 *              metersPerUnit = 1
 *              upAxis = "Y"
 *          )
 *   2. every prim carries `kind`: root = "assembly", container groups =
 *      "group", leaf element = "component" (Apple: 20 assemblies, 61 groups,
 *      101 components, never a kind-less prim).
 *   3. prim metadata lives in the parenthesis block AFTER the prim name,
 *      never inside the braces:
 *          def Xform "Wall0" (
 *              customData = { string Category = "Wall" }
 *              kind = "component"
 *          )
 *      Entries are 4 spaces deeper than `def`, one per line, no commas,
 *      `key = value` with exactly one space each side of `=`.
 *   4. every prim that carries geometry is a leaf Xform of kind "component"
 *      holding a `def Mesh` plus a `def Material` named "<Name>_color", and
 *      the Mesh binds it:  rel material:binding = </room/Mesh_grp/Wall_1/Wall_1_color>
 *      The Material holds a UsdPreviewSurface shader wired with
 *      `token outputs:surface.connect = <...outputs:surface>`.
 *   5. mesh attributes are written in ASCII-alphabetical order — Apple never
 *      deviates: extent, faceVertexCounts, faceVertexIndices, material:binding,
 *      normals, points, subdivisionScheme, xformOp:transform, xformOpOrder.
 *   6. meshes are TRIANGULATED (Apple: 382 of 382 faces are 3s) and vertices
 *      are SPLIT per face-vertex so `normals` has exactly one normal per point
 *      (Apple: 42 points / 42 normals). There is no `interpolation` metadata —
 *      the default "vertex" is what Apple relies on. Face-varying normals
 *      (`(...) ( interpolation = "faceVarying" )`) are legal USD but appear
 *      NOWHERE in the reference corpus.
 *   7. `uniform token subdivisionScheme = "none"` on every mesh.
 *   8. no `extent` in Apple's files; we keep one because it costs nothing and
 *      lets a reader cull without walking the points, and it is validated.
 *   9. prims are Xform/Mesh/Material/Shader, Cube and references only for
 *      parametric assets; we emit no `over`, `class`, `inherits`, `payload`,
 *      `variantSet`, `apiSchemas` or `customData` on attributes.
 *
 * Coordinate system: RoomPlan/ARKit already use metres, Y up, Z forward. USD
 * wants metres, Y up, so points are used verbatim in SOURCE space (the DXF
 * sheet rotation from align.js is a drawing-only transform and is deliberately
 * NOT applied here — the 3D model stays true to the capture).
 *
 * Scene shape (matches Apple's own RoomPlan export):
 *
 *   #usda 1.0 ( defaultPrim = "room" metersPerUnit = 1 upAxis = "Y" )
 *   def Xform "room" ( kind = "assembly" )
 *   {
 *       def Xform "Section_grp" ( kind = "group" )      # one assembly per room
 *       def Xform "Mesh_grp" ( kind = "group" )         # one component per mesh
 *   }
 *
 * Geometry: a surface with 3D `polygonCorners` becomes that polygon (fan
 * triangulated); any other surface becomes an oriented box built from
 * `dimensions` (x = length, y = height, z = thickness) and placed by its 4x4
 * transform. A wall with no measured thickness gets the Apple default of
 * 0.16 m and is flagged `string Thickness = "assumed"` so a reader is never
 * misled.
 *
 * Not exported: textures, UVs, cameras, lights, semantics/panels.
 *
 * API: buildUsda(capture, options) -> { files, text, summary, warnings, primCount }
 */
const { buildWallWithHoles, indexOpeningsByParent } = require('./wall-holes');
const { prismGeometry } = require('./polygon-prism');

const DEFAULT_THICKNESS = 0.16; // metres, Apple's assumed wall thickness
const EPS = 1e-9;
const MATERIAL_COLOR = '(1, 1, 1)'; // Apple's own diffuseColor for every element

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

/* ------------------------------------------------------------- geometry -- */

/** 8 corners + 6 quads of an oriented box, in world space (CCW seen outside). */
const BOX_FACES = [
  [0, 3, 2, 1], // -Z
  [4, 5, 6, 7], // +Z
  [0, 1, 5, 4], // -Y
  [3, 7, 6, 2], // +Y
  [0, 4, 7, 3], // -X
  [1, 2, 6, 5], // +X
];

function boxGeometry(dx, dy, dz, m) {
  const hx = dx / 2;
  const hy = dy / 2;
  const hz = dz / 2;
  const local = [
    [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
    [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
  ];
  return {
    points: local.map((p) => world(p, m)),
    faces: BOX_FACES.map((f) => f.slice()),
    kind: 'box',
  };
}

function polygonGeometry(cornersWorld) {
  return {
    points: cornersWorld,
    faces: [cornersWorld.map((_, i) => i)],
    kind: 'polygon',
  };
}

/* ------------------------------------------------------------- emit text -- */

/**
 * Triangulate + split vertices, exactly the shape Apple's exporter produces:
 * one vertex (and one normal) per face-vertex, `faceVertexCounts` all 3s and
 * `faceVertexIndices` running 0..n-1. Flat shading without any `interpolation`
 * metadata, and no index can ever fall outside `points`.
 */
function meshArrays(geometry) {
  const points = [];
  const normals = [];
  const counts = [];
  const indices = [];
  for (const face of geometry.faces) {
    const poly = face.map((i) => geometry.points[i]);
    if (poly.length < 3) continue;
    const n = polygonNormal(poly);
    if (!n) continue;
    for (let t = 1; t < poly.length - 1; t += 1) {
      const tri = [poly[0], poly[t], poly[t + 1]];
      // drop a zero-area triangle rather than emit a degenerate face
      const area = cross(
        [tri[1][0] - tri[0][0], tri[1][1] - tri[0][1], tri[1][2] - tri[0][2]],
        [tri[2][0] - tri[0][0], tri[2][1] - tri[0][1], tri[2][2] - tri[0][2]],
      );
      if (!(Math.hypot(area[0], area[1], area[2]) > 1e-12)) continue;
      const base = points.length;
      for (const p of tri) { points.push(p); normals.push(n); }
      counts.push(3);
      indices.push(base, base + 1, base + 2);
    }
  }
  return { points, normals, counts, indices };
}

/**
 * Attribute lines for one mesh, in Apple's exact (alphabetical) order:
 *   extent, faceVertexCounts, faceVertexIndices, rel material:binding,
 *   normals, points, subdivisionScheme
 * No `interpolation` metadata: normals are one-per-point ("vertex", the USD
 * default), which is what Apple writes.
 */
function attributeLines(mesh, bindingPath, indent) {
  const pad = ' '.repeat(indent);
  const xs = mesh.points.map((p) => p[0]);
  const ys = mesh.points.map((p) => p[1]);
  const zs = mesh.points.map((p) => p[2]);
  const out = [];
  out.push(`${pad}float3[] extent = [${vec3([Math.min(...xs), Math.min(...ys), Math.min(...zs)])}, ${vec3([Math.max(...xs), Math.max(...ys), Math.max(...zs)])}]`);
  out.push(`${pad}int[] faceVertexCounts = [${mesh.counts.join(', ')}]`);
  out.push(`${pad}int[] faceVertexIndices = [${wrapNumbers(mesh.indices, pad)}]`);
  if (bindingPath) out.push(`${pad}rel material:binding = </${bindingPath}>`);
  out.push(`${pad}normal3f[] normals = [${wrapVectors(mesh.normals, pad)}]`);
  out.push(`${pad}point3f[] points = [${wrapVectors(mesh.points, pad)}]`);
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

/** Prim metadata block, Apple-shaped: 4-space indented entries, no commas. */
function metadataBlock(lines, primIndent, entries) {
  if (!entries.length) return;
  const pad = ' '.repeat(primIndent + 4);
  // Apple opens the block on the same line as the prim name: def Xform "X" (
  lines[lines.length - 1] = `${lines[lines.length - 1]} (`;
  for (const entry of entries) {
    if (entry.raw) {
      lines.push(`${pad}${entry.key} = {`);
      for (const [k, v] of entry.fields) lines.push(`${pad}    ${k} = ${v}`);
      lines.push(`${pad}}`);
    } else {
      lines.push(`${pad}${entry.key} = ${entry.value}`);
    }
  }
  lines.push(`${' '.repeat(primIndent)})`);
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
  // Openings grouped by the wall identifier they name (`parentIdentifier`).
  const openingsByParent = indexOpeningsByParent(surfaces);
  const holesSummary = { walls: 0, openings: 0, cutArea: 0 };
  const prismSummary = { walls: 0, area: 0 };

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

    const attached = identifier != null ? openingsByParent.get(identifier) || [] : [];
    const poly = polygonOf(s);
    if (poly) {
      if (attached.length) {
        // An n-gon wall has no (u, v) grid, so it cannot be cut. Say so once.
        warnings.push({
          code: 'usdz.opening-not-cut',
          message: `Wall "${identifier || 'anonymous'}" keeps ${attached.length} opening(s) uncut (USDZ): a wall exported from polygonCorners is an n-gon, not a box, so there is no (u, v) grid to cut.`,
        });
      }
      if (category === 'Wall') {
        // A plan polygon is a wall OUTLINE, not a sheet: extrude it through the
        // thickness, otherwise Quick Look shows paper that vanishes from behind.
        let prismThickness = Number.isFinite(dims.z) && dims.z > 0
          ? dims.z
          : Number.isFinite(s.wallThickness) && s.wallThickness > 0 ? s.wallThickness : NaN;
        let prismAssumed = false;
        if (!(prismThickness > 0)) { prismThickness = assumedThickness; prismAssumed = true; }
        const prism = prismGeometry(poly, transform, prismThickness);
        if (prism) {
          addPrim(prefix, category, identifier, prism, {
            dims, poly: true, prism: true, prismArea: prism.area,
            thickness: prismThickness, thicknessAssumed: prismAssumed,
          }, extra);
          prismSummary.walls += 1;
          prismSummary.area += prism.area.total;
          return;
        }
        warnings.push({
          code: 'usdz.polygon-not-extruded',
          message: `Wall "${identifier || 'anonymous'}" stays a flat polygon (USDZ): its corners are not a plan outline perpendicular to the thickness axis, so it cannot be extruded.`,
        });
      }
      addPrim(prefix, category, identifier, polygonGeometry(poly.map((p) => world(p, transform))), { dims, poly: true }, extra);
      return;
    }

    const dx = Number.isFinite(dims.x) ? dims.x : NaN;
    const dy = Number.isFinite(dims.y) ? dims.y : NaN;
    // Thickness precedence: the captured box depth, then the source's own
    // wallThickness, then Apple's 0.16 m default (flagged as assumed).
    let dz = Number.isFinite(dims.z) && dims.z > 0
      ? dims.z
      : Number.isFinite(s.wallThickness) && s.wallThickness > 0 ? s.wallThickness : NaN;
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
    // A wall that owns openings is CUT, not merely overlaid: grid decomposition
    // in the wall's own (u, v) plane turns the openings into real holes with
    // reveal faces, so Quick Look shows a doorway, not a door plank on a wall.
    if (category === 'Wall' && attached.length) {
      const holed = buildWallWithHoles({
        wall: s,
        dimensions: { x: dx, y: dy },
        thickness: dz,
        openings: attached,
      });
      for (const warning of holed.warnings) warnings.push(warning);
      if (holed.cut) {
        addPrim(prefix, category, identifier, holed.geometry, {
          dims, poly: false, thickness: dz, thicknessAssumed, holed,
        }, extra);
        holesSummary.walls += 1;
        holesSummary.openings += holed.openings.length;
        holesSummary.cutArea += holed.cutArea;
        return;
      }
    }
    addPrim(prefix, category, identifier, geometry, { dims, poly: false, thickness: dz, thicknessAssumed }, extra);
  };

  const SURFACE_TARGETS = [
    { kind: 'wall', prefix: 'Wall', category: 'Wall' },
    { kind: 'floor', prefix: 'Floor', category: 'Floor' },
    { kind: 'door', prefix: 'Door', category: 'Door', openings: true },
    { kind: 'window', prefix: 'Window', category: 'Window', openings: true },
    { kind: 'opening', prefix: 'Opening', category: 'Opening', openings: true },
  ];
  for (const target of SURFACE_TARGETS) {
    for (const s of surfaces) {
      if (!s || s.kind !== target.kind) continue;
      // Openings stay separate prims (Apple keeps Window0.units next to its
      // wall) but declare what they are, so nobody mistakes them for solids.
      buildOne(s, target.prefix, target.category, target.openings ? { Role: 'opening' } : {});
    }
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
  lines.push('    metersPerUnit = 1');
  lines.push('    upAxis = "Y"');
  if (opts.doc) lines.push(`    doc = "${escapeString(opts.doc)}"`);
  lines.push(')');
  lines.push('');

  // Root assembly — Apple tags the stage root "assembly".
  lines.push('def Xform "room"');
  metadataBlock(lines, 0, [{ key: 'kind', value: '"assembly"' }]);
  lines.push('{');

  lines.push('    def Xform "Section_grp"');
  metadataBlock(lines, 4, [{ key: 'kind', value: '"group"' }]);
  lines.push('    {');
  sectionNames.forEach((s, i) => {
    const fields = [['string Category', '"Room"']];
    if (s.label != null) fields.push(['string Label', `"${escapeString(s.label)}"`]);
    if (s.identifier != null) fields.push(['string Identifier', `"${escapeString(s.identifier)}"`]);
    fields.push(['int Index', String(i)]);
    if (s.story != null) fields.push(['int Story', String(Math.trunc(s.story))]);
    lines.push(`        def Xform "${s.name}"`);
    metadataBlock(lines, 8, [
      { key: 'customData', raw: true, fields },
      { key: 'kind', value: '"assembly"' },
    ]);
    lines.push('        {');
    lines.push('        }');
    if (i < sectionNames.length - 1) lines.push('');
  });
  lines.push('    }');
  lines.push('');

  lines.push('    def Xform "Mesh_grp"');
  metadataBlock(lines, 4, [{ key: 'kind', value: '"group"' }]);
  lines.push('    {');
  prims.forEach((prim, i) => {
    const mesh = meshArrays(prim.geometry);
    const materialName = `${prim.name}_color`;
    const materialPath = `room/Mesh_grp/${prim.name}/${materialName}`;

    // Leaf component, Apple-shaped: customData then kind (alphabetical).
    const fields = [['string Category', `"${escapeString(prim.category)}"`]];
    if (prim.identifier != null) fields.push(['string Identifier', `"${escapeString(prim.identifier)}"`]);
    if (prim.element.thicknessAssumed) {
      // The spec asks for the assumed flag to be unmistakable in customData.
      fields.push(['string Thickness', '"assumed"']);
      fields.push(['double AssumedThickness', num(prim.element.thickness)]);
    } else if (prim.element.thickness != null) {
      fields.push(['double Thickness', num(prim.element.thickness)]);
    }
    if (prim.element.holed) {
      const holed = prim.element.holed;
      fields.push(['string Geometry', '"box with openings cut out (grid decomposition)"']);
      fields.push(['int Openings', String(holed.openings.length)]);
      fields.push(['double CutArea', num(holed.cutArea)]);
      fields.push(['double ExposedArea', num(holed.frontArea)]);
    } else if (prim.element.prism) {
      fields.push(['string Geometry', '"polygonCorners extruded through the thickness (prism)"']);
      fields.push(['double Perimeter', num(prim.element.prismArea.perimeter)]);
      fields.push(['double SurfaceArea', num(prim.element.prismArea.total)]);
      fields.push(['double Volume', num(prim.element.prismArea.volume)]);
    } else {
      fields.push(['string Geometry', prim.element.poly ? '"source polygonCorners"' : '"oriented box from dimensions"']);
    }
    for (const [k, v] of Object.entries(prim.extra)) fields.push([`string ${k}`, `"${escapeString(v)}"`]);
    fields.push(['string UUID', `"${stableUuid(`${prim.category}:${prim.identifier || prim.name}`)}"`]);

    lines.push(`        def Xform "${prim.name}"`);
    metadataBlock(lines, 8, [
      { key: 'customData', raw: true, fields },
      { key: 'kind', value: '"component"' },
    ]);
    lines.push('        {');
    lines.push(`            def Mesh "${prim.name}"`);
    lines.push('            {');
    for (const line of attributeLines(mesh, materialPath, 16)) lines.push(line);
    lines.push('            }');
    lines.push('');
    lines.push(`            def Material "${materialName}"`);
    lines.push('            {');
    lines.push(`                token outputs:surface.connect = </${materialPath}/surfaceShader.outputs:surface>`);
    lines.push('');
    lines.push('                def Shader "surfaceShader"');
    lines.push('                {');
    lines.push('                    uniform token info:id = "UsdPreviewSurface"');
    lines.push(`                    color3f inputs:diffuseColor = ${MATERIAL_COLOR}`);
    lines.push('                    color3f inputs:emissiveColor = (0, 0, 0)');
    lines.push('                    normal3f inputs:normal = (1, 1, 1)');
    lines.push('                    float inputs:occlusion = 1');
    lines.push('                    float inputs:opacity = 1');
    lines.push('                    token outputs:surface');
    lines.push('                }');
    lines.push('            }');
    lines.push('        }');
    if (i < prims.length - 1) lines.push('');
  });
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
    // Openings that became real holes: how many walls were cut, how many
    // openings were removed and how much wall face that took away (m2).
    holes: {
      wallsCut: holesSummary.walls,
      openingsCut: holesSummary.openings,
      cutArea: holesSummary.cutArea,
    },
    // Polygon walls are solids, not sheets: how many were extruded and their
    // total surface area (2 caps + one side per edge).
    prisms: prismSummary,
    prims: prims.map((p) => {
      const m = meshArrays(p.geometry);
      return {
        name: p.name,
        category: p.category,
        identifier: p.identifier,
        points: m.points.length,
        faces: m.counts.length,
        cut: p.element.holed ? p.element.holed.openings.length : 0,
        prism: Boolean(p.element.prism),
      };
    }),
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

/** Deterministic UUID-shaped tag from a seed (Apple puts a UUID in customData). */
function stableUuid(seed) {
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < seed.length; i += 1) {
    h1 = (h1 ^ seed.charCodeAt(i)) >>> 0;
    h1 = Math.imul(h1, 0x01000193) >>> 0;
    h2 = (h2 + seed.charCodeAt(i) * (i + 7)) >>> 0;
    h2 = Math.imul(h2, 0x85ebca6b) >>> 0;
  }
  const hex = (h, n) => h.toString(16).toUpperCase().padStart(8, '0').slice(0, n);
  return `${hex(h1, 8)}-${hex(h2, 4)}-4${hex(h1 ^ h2, 3)}-8${hex((h1 + h2) >>> 0, 3)}-${hex(h2, 4)}${hex(h1, 8)}`.slice(0, 36);
}

module.exports = { buildUsda, sanitizeIdentifier, DEFAULT_THICKNESS, meshArrays };
