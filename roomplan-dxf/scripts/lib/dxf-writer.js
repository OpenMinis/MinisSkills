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
  const floorAreaByStory = new Map();
  const isOptimized = model.kind === 'optimized';

  for (const s of model.surfaces) {
    currentStory = Number.isFinite(s.story) ? s.story : 0;
    const layer = layerFor(s.story, s.kind);
    layerSet.add(layer);

    if (s.kind === 'floor') {
      if (!s.polygonCorners || s.polygonCorners.length < 3) continue; // no usable polygon; skip (manifest warns separately)
      const pts = polygonDXF(s.polygonCorners, s.transform, alignment);
      trackAll(pts); trackAllStory(pts);
      // shoelace area of the drawn footprint: the datum for a story label when
      // no ceiling could be reconstructed
      let area = 0;
      for (let i = 0; i < pts.length; i += 1) {
        const [x1, y1] = pts[i];
        const [x2, y2] = pts[(i + 1) % pts.length];
        area += x1 * y2 - x2 * y1;
      }
      floorAreaByStory.set(currentStory, (floorAreaByStory.get(currentStory) || 0) + Math.abs(area) / 2);
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

  // Room labels. Heights come from lib/ceiling-3d.js, i.e. from the SAME
  // reconstruction the ceiling annotations use; a height is never invented and
  // never omitted when it was determined.
  const { ceilingHeights } = require('./ceiling-3d');
  const labelHeights = ceilingHeights(model);
  const labelledStories = new Set();
  const roomLabelText = (name, area, h) => {
    const parts = [name, `${area.toFixed(2)} m2`];
    // Heights are region annotations, not a duplicate room title.
    return parts.join('  ');
  };
  const storyLabelText = (story, area, h) => {
    const parts = [`Kat ${story}`, `${area.toFixed(2)} m2`];
    // Heights are region annotations, not a duplicate room title.
    return parts.join('  ');
  };

  // Room labels (optimized — raw format has no room polygons/labels)
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
      const h = labelHeights.byRoom.get(String(r.identifier)) || labelHeights.byStory.get(currentStory) || null;
      const value=roomLabelText(r.label ?? `[${r.category}; id=${r.identifier}]`, r.area, (r.ceilingCurrent?.length||r.ceiling?.length)?null:h);
      const placed=[];require('./ceiling-layout').place(pts,currentStory,labelLayer,entities,placed,value);
      for(const e of placed){if(e.pos){track(...e.pos);trackStory(...e.pos);}push(e);}
      labelledStories.add(currentStory);
    }
  }

  // Story-level label: raw captures have no room polygons at all, and a plan
  // with no text on it leaves the user without the one number they came for.
  // Placed at the centre of the story's bounding box, area from the ceiling
  // (footprint) or the floor polylines, height from the reconstruction.
  for (const [story, b] of storyBounds) {
    if (labelledStories.has(story)) continue;
    if (!Number.isFinite(b.minX)) continue;
    const floorArea = floorAreaByStory.get(story);
    const h = labelHeights.byStory.get(story) || null;
    // Room/floor area, not the ceiling area: the slope surplus belongs to the
    // ceiling, and a plan label must state the floor the user stands on.
    const area = floorArea > 0 ? floorArea : (h && Number.isFinite(h.area) && h.area > 0 ? h.area : null);
    if (!(area > 0)) continue;
    currentStory = story;
    const layer = layerFor(story, 'label');
    layerSet.add(layer);
    const cx = (b.minX + b.maxX) / 2;
    const cy = (b.minY + b.maxY) / 2;
    track(cx, cy);
    trackStory(cx, cy);
    const f=model.surfaces.find(s=>s.kind==='floor'&&s.story===story&&s.polygonCorners?.length>=3);
    const region=f?polygonDXF(f.polygonCorners,f.transform,alignment):[[b.minX,b.minY],[b.maxX,b.minY],[b.maxX,b.maxY],[b.minX,b.maxY]];
    const placed=[];require('./ceiling-layout').place(region,story,layer,entities,placed,storyLabelText(story,area,h));
    for(const e of placed){if(!f)e.regionBasis='story bbox, not measured room';if(e.pos){track(...e.pos);trackStory(...e.pos);}push(e);}
  }

  // Ceilings are ON by default: a plan without its ceiling is a plan the user
  // asked for and did not get. --no-ceilings is the explicit opt-out.
  let ceilingDiagnostics = {enabled:false,reason:'disabled by --no-ceilings'};
  if(options.ceilings !== false){
    const result=require('./ceilings').addCeilings(model,entities);
    ceilingDiagnostics=result.diagnostics;
    for(const entity of result.annotations){currentStory=entity.story;layerSet.add(entity.layer);const pts=entity.type==='line'?[entity.a,entity.b]:[entity.pos];trackAll(pts);trackAllStory(pts);push(entity);}
    // A confirmed Surface Region group is drawn ONCE for the whole slope: the
    // per-face SR labels and the extra per-face fall arrows are withdrawn, and
    // one group label plus one arrow replace them. The internal seam is NOT
    // drawn — a confirmed group is one piece on the sheet. Registry, areas and
    // faces are unchanged; the seam stays in the manifest as data.
    if(options.surfaceRegionGroups){
      const groupDraw=require('./surface-region-draw').renderGroups(entities,ceilingDiagnostics.records||[],options.surfaceRegionGroups,options.sourceSHA256);
      ceilingDiagnostics.surfaceRegionDraw=groupDraw.drawn;
      ceilingDiagnostics.warnings=(ceilingDiagnostics.warnings||[]).concat(groupDraw.warnings);
      for(const entity of groupDraw.added){currentStory=entity.story;layerSet.add(entity.layer);const pts=entity.type==='line'?[entity.a,entity.b]:[entity.pos];trackAll(pts);trackAllStory(pts);push(entity);}
    }
  }

  // Text insert is NOT its full extent; reserve review strip, then pack sheets.
  const sheetAnnotations = require('./ceiling-layout').finalizeSheetAnnotations(entities);
  for (const sheet of sheetAnnotations) {
    const b=storyBounds.get(sheet.story);if(b)Object.assign(b,sheet.bounds);
    track(sheet.bounds.minX,sheet.bounds.minY);track(sheet.bounds.maxX,sheet.bounds.maxY);
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
    annotationStrips: sheetAnnotations,
    meta: frame && options.planMeta ? (options.planMeta.dxfMeta || options.planMeta) : null,
  };

  return { plan, layers: plan.layers, entityCount: entities.length, stories: plan.stories, ceilingDiagnostics };
}

module.exports = { buildDXF, layerFor };
