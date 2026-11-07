'use strict';
/**
 * Produces a `.roomplan.json` diagnostics manifest alongside the DXF output —
 * Every omission/assumption is
 * spelled out with a machine-readable code + human message, output is never
 * silently claimed to be lossless.
 */

function buildManifest(model, dxfResult, opts) {
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

  return {
    tool: 'roomplan-dxf',
    sourceFormat: model.kind,
    sourceFilename: model.originalFilename,
    sourceSHA256: model.sourceSHA256,
    storyCount: model.meta && model.meta.storyCount != null ? model.meta.storyCount : (model.rooms ? new Set(model.rooms.map((r) => r.story)).size : 1),
    storyAssignmentMethod: model.storyAssignmentMethod,
    architecturalAlignment: model.architecturalAlignment,
    entityCount: dxfResult.entityCount,
    layers: dxfResult.layers,
    lossy: true,
    warnings,
  };
}

module.exports = { buildManifest };
