'use strict';
/**
 * Decoder for Polycam-style "optimized RoomPlan" export (format_version: 1),
 * ported from Sources/RoomPlanRaw/OptimizedRoomPlanJSONDecoder.swift.
 *
 * Unlike the raw Apple format, this one already carries an explicit `story`
 * per element/room and pre-computed room polygons + automated labels
 * (label_automated, category, area, floor_height).
 */
const crypto = require('crypto');
const validate = require('./validate');
const {detectDialect} = require('./dialect');

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

const ELEMENT_KEYS = { wall: 'walls', floor: 'floors', door: 'doors', window: 'windows', opening: 'openings', object: 'objects' };

function num(v, path) {
  if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error(`Malformed optimized RoomPlan JSON at ${path}`);
  return v;
}
function nums(arr, count, path) {
  if (!Array.isArray(arr) || (count != null && arr.length !== count)) {
    throw new Error(`Malformed optimized RoomPlan JSON at ${path}`);
  }
  return arr.map((v, i) => num(v, `${path}[${i}]`));
}
function str(v, path) {
  if (typeof v !== 'string' || v.length === 0) throw new Error(`Malformed optimized RoomPlan JSON at ${path}`);
  return v;
}
function taggedName(v, path) {
  if (v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 1) return Object.keys(v)[0];
  if (typeof v === 'string') return v;
  throw new Error(`Malformed optimized RoomPlan JSON at ${path}`);
}

function decodeElement(record, kind, path) {
  validate.element(record, path, kind === 'floor');
  const story = typeof record.story === 'number' ? record.story : 0;
  const identifier = record.identifier != null ? str(record.identifier, `${path}.identifier`) : (kind === 'floor' ? `floor-${story}-${path}` : str(record.identifier, `${path}.identifier`));
  const dimensions = kind === 'floor'
    ? { x: 1, y: 0, z: 0 }
    : (() => { const a = nums(record.dimensions, 3, `${path}.dimensions`); return { x: a[0], y: a[1], z: a[2] }; })();
  const category = kind === 'floor' ? 'floor' : taggedName(record.category, `${path}.category`);
  let confidence = null;
  if (record.confidence != null) confidence = taggedName(record.confidence, `${path}.confidence`);
  const corners = Array.isArray(record.polygonCorners)
    ? record.polygonCorners.map((p, i) => { const a = nums(p, 3, `${path}.polygonCorners[${i}]`); return { x: a[0], y: a[1], z: a[2] }; })
    : [];
  const transform = nums(record.transform, 16, `${path}.transform`);
  return {
    identifier,
    identifierProvenance: record.identifier != null ? 'source.identifier' : `generated from ${path}; source identifier absent`,
    sourceRecordIndex: path,
    dimensionsProvenance: kind === 'floor' ? 'DXF placeholder (1,0,0); floor geometry is polygonCorners; original dimensions, if any, retained in sourceRecords' : 'source.dimensions',
    parentIdentifier: record.parentIdentifier || null,
    kind,
    category,
    categoryDetail: record.category_detail || null,
    confidence,
    sourceStory: record.story ?? null,
    sourceStoryProvenance: record.story == null ? 'default 0 for DXF; not measured' : 'source record',
    story,
    dimensions,
    transform,
    // NOTE: kept in surface-local space (untransformed) — Swift's
    // OptimizedRoomPlanProjector only ever uses polygonCorners for floors,
    // and applies `transform` then `alignment` to them at projection time
    // (see geometry(_:alignment:) case .floor). Walls/doors/windows/openings/
    // objects are always drawn as a footprint/centerline computed purely
    // from `dimensions` (+ wallThickness for walls) — polygonCorners on
    // those kinds is unused by the reference implementation and so is here.
    polygonCorners: corners,
    curve: record.curve ? {
      centerX: record.curve.centerX ?? record.curve.center_x,
      centerZ: record.curve.centerZ ?? record.curve.center_z,
      radius: record.curve.radius,
      startAngleRadians: record.curve.startAngleRadians ?? record.curve.start_angle,
      endAngleRadians: record.curve.endAngleRadians ?? record.curve.end_angle,
    } : null,
    isOpen: kind === 'door' ? (record.isOpen ?? record.category?.door?.isOpen ?? null) : null,
    attributes: record.attributes || null,
    sections: record.sections || null,
    wallThickness: typeof record.wall_thickness === 'number' ? record.wall_thickness : null,
  };
}

// Ported from OptimizedRoomPlanJSONDecoder.matrixObject: accepts either a
// column-major 16-number array, or the source's native object shape with
// keys t00,t10,t20,t30,t01,...,t33 (column-major, same order).
const ALIGNMENT_MATRIX_KEYS = ['t00','t10','t20','t30','t01','t11','t21','t31','t02','t12','t22','t32','t03','t13','t23','t33'];
function decodeAlignmentTransform(v) {
  if (Array.isArray(v)) return validate.matrix(nums(v, 16, 'alignment_transform'), 'alignment_transform');
  if (v && typeof v === 'object') {
    return validate.matrix(ALIGNMENT_MATRIX_KEYS.map((k) => num(v[k], `alignment_transform.${k}`)), 'alignment_transform');
  }
  if (v !== undefined) throw new Error('Malformed optimized RoomPlan JSON at alignment_transform');
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
}

