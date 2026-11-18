'use strict';
// Draws a confirmed Surface Region GROUP on the plan sheet.
//
// A group (e.g. K2.1 = SR 2.1 + SR 2.2) is one physical slope made of two
// supplied faces. The registry keeps every face and its area; the SHEET
// carries ONE group label and ONE fall arrow for the whole slope. The internal
// seam where the source faces meet is NOT drawn (a confirmed group is one
// piece on the sheet), and the extra per-face fall arrow is withdrawn. Nothing
// is flattened, merged arithmetically or deleted: the faces remain in the
// registry and in the quantity reference, and the seam geometry stays recorded
// in `drawn[].seamWithdrawn` as data, not as a drawn line.
//
// Honest limits: if a shared edge cannot be found the seam is NOT invented and
// the label is placed in the largest member face (or as a local callout by the
// shared layout engine). Every such decision is reported in `warnings`.
const { place } = require('./ceiling-layout');

const EPS = 1e-7;
const near = (p, q) => Math.abs(p[0] - q[0]) < 1e-6 && Math.abs(p[1] - q[1]) < 1e-6;
const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const ringArea = (p) => Math.abs(p.reduce((s, a, i) => {
  const b = p[(i + 1) % p.length];
  return s + a[0] * b[1] - b[0] * a[1];
}, 0)) / 2;

/** Overlap of two collinear edges, as a segment, or null. */
function sharedSegment(a, b) {
  let best = null;
  for (let i = 0; i < a.length; i += 1) {
    const p = a[i];
    const q = a[(i + 1) % a.length];
    const dx = q[0] - p[0];
    const dy = q[1] - p[1];
    const len = Math.hypot(dx, dy);
    if (len < EPS) continue;
    for (let j = 0; j < b.length; j += 1) {
      const r = b[j];
      const s = b[(j + 1) % b.length];
      if (Math.abs(cross(p, q, r)) > 1e-6 * len || Math.abs(cross(p, q, s)) > 1e-6 * len) continue;
      const t = (u) => ((u[0] - p[0]) * dx + (u[1] - p[1]) * dy) / (len * len);
      const lo = Math.max(0, Math.min(t(r), t(s)));
      const hi = Math.min(1, Math.max(t(r), t(s)));
      if (hi - lo < 1e-4) continue;
      const seg = [[p[0] + dx * lo, p[1] + dy * lo], [p[0] + dx * hi, p[1] + dy * hi]];
      const l = (hi - lo) * len;
      if (!best || l > best.len) best = { len: l, a: seg[0], b: seg[1] };
    }
  }
  return best;
}

/** Union ring of two polygons that share exactly one edge; null otherwise. */
function stitchUnion(a, b) {
  for (let i = 0; i < a.length; i += 1) {
    const v = a[(i + 1) % a.length];
    const u = a[i];
    for (let j = 0; j < b.length; j += 1) {
      // shared edge a[i]->a[i+1] equals b[j+1]->b[j] (opposite direction)
      if (!(near(u, b[(j + 1) % b.length]) && near(v, b[j]))) continue;
      const ring = [v];
      let k = (i + 2) % a.length;
      let guard = 0;
      while (k !== i && guard++ < a.length + 1) { ring.push(a[k]); k = (k + 1) % a.length; }
      k = (j + 2) % b.length;
      guard = 0;
      while (k !== j && guard++ < b.length + 1) { ring.push(b[k]); k = (k + 1) % b.length; }
      const clean = ring.filter((p, n) => n === 0 || !near(p, ring[n - 1]));
      // A stitched ring is already open (no repeated closing vertex); popping
      // the last vertex would cut a real corner and halve the area.
      return clean.length >= 3 ? clean : null;
    }
  }
  return null;
}

