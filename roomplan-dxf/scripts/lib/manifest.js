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

  if (model.kind === 'optimized' && model.meta.orientationConfidence != null && model.meta.orientationConfidence < 0.8) {
    warnings.push({
      code: 'roomplan.compass-orientation-uncertain',
      message: `Source compass orientation confidence is ${model.meta.orientationConfidence} (< 0.8) — north-alignment metadata should not be trusted for this scan.`,
    });
  }

  const manifest = {
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

  // Location and compass are sensitive: they are written only on explicit
  // request (--geo) and never used to georeference the drawing geometry.
  if (opts && opts.includeGeo && model.meta) {
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
      manifest.sourceGeo = geo;
      manifest.warnings.push({
        code: 'roomplan.geo-metadata-included',
        message: 'Source location/compass metadata was requested and copied into this manifest; treat it as sensitive and do not publish it unredacted. It does not georeference the DXF.',
      });
    }
  }

  return manifest;
}

module.exports = { buildManifest };