function decodeRoom(record, path) {
  validate.optimizedRoom(record, path);
  const xs = nums(record.vertices_x, undefined, `${path}.vertices_x`);
  const zs = nums(record.vertices_z, undefined, `${path}.vertices_z`);
  if (xs.length !== zs.length || xs.length < 3) throw new Error(`Malformed optimized RoomPlan JSON at ${path}.vertices`);
  const center = nums(record.center_xz, 2, `${path}.center_xz`);
  const edges = Array.isArray(record.edges) ? record.edges : [];
  return {
    identifier: str(record.id, `${path}.id`),
    label: record.label_automated == null ? null : str(record.label_automated, `${path}.label_automated`),
    labelProvenance: record.label_automated == null ? 'absent; category/id are source classifications, not measured names' : 'source.label_automated',
    curvedEdges: record.curved_edges || [],
    outerHull: record.outer_hull ?? null,
    ceiling: record.ceiling ?? null,
    ceilingCurrent: record.ceiling_curr ?? null,
    doorIdentifiers: record.doors || [],
    openingIdentifiers: record.openings || [],
    windowIdentifiers: record.windows || [],
    category: str(record.category, `${path}.category`),
    sourceStory: record.story ?? null,
    sourceStoryProvenance: record.story == null ? 'default 0 for DXF; not measured' : 'source record',
    story: typeof record.story === 'number' ? record.story : 0,
    area: num(record.area, `${path}.area`),
    floorHeight: record.floor_height == null ? null : num(record.floor_height, `${path}.floor_height`),
    centerX: center[0],
    centerZ: center[1],
    vertices: xs.map((x, i) => ({ x, z: zs[i] })),
    edges,
    ceilingLidarAverageDifference: typeof record.ceiling_lidar_avg_diff === 'number' ? record.ceiling_lidar_avg_diff : null,
    ceilingLidarValidFraction: typeof record.ceiling_lidar_valid_pct === 'number' ? record.ceiling_lidar_valid_pct : null,
  };
}

/**
 * @param {Buffer|string} data raw JSON bytes/text
 * @param {string|null} originalFilename
 */
function decode(data, originalFilename) {
  const buf = Buffer.isBuffer(data) ? data : Buffer.from(String(data), 'utf8');
  const root = JSON.parse(buf.toString('utf8'));
  const dialect = detectDialect(root);
  if (dialect.kind !== 'optimized') throw new Error('Expected optimized RoomPlan geometry');
  validate.geo(root);
  validate.sourceGeometry(root);
  if (!Array.isArray(root.walls) || root.walls.length === 0 || !Array.isArray(root.rooms)) throw new Error('Malformed optimized RoomPlan: requires walls[] and rooms[]');
  for (const key of Object.values(ELEMENT_KEYS)) if (root[key] != null && !Array.isArray(root[key])) throw new Error(`Malformed optimized RoomPlan at ${key}: expected array`);

  const elements = [];
  for (const [kind, key] of Object.entries(ELEMENT_KEYS)) {
    const arr = Array.isArray(root[key]) ? root[key] : [];
    arr.forEach((r, i) => elements.push(decodeElement(r, kind, `${key}[${i}]`)));
  }
  const rooms = Array.isArray(root.rooms) ? root.rooms.map((r, i) => decodeRoom(r, `rooms[${i}]`)) : [];
  const alignmentTransform = decodeAlignmentTransform(root.alignment_transform);

  const geo = root.latLonAlt || {};
  const orientation = root.orientation || {};

  return {
    kind: 'optimized',
    dialect: dialect.dialect,
    dialectEvidence: dialect.evidence,
    sourceByteCount: buf.length,
    sourceSHA256: sha256(buf),
    originalFilename: originalFilename || null,
    storyAssignmentMethod: [...elements,...rooms].every(e=>e.sourceStory!=null) ? 'source-provided' : 'source-provided; missing story defaults to 0 for DXF (not measured)',
    surfaces: elements.filter((e) => e.kind !== 'object'),
    objects: elements.filter((e) => e.kind === 'object'),
    rooms,
    meta: {
      formatVersion: root.format_version,
      alignmentTransform,
      latitude: geo.latitude ?? null,
      longitude: geo.longitude ?? null,
      altitude: geo.altitude ?? null,
      orientationDegrees: orientation.orientation_degrees ?? null,
      orientationUncertaintyDegrees: orientation.uncertainty_degrees ?? null,
      orientationConfidence: orientation.confidence ?? null,
      jointCount: Array.isArray(root.joints) ? root.joints.length : 0,
    },
  };
}

module.exports = { decode };