function heightRange(faces) {
  const values = [];
  for (const f of faces) {
    if (!f.heightM || !Number.isFinite(f.heightM.min) || !Number.isFinite(f.heightM.max)) continue;
    values.push(f.heightM.min, f.heightM.max);
  }
  return values.length ? { min: Math.min(...values), max: Math.max(...values) } : null;
}

const fmt = (v) => (Math.round(v * 100) / 100).toFixed(2);
function rangeLabel(h) {
  if (!h) return 'h unknown';
  return h.max - h.min < 0.005 ? `h ${fmt(h.min)}` : `h ${fmt(h.min)}-${fmt(h.max)}`;
}

/** One-piece group title: "SR 2.1-SR 2.2" -> "SR 2.1-2.2".
 *  Members that share a textual prefix and a numeric stem collapse into a
 *  single range, so the sheet reads one slope, not two blocks joined by "+".
 *  Anything that cannot be read as such a series keeps the explicit "+" join
 *  (never invent a range that the member ids do not support). */
function groupTitle(members) {
  const list = members.map((m) => String(m).trim());
  if (list.length < 2) return list.join('+');
  const parsed = list.map((m) => {
    const match = /^(.*?)(\d+(?:\.\d+)*)$/.exec(m);
    return match ? { head: match[1], parts: match[2].split('.').map(Number), raw: match[2] } : null;
  });
  if (parsed.some((p) => !p)) return list.join('+');
  const head = parsed[0].head;
  if (parsed.some((p) => p.head !== head)) return list.join('+');
  const depth = parsed[0].parts.length;
  if (parsed.some((p) => p.parts.length !== depth)) return list.join('+');
  const stem = parsed[0].parts.slice(0, -1);
  if (parsed.some((p) => p.parts.slice(0, -1).some((v, i) => v !== stem[i]))) return list.join('+');
  const tails = parsed.map((p) => p.parts[p.parts.length - 1]);
  const lo = Math.min(...tails);
  const hi = Math.max(...tails);
  const pre = [...stem.map((v) => `${v}.`), lo].join('');
  const post = [...stem.map((v) => `${v}.`), hi].join('');
  if (pre === post) return list.join('+');
  return `${head}${pre}-${post}`;
}

/** Entities of one face's fall arrow: shaft match OR midpoint inside the face.
 *  A fall arrow is THREE lines (shaft + two wings), so the whole cluster must be
 *  found; matching only the shaft would leave two orphan wings on the sheet. */
function arrowIndicesFor(entities, face, story) {
  const line = Array.isArray(face.slopeIndicatorLine) ? face.slopeIndicatorLine : null;
  const poly = face.regionPlanM;
  const same = (p, q) => p && q && Math.abs(p[0] - q[0]) < 1e-4 && Math.abs(p[1] - q[1]) < 1e-4;
  const out = [];
  for (let i = 0; i < entities.length; i += 1) {
    const e = entities[i];
    if (!e || e.type !== 'line' || e.role !== 'downhill-arrow' || e.story !== story) continue;
    const shaft = line && ((same(e.a, line[0]) && same(e.b, line[1])) || (same(e.a, line[1]) && same(e.b, line[0])));
    const mid = [(e.a[0] + e.b[0]) / 2, (e.a[1] + e.b[1]) / 2];
    if (shaft || (Array.isArray(poly) && insideRing(mid, poly))) out.push(i);
  }
  return out;
}

/** Ray-casting point-in-polygon (no dependencies). */
function insideRing(p, ring) {
  let hit = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const a = ring[i];
    const b = ring[j];
    if ((a[1] > p[1]) !== (b[1] > p[1])) {
      const x = a[0] + ((p[1] - a[1]) / (b[1] - a[1])) * (b[0] - a[0]);
      if (p[0] < x) hit = !hit;
    }
  }
  return hit;
}

