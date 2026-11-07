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
 * @param {object} [opts] { noFrame, planMeta } — planMeta is the title-block
 *   metadata from lib/plan-meta.js; when it is present (and noFrame is not
 *   set) the FRAME/TITLE/NORTH layers are declared here so that dxf-emit.py
 *   can draw sheet furniture around the untouched plan geometry.
 * @returns {{ plan: object, layers: string[], entityCount: number }}
 */
function buildDXF(model, opts) {
  const options = opts || {};
  const frame = !options.noFrame;
  const entities = [];
  const layerSet = new Set();
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  function track(x, y) {
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
  }
  function trackAll(pts) { pts.forEach(([x, y]) => track(x, y)); }

  // Per-story bounds. Every entity carries its own `story` so that
  // dxf-emit.py can lay each floor out in its own frame without re-deriving
  // the floor from the layer name (the layer prefix is still the same story).
  const storyBounds = new Map();
  let currentStory = 0;
  function trackStory(x, y) {
    let b = storyBounds.get(currentStory);
    if (!b) {
      b = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, count: 0 };
      storyBounds.set(currentStory, b);
    }
    if (x < b.minX) b.minX = x;
    if (x > b.maxX) b.maxX = x;
    if (y < b.minY) b.minY = y;
    if (y > b.maxY) b.maxY = y;
  }
  function trackAllStory(pts) { pts.forEach(([x, y]) => trackStory(x, y)); }
  function push(entity) {
    entity.story = currentStory;
    entities.push(entity);
    const b = storyBounds.get(currentStory);
    if (b) b.count += 1;
    else storyBounds.set(currentStory, { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, count: 1 });
  }

  const alignment = (model.architecturalAlignment && model.architecturalAlignment.matrix) || [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
  const isOptimized = model.kind === 'optimized';

  for (const s of model.surfaces) {
    currentStory = Number.isFinite(s.story) ? s.story : 0;
    const layer = layerFor(s.story, s.kind);
    layerSet.add(layer);

    if (s.kind === 'floor') {
      if (!s.polygonCorners || s.polygonCorners.length < 3) continue; // no usable polygon; skip (manifest warns separately)
      const pts = polygonDXF(s.polygonCorners, s.transform, alignment);
      trackAll(pts); trackAllStory(pts);
      push({ type: 'polyline', layer, points: pts, closed: true });
      continue;
    }

    if (s.kind === 'wall') {
      let pts;
      if (isOptimized) {
        const depth = s.wallThickness != null ? s.wallThickness : (s.dimensions.z > 0 ? s.dimensions.z : 0.1);
        pts = footprintDXF(s.dimensions.x, depth, s.transform, alignment);
        trackAll(pts); trackAllStory(pts);
        push({ type: 'polyline', layer, points: pts, closed: true });
      } else if (s.dimensions.z > 0) {
        pts = footprintDXF(s.dimensions.x, s.dimensions.z, s.transform, alignment);
        trackAll(pts); trackAllStory(pts);
        push({ type: 'polyline', layer, points: pts, closed: true });
      } else {
        const { a, b } = centerLineDXF(s.dimensions.x, s.transform, alignment);
        track(a[0], a[1]); track(b[0], b[1]);
        trackStory(a[0], a[1]); trackStory(b[0], b[1]);
        push({ type: 'line', layer, a, b });
      }
      continue;
    }

    if (s.kind === 'door' || s.kind === 'window' || s.kind === 'opening') {
      const { a, b } = centerLineDXF(s.dimensions.x, s.transform, alignment);
      track(a[0], a[1]); track(b[0], b[1]);
      trackStory(a[0], a[1]); trackStory(b[0], b[1]);
      push({ type: 'line', layer, a, b });
      continue;
    }
  }

  // Objects (furniture) -> a footprint rectangle at their transform (both formats).
  for (const o of model.objects) {
    currentStory = Number.isFinite(o.story) ? o.story : 0;
    const layer = layerFor(o.story, 'object');
    layerSet.add(layer);
    const pts = footprintDXF(o.dimensions.x, o.dimensions.z, o.transform, alignment);
    trackAll(pts); trackAllStory(pts);
    push({ type: 'polyline', layer, points: pts, closed: true });
  }

  // Room labels (optimized only — raw format has no room polygons/labels)
  if (Array.isArray(model.rooms)) {
    for (const r of model.rooms) {
      currentStory = Number.isFinite(r.story) ? r.story : 0;
      const roomLayer = layerFor(r.story, 'room');
      const labelLayer = layerFor(r.story, 'label');
      layerSet.add(roomLayer);
      layerSet.add(labelLayer);
      const localVerts = r.vertices.map((v) => ({ x: v.x, y: 0, z: v.z }));
      // Rooms have identity local transform (vertices already in the room's
      // own ground-plane space) — only the alignment matrix applies.
      const pts = polygonDXF(localVerts, [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1], alignment);
      trackAll(pts); trackAllStory(pts);
      push({ type: 'polyline', layer: roomLayer, points: pts, closed: true });
      const centerDXF = projectLocal({ x: r.centerX, y: 0, z: r.centerZ }, [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1], alignment);
      track(centerDXF.x, centerDXF.y);
      trackStory(centerDXF.x, centerDXF.y);
      push({ type: 'text', layer: labelLayer, pos: [centerDXF.x, centerDXF.y], height: 0.18, value: `${r.label ?? `[${r.category}; id=${r.identifier}]`}  ${r.area.toFixed(2)} m2` });
    }
  }

  let ceilingDiagnostics = {enabled:false,reason:'conservative default off; use --ceilings'};
  if(options.ceilings){
    const result=require('./ceilings').addCeilings(model,entities);
    ceilingDiagnostics=result.diagnostics;
    for(const entity of result.annotations){currentStory=entity.story;layerSet.add(entity.layer);const pts=entity.type==='line'?[entity.a,entity.b]:[entity.pos];trackAll(pts);trackAllStory(pts);push(entity);}
  }

  if (!Number.isFinite(minX)) { minX = maxX = minY = maxY = 0; }

  // Sheet furniture lives on its own layers; the plan geometry above is
  // already complete and is never modified by the frame.
  if (frame) {
    layerSet.add('FRAME');
    layerSet.add('TITLE');
    layerSet.add('NORTH');
  }

  // Per-story summary, sorted by story number. `bounds` here is in DRAWING
  // coordinates BEFORE dxf-emit.py places the sheets side by side; the placed
  // frames come back in the emitter summary and are what the manifest reports.
  const stories = Array.from(storyBounds.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([story, b]) => ({
      story,
      entityCount: b.count,
      bounds: Number.isFinite(b.minX)
        ? { minX: b.minX, maxX: b.maxX, minY: b.minY, maxY: b.maxY }
        // Degenerate (no tracked point) — fall back to the whole drawing so a
        // sheet is never laid out with a zero-size bbox.
        : { minX, maxX, minY, maxY },
      layers: Array.from(layerSet).filter((n) => n.startsWith(`S${story}_`)).sort(),
    }));

  const plan = {
    bounds: { minX, maxX, minZ: minY, maxZ: maxY },
    layers: Array.from(layerSet).sort(),
    entities,
    stories,
    frame,
    // One frame per story, side by side, whenever the plan has more than one.
    multiSheet: frame && stories.length > 1,
    meta: frame && options.planMeta ? (options.planMeta.dxfMeta || options.planMeta) : null,
  };

  return { plan, layers: plan.layers, entityCount: entities.length, stories: plan.stories, ceilingDiagnostics };
}

module.exports = { buildDXF, layerFor };
