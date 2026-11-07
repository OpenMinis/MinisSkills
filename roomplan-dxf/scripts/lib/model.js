'use strict';
/**
 * Common internal capture model shared by both RoomPlan sources:
 *  - "raw"       Apple's own CapturedRoom/CapturedStructure JSON (RoomPlan framework output)
 *  - "optimized" post-processed export (format_version: 1)
 *
 * Everything downstream (story assignment, architectural alignment, DXF writing)
 * only ever looks at this shape, so adding a third source later only means
 * adding another decode-*.js that returns this same structure.
 *
 * Capture = {
 *   kind: 'raw' | 'optimized',
 *   sourceByteCount, sourceSHA256, originalFilename,
 *   storyAssignmentMethod: string|null,
 *   surfaces: Surface[],   // walls, floors, doors, windows, openings
 *   objects: Obj[],        // furniture
 *   rooms: Room[]|null,    // optimized only — pre-computed room polygons + labels
 *   meta: {...source-specific extras, e.g. geo, mesh info, alignment}
 * }
 *
 * Surface = {
 *   identifier, parentIdentifier, kind: 'wall'|'floor'|'door'|'window'|'opening',
 *   confidence, story, dimensions: {x,y,z}, transform: number[16] (column-major),
 *   polygonCorners: {x,y,z}[], curve: {centerX,centerZ,radius,startAngleRadians,endAngleRadians}|null,
 *   isOpen: bool|null
 * }
 *
 * Obj = { identifier, parentIdentifier, category, confidence, story, dimensions, transform }
 *
 * Room = { identifier, label, category, story, area, floorHeight, centerX, centerZ,
 *          vertices: {x,z}[], edges: string[][] }
 */
module.exports = {};