/**
 * Replace per-face SR labels with one group label + a thin seam line.
 *
 * @param {Array} entities  the plan entity array (mutated: member labels removed)
 * @param {Array} records   ceilingDiagnostics.records (sourceRegionId, regionPlanM, heightM)
 * @param {object} override {sourceSHA256, groups:[{id, members, confirmation}]} or null
 * @param {string} sourceSHA256  SHA256 of the scan the override must match
 * @returns {{added:Array, drawn:Array, warnings:Array}}
 */
function renderGroups(entities, records, override, sourceSHA256) {
  const added = [];
  const drawn = [];
  const warnings = [];
  if (!override || !Array.isArray(override.groups) || !override.groups.length) return { added, drawn, warnings };
  if (override.sourceSHA256 && sourceSHA256 && override.sourceSHA256 !== sourceSHA256) {
    warnings.push({ code: 'roomplan.surface-region-group-hash-mismatch', message: 'Surface Region groups were not drawn: the sidecar source SHA256 does not match this scan.' });
    return { added, drawn, warnings };
  }
  const byId = new Map();
  for (const r of records || []) if (r && r.sourceRegionId && Array.isArray(r.regionPlanM) && r.regionPlanM.length >= 3) byId.set(r.sourceRegionId, r);

  for (const g of override.groups) {
    if (!g || !g.id || !Array.isArray(g.members) || g.members.length < 2) continue;
    if (g.confirmation !== 'user-confirmed') continue;
    const faces = g.members.map((m) => byId.get(m));
    if (faces.some((f) => !f)) {
      warnings.push({ code: 'roomplan.surface-region-group-unrendered', message: `Surface Region group ${g.id} was not drawn: member face geometry is missing.` });
      continue;
    }
    if (faces.some((f) => f.story !== faces[0].story || f.roomIdentifier !== faces[0].roomIdentifier)) {
      warnings.push({ code: 'roomplan.surface-region-group-unrendered', message: `Surface Region group ${g.id} was not drawn: members span rooms or stories.` });
      continue;
    }
    const story = faces[0].story;
    const layer = `S${story}_CEILING`;
    const seamLayer = `S${story}_CEILING_SEAM`;

    // 1. Remove the per-face labels of this group only. Each label text is
    //    tagged with its `sourceRegionId` when it is placed, so a wrapped
    //    two-line label loses BOTH lines; the value-prefix match is kept as a
    //    fallback for callers that render labels without the tag.
    let removed = 0;
    for (let i = entities.length - 1; i >= 0; i -= 1) {
      const e = entities[i];
      if (!e || e.type !== 'text' || typeof e.value !== 'string') continue;
      if (!/_CEILING(_FLAT)?$/.test(String(e.layer || ''))) continue;
      if (e.story !== story) continue;
      const tagged = faces.some((f) => e.sourceRegionId === f.sourceRegionId);
      const prefixed = faces.some((f) => e.value.startsWith(`${f.sourceRegionId}  `) || e.value === f.sourceRegionId);
      if (!tagged && !prefixed) continue;
      entities.splice(i, 1);
      removed += 1;
    }

    // 2. Group footprint: stitched union when the faces share an edge, else the
    //    largest member face. Never a bounding box - that would claim area.
    let poly = null;
    let polyBasis = null;
    if (faces.length === 2) {
      poly = stitchUnion(faces[0].regionPlanM, faces[1].regionPlanM);
      if (poly) polyBasis = 'stitched-union-of-source-faces';
    }
    if (!poly) {
      poly = faces.slice().sort((a, b) => ringArea(b.regionPlanM) - ringArea(a.regionPlanM))[0].regionPlanM;
      polyBasis = 'largest-member-face';
      warnings.push({ code: 'roomplan.surface-region-group-no-shared-edge', message: `Surface Region group ${g.id}: no single shared edge between the member faces, so the label uses the largest face and no seam line is drawn.` });
    }

    // 3. ONE fall arrow for the whole slope. Every member face carried its own
    //    downhill arrow; a confirmed group keeps the arrow of the largest
    //    member and withdraws the rest, so the sheet shows a single direction.
    const ordered = faces.slice().sort((a, b) => ringArea(b.regionPlanM) - ringArea(a.regionPlanM));
    let keptFace = null;
    for (const f of ordered) if (arrowIndicesFor(entities, f, story).length) { keptFace = f; break; }
    const drop = new Set();
    let withdrawnArrows = 0;
    for (const f of faces) {
      if (f === keptFace) continue;
      for (const i of arrowIndicesFor(entities, f, story)) drop.add(i);
    }
    for (const i of Array.from(drop).sort((a, b) => b - a)) { entities.splice(i, 1); withdrawnArrows += 1; }
    if (faces.length > 2 && withdrawnArrows) {
      warnings.push({ code: 'roomplan.surface-region-group-arrow-withdrawn', message: `Surface Region group ${g.id}: ${withdrawnArrows} per-face fall arrow lines were withdrawn; one arrow is drawn for the whole group.` });
    }

    // 4. ONE label for the whole slope, read as one piece ("SR 2.1-2.2").
    const value = `${groupTitle(g.members)}  ${rangeLabel(heightRange(faces))}`;
    const out = [];
    const layout = place(poly.map((p) => [p[0], p[1]]), story, layer, entities, out, value);
    for (const e of out) {
      e.groupId = g.id;
      e.annotationRole = 'surface-region-group';
      added.push(e);
    }

    // 5. The internal seam is DATA, not a drawn line: a confirmed group is one
    //    piece on the sheet. The shared edge stays recorded so the grouping is
    //    still auditable, and the source faces still exist in the registry.
    let seam = null;
    let withdrawnBoundary = 0;
    if (faces.length === 2) {
      const s = sharedSegment(faces[0].regionPlanM, faces[1].regionPlanM);
      if (s) {
        seam = { a: s.a, b: s.b };
        // The shared edge is also part of BOTH face perimeters, so the ceiling
        // outline drew it once. On the sheet that line is the last thing that
        // still reads as "two pieces": withdraw it, leaving one continuous
        // outline of the stitched union. The outer perimeter is untouched.
        const onSeam = (p, q) => (near(p, s.a) && near(q, s.b)) || (near(p, s.b) && near(q, s.a));
        for (let i = entities.length - 1; i >= 0; i -= 1) {
          const e = entities[i];
          if (!e || e.type !== 'line' || e.story !== story) continue;
          if (e.role !== 'source-region-boundary') continue;
          if (!onSeam(e.a, e.b)) continue;
          entities.splice(i, 1);
          withdrawnBoundary += 1;
        }
      } else warnings.push({ code: 'roomplan.surface-region-group-no-shared-edge', message: `Surface Region group ${g.id}: the member faces share no single edge; the group label still describes one slope, but no shared edge is recorded.` });
    }

    drawn.push({
      id: g.id,
      members: g.members.slice(),
      label: value,
      labelPolygonBasis: polyBasis,
      labelStatus: layout ? layout.status : null,
      replacedFaceLabels: removed,
      fallArrow: {
        keptMember: keptFace ? keptFace.sourceRegionId : null,
        withdrawnLines: withdrawnArrows,
        quantityEffect: 'none',
      },
      seamWithdrawn: seam ? { a: seam.a.map((v) => Math.round(v * 1000) / 1000), b: seam.b.map((v) => Math.round(v * 1000) / 1000), drawnOnSheet: false, layer: seamLayer, boundaryLinesWithdrawn: withdrawnBoundary, reason: 'confirmed group is one piece on the sheet; the shared edge and the coincident perimeter line are not drawn, the edge remains data in this record and the source faces remain in the registry' } : null,
      quantityEffect: 'none: group is a reference only; member faces and their areas are unchanged',
    });
  }
  return { added, drawn, warnings };
}

module.exports = { renderGroups, sharedSegment, stitchUnion, heightRange, groupTitle, insideRing };
