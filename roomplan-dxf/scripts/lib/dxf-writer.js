'use strict';
/**
 * Builds an entity PLAN (plain JSON) for the RoomPlan/Optimized-RoomPlan
 * export path.
 *
 * Geometry rules (verified against reference output — do NOT "improve"
 * these without re-checking, since deviating here caused earlier visual
 * mismatches against real CAD output):
 *   - floor:  polygonCorners, transformed by (alignment ∘ surface.transform), projected.
 *   - wall (raw):        dimensions.z > 0 -> footprint(width=dims.x, depth=dims.z);
 *                         else               -> centerLine(width=dims.x).
 *                         polygonCorners is NEVER used for walls.
 *   - wall (optimized):  always footprint(width=dims.x, depth=wallThickness||dims.z||0.1).
 *   - door/window/opening: always centerLine(width=dims.x). polygonCorners unused.
 *   - object (raw):       footprint(width=dims.x, depth=dims.z) — a rectangle, not a label.
 *   - object (optimized): footprint(width=dims.x, depth=dims.z).
 *   - room (optimized only): polyline from room.vertices + a TEXT label at its center.
 *
 * All local points go through `transform` (surface's own 4x4) THEN
 * `alignment` (architectural alignment, composed on the left — i.e. applied
 * after), THEN `project` (x, -z) to get final DXF (x, y). This mirrors
 * the reference pipeline: compose(alignment, surface.transform), apply,
 * then project.
 *
 * The actual DXF *file* is written by `dxf-emit.py` (via the `ezdxf`
 * library) — see that file's docstring for why a hand-rolled ASCII DXF
 * writer isn't safe for real AutoCAD.
 */
const { apply, multiply, project } = require('./transform');

function layerFor(story, kind) {
  return `S${story}_${String(kind).toUpperCase()}`;
}

// composed(alignment, surfaceTransform) then apply to a local point, then project.
function projectLocal(localPoint, surfaceTransform, alignmentMatrix) {
  const composed = multiply(alignmentMatrix, surfaceTransform);
  const worldPoint = apply(composed, localPoint);
  return project(worldPoint);
}

function centerLineDXF(width, surfaceTransform, alignmentMatrix) {
  const a = projectLocal({ x: -width / 2, y: 0, z: 0 }, surfaceTransform, alignmentMatrix);
  const b = projectLocal({ x: width / 2, y: 0, z: 0 }, surfaceTransform, alignmentMatrix);
  return { a: [a.x, a.y], b: [b.x, b.y] };
}

function footprintDXF(width, depth, surfaceTransform, alignmentMatrix) {
  const local = [
    { x: -width / 2, y: 0, z: -depth / 2 },
    { x: width / 2, y: 0, z: -depth / 2 },
    { x: width / 2, y: 0, z: depth / 2 },
    { x: -width / 2, y: 0, z: depth / 2 },
  ];
  return local.map((p) => {
    const dp = projectLocal(p, surfaceTransform, alignmentMatrix);
    return [dp.x, dp.y];
  });
}

function polygonDXF(localPoints, surfaceTransform, alignmentMatrix) {
  return localPoints.map((p) => {
    const dp = projectLocal(p, surfaceTransform, alignmentMatrix);
    return [dp.x, dp.y];
  });
}

/**
 * @param {object} model decoded + story-assigned + architecturally-aligned model
 * @returns {{ plan: object, layers: string[], entityCount: number }}
 */
function buildDXF(model) {
  const entities = [];
  const layerSet = new Set();
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  function track(x, y) {
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
  }
  function trackAll(pts) { pts.forEach(([x, y]) => track(x, y)); }

  const alignment = (model.architecturalAlignment && model.architecturalAlignment.matrix) || [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
  const isOptimized = model.kind === 'optimized';

  for (const s of model.surfaces) {
    const layer = layerFor(s.story, s.kind);
    layerSet.add(layer);

    if (s.kind === 'floor') {
      if (!s.polygonCorners || s.polygonCorners.length < 3) continue; // no usable polygon; skip (manifest warns separately)
      const pts = polygonDXF(s.polygonCorners, s.transform, alignment);
      trackAll(pts);
      entities.push({ type: 'polyline', layer, points: pts, closed: true });
      continue;
    }

    if (s.kind === 'wall') {
      let pts;
      if (isOptimized) {
        const depth = s.wallThickness != null ? s.wallThickness : (s.dimensions.z > 0 ? s.dimensions.z : 0.1);
        pts = footprintDXF(s.dimensions.x, depth, s.transform, alignment);
        trackAll(pts);
        entities.push({ type: 'polyline', layer, points: pts, closed: true });
      } else if (s.dimensions.z > 0) {
        pts = footprintDXF(s.dimensions.x, s.dimensions.z, s.transform, alignment);
        trackAll(pts);
        entities.push({ type: 'polyline', layer, points: pts, closed: true });
      } else {
        const { a, b } = centerLineDXF(s.dimensions.x, s.transform, alignment);
        track(a[0], a[1]); track(b[0], b[1]);
        entities.push({ type: 'line', layer, a, b });
      }
      continue;
    }

    if (s.kind === 'door' || s.kind === 'window' || s.kind === 'opening') {
      const { a, b } = centerLineDXF(s.dimensions.x, s.transform, alignment);
      track(a[0], a[1]); track(b[0], b[1]);
      entities.push({ type: 'line', layer, a, b });
      continue;
    }
  }

  // Objects (furniture) -> a footprint rectangle at their transform (both formats).
  for (const o of model.objects) {
    const layer = layerFor(o.story, 'object');
    layerSet.add(layer);
    const pts = footprintDXF(o.dimensions.x, o.dimensions.z, o.transform, alignment);
    trackAll(pts);
    entities.push({ type: 'polyline', layer, points: pts, closed: true });
  }

  // Room labels (optimized only — raw format has no room polygons/labels)
  if (Array.isArray(model.rooms)) {
    for (const r of model.rooms) {
      const roomLayer = layerFor(r.story, 'room');
      const labelLayer = layerFor(r.story, 'label');
      layerSet.add(roomLayer);
      layerSet.add(labelLayer);
      const localVerts = r.vertices.map((v) => ({ x: v.x, y: 0, z: v.z }));
      // Rooms have identity local transform (vertices already in the room's
      // own ground-plane space) — only the alignment matrix applies.
      const pts = polygonDXF(localVerts, [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1], alignment);
      trackAll(pts);
      entities.push({ type: 'polyline', layer: roomLayer, points: pts, closed: true });
      const centerDXF = projectLocal({ x: r.centerX, y: 0, z: r.centerZ }, [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1], alignment);
      track(centerDXF.x, centerDXF.y);
      entities.push({ type: 'text', layer: labelLayer, pos: [centerDXF.x, centerDXF.y], height: 0.18, value: `${r.label}  ${r.area.toFixed(2)} m2` });
    }
  }

  if (!Number.isFinite(minX)) { minX = maxX = minY = maxY = 0; }

  const plan = {
    bounds: { minX, maxX, minZ: minY, maxZ: maxY },
    layers: Array.from(layerSet).sort(),
    entities,
  };

  return { plan, layers: plan.layers, entityCount: entities.length };
}

module.exports = { buildDXF, layerFor };
