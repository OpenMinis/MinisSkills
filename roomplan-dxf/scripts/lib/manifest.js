'use strict';
/**
 * Produces a `.roomplan.json` diagnostics manifest alongside the DXF output —
 * Every omission/assumption is
 * spelled out with a machine-readable code + human message, output is never
 * silently claimed to be lossless.
 */

function buildManifest(model, dxfResult, opts) {
  const options = opts || {};
  const planMeta = options.planMeta || null;
  const sourceMeta = options.sourceMeta || null;
  const warnings = [];

  if (model.kind === 'raw' && model.storyAssignmentMethod && model.storyAssignmentMethod.startsWith('multiroom floor-elevation')) {
    warnings.push({
      code: 'roomplan.story-assigned-by-clustering',
      message: `Story (floor level) was inferred by elevation clustering, not provided by source: ${model.storyAssignmentMethod}`,
    });
  }

  const wallsWithoutFootprint = model.surfaces.filter((s) => s.kind === 'wall' && s.dimensions.z <= 0 && model.kind === 'raw');
  if (wallsWithoutFootprint.length > 0) {
    warnings.push({
      code: 'roomplan.wall-no-thickness-centerline',
      message: `${wallsWithoutFootprint.length} wall(s) had dimensions.z <= 0 (no captured thickness); drawn as a centerline instead of a footprint rectangle — the documented behaviour for this case.`,
    });
  }

  if (!model.rooms) {
    warnings.push({
      code: 'roomplan.no-room-polygons-raw-format',
      message: 'Raw Apple RoomPlan format carries no pre-computed room polygons/labels — only wall/floor/door/window/object geometry was exported. Use an optimized-format source for room-level output.',
    });
  }

  if (model.kind === 'optimized' && model.meta.orientationUncertaintyDegrees != null && model.meta.orientationUncertaintyDegrees > 10) {
    warnings.push({
      code: 'roomplan.compass-orientation-uncertain',
      message: `Source compass orientation uncertainty is ${model.meta.orientationUncertaintyDegrees}°, exceeding 10° — north-alignment metadata should not be trusted for this scan.`,
    });
  }

  if (model.kind === 'optimized' && model.meta.orientationConfidence != null && model.meta.orientationConfidence < 0.8) {
    warnings.push({
      code: 'roomplan.compass-orientation-uncertain',
      message: `Source compass orientation confidence is ${model.meta.orientationConfidence} (< 0.8) — north-alignment metadata should not be trusted for this scan.`,
    });
  }

  if (sourceMeta) {
    if (options.metaFallbackFields && options.metaFallbackFields.length > 0) {
      warnings.push({
        code: 'roomplan.meta-metadata-fallback',
        message: `The scan carries no ${options.metaFallbackFields.join('/')}; those values were taken from ${options.metaRelative || 'meta.json'}.`,
      });
    }
    if (options.metaFallbackFields && options.metaFallbackFields.includes('orientationDegrees')) {
      warnings.push({
        code: 'roomplan.heading-from-meta',
        message: `Orientation (${sourceMeta.headingDegrees}°) comes from meta.json headingDegrees, not from the scan's own compass reading — the north arrow is drawn from it and marked approximate, not a surveyed bearing.`,
      });
    }
  }
  if (options.otherScanCandidates && options.otherScanCandidates.length > 0) {
    warnings.push({
      code: 'roomplan.directory-multiple-scans',
      message: `The input directory holds more than one scan candidate; ${options.scanRelative} was used by the documented priority and these were ignored: ${options.otherScanCandidates.join(', ')}.`,
    });
  }
  if (planMeta && planMeta.warnings) {
    for (const warning of planMeta.warnings) warnings.push(warning);
  }
  if (!planMeta) {
    warnings.push({
      code: 'roomplan.no-title-block',
      message: 'No sheet frame/title block was drawn (--no-frame); the DXF contains plan geometry only.',
    });
  }

  // ---- per-story sheets ---------------------------------------------------
  const planStories = dxfResult.stories || [];
  const emittedSheets = (options.emitted && Array.isArray(options.emitted.sheets))
    ? options.emitted.sheets
    : [];
  const sheetByStory = new Map(emittedSheets.map((s) => [s.story, s]));
  const storyCount = planStories.length;
  const separated = storyCount > 1 && emittedSheets.length > 1;

  const stories = planStories.map((s) => {
    const sheet = sheetByStory.get(s.story);
    const local = s.bounds || {};
    const placed = sheet && sheet.bbox
      ? sheet.bbox
      : [local.minX, local.minY, local.maxX, local.maxY];
    return {
      story: s.story,
      label: s.label || null,
      entityCount: sheet && sheet.entityCount != null ? sheet.entityCount : s.entityCount,
      bbox: placed,
      // bbox source matters: 'sheet' = placed in the final DXF, 'local' =
      // drawing coordinates before any multi-sheet layout (--no-frame).
      bboxSource: sheet && sheet.bbox ? 'sheet' : 'local',
      frame: sheet ? sheet.frame : null,
      layers: s.layers || [],
    };
  });

  const storyWarning = [];
  if (storyCount > 1 && !separated) {
    storyWarning.push({
      code: 'roomplan.stories-not-separated',
      message: `The plan has ${storyCount} stories (${stories.map((s) => s.story).join(', ')}) but they were NOT split into separate frames: ${options.noFrame ? '--no-frame draws one common plan' : 'no multi-sheet layout was produced'}. Floors overlap in this drawing; do not read it as a single-level plan.`,
    });
  }
  if (storyCount > 1 && separated) {
    const boxes = stories.map((s) => s.bbox).filter((b) => Array.isArray(b));
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i];
        const b = boxes[j];
        if (a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]) {
          storyWarning.push({
            code: 'roomplan.story-bbox-overlap',
            message: `Placed bounding boxes of stories ${stories[i].story} and ${stories[j].story} overlap — the per-story layout did not separate them.`,
          });
        }
      }
    }
  }
  for (const w of storyWarning) warnings.push(w);

  const out = {
    tool: 'roomplan-dxf',
    sourceFormat: model.kind,
    sourceFilename: model.originalFilename,
    sourceSHA256: model.sourceSHA256,
    inputKind: options.inputWasDirectory ? 'directory' : 'file',
    sourceMetadata: sourceMeta ? 'meta.json' : null,
    sourceMetadataFile: sourceMeta ? (options.metaRelative || 'meta.json') : null,
    metadataFallbackFields: options.metaFallbackFields && options.metaFallbackFields.length > 0 ? options.metaFallbackFields : [],
    sourceMeta: sourceMeta ? {
      name: sourceMeta.name,
      roomCount: sourceMeta.roomCount,
      floorAreaSquareMetres: sourceMeta.floorAreaSquareMetres,
      createdAt: sourceMeta.createdAt ? sourceMeta.createdAt.iso : null,
      createdAtConvention: sourceMeta.createdAt ? sourceMeta.createdAt.convention : null,
      headingDegrees: sourceMeta.headingDegrees,
    } : null,
    storyCount: model.meta && model.meta.storyCount != null ? model.meta.storyCount : (model.rooms ? new Set(model.rooms.map((r) => r.story)).size : 1),
    storyAssignmentMethod: model.storyAssignmentMethod,
    architecturalAlignment: model.architecturalAlignment,
    entityCount: options.emitted && options.emitted.entityCount != null ? options.emitted.entityCount : dxfResult.entityCount,
    geometryEntityCount: dxfResult.entityCount,
    layers: dxfResult.layers,
    titleBlock: planMeta ? planMeta.titleBlock : null,
    // Reverse-geocode attempt, if the operator asked for one. `status` is
    // ok | failed | unavailable | no-coordinates; null means "not requested".
    placeLookup: planMeta && planMeta.placeLookup ? planMeta.placeLookup : null,
    northArrow: planMeta ? planMeta.north : null,
    frame: planMeta ? planMeta.titleBlock.frame : false,
    stories,
    sheetLayout: options.emitted ? {
      mode: (options.emitted.layout && options.emitted.layout.mode) || 'single-sheet',
      sheetCount: options.emitted.sheetCount != null ? options.emitted.sheetCount : emittedSheets.length,
      // Horizontal gap between per-story frames, as a fraction of the widest
      // frame width. Documented layout rule, not a cosmetic guess.
      gapRatio: options.emitted.layout ? options.emitted.layout.gapRatio : 0.08,
      gap: options.emitted.layout && options.emitted.layout.gap != null
        ? options.emitted.layout.gap : null,
      storiesSeparated: separated,
    } : {
      mode: 'none',
      sheetCount: 0,
      gapRatio: 0.08,
      gap: null,
      storiesSeparated: false,
    },
    sheetFurniture: options.emitted && planMeta ? {
      frameBounds: options.emitted.frame || null,
      titleBlockBounds: options.emitted.titleBlock || null,
      northArrow: options.emitted.northArrow || null,
      // One entry per drawn sheet: frame, title block cells and north arrow of
      // THAT sheet. Cells carry the fitted text height and the drawn string so
      // the text-in-cell rule is machine-checkable.
      sheets: emittedSheets.map((s) => ({
        story: s.story,
        label: s.label,
        bbox: s.bbox,
        frame: s.frame,
        titleBlock: s.titleBlock,
        northArrow: s.northArrow,
      })),
    } : null,
    lossy: true,
    warnings,
  };

  // Location and compass are sensitive: they are written only on explicit
  // request (--geo) and never used to georeference the drawing geometry.
  // The north arrow is separate: it uses the heading regardless of --geo,
  // because orientation is not a location.
  if (options.includeGeo && model.meta) {
    const geo = {};
    for (const [key, value] of Object.entries({
      latitude: model.meta.latitude,
      longitude: model.meta.longitude,
      altitude: model.meta.altitude,
      orientationDegrees: model.meta.orientationDegrees,
      orientationUncertaintyDegrees: model.meta.orientationUncertaintyDegrees,
      orientationConfidence: model.meta.orientationConfidence,
    })) {
      if (value != null) geo[key] = value;
    }
    if (Object.keys(geo).length > 0) {
      out.sourceGeo = geo;
      out.warnings.push({
        code: 'roomplan.geo-metadata-included',
        message: 'Source location/compass metadata was requested and copied into this manifest; treat it as sensitive and do not publish it unredacted. It does not georeference the DXF.',
      });
    }
  }

  return out;
}

module.exports = { buildManifest };
