'use strict';
/**
 * Decoder for an "optimized RoomPlan" export (format_version: 1),
 * such as the files produced by Polycam-style room-scan post-processing.
 *
 * Unlike the raw Apple format, this one already carries an explicit `story`
 * per element/room and pre-computed room polygons + automated labels
 * (label_automated, category, area, floor_height).
 */
const crypto = require('crypto');

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
  if (v && typeof v === 'object') return Object.keys(v)[0] || null;
  if (typeof v === 'string') return v;
  throw new Error(`Malformed optimized RoomPlan JSON at ${path}`);
}

function decodeElement(record, kind, path) {
  const story = typeof record.story === 'number' ? record.story : 0;
  const identifier = kind === 'floor' ? `floor-${story}` : str(record.identifier, `${path}.identifier`);
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
    parentIdentifier: record.parentIdentifier || null,
    kind,
    category,
    categoryDetail: record.category_detail || null,
    confidence,
    story,
    dimensions,
    transform,
    // NOTE: kept in surface-local space (untransformed). polygonCorners is
    // only used for floors; transform and alignment are applied at
    // projection time. Walls/doors/windows/openings/objects are drawn as a
    // footprint/centerline computed purely from `dimensions` (+ wallThickness
    // for walls), so their polygonCorners is ignored here as well.
    polygonCorners: corners,
    wallThickness: typeof record.wall_thickness === 'number' ? record.wall_thickness : null,
  };
}

// Accepts either a column-major 16-number array, or the source's native
// object shape with
// keys t00,t10,t20,t30,t01,...,t33 (column-major, same order).
const ALIGNMENT_MATRIX_KEYS = ['t00','t10','t20','t30','t01','t11','t21','t31','t02','t12','t22','t32','t03','t13','t23','t33'];
function decodeAlignmentTransform(v) {
  if (Array.isArray(v)) return nums(v, 16, 'alignment_transform');
  if (v && typeof v === 'object') {
    return ALIGNMENT_MATRIX_KEYS.map((k) => num(v[k], `alignment_transform.${k}`));
  }
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
}

function decodeRoom(record, path) {
  const xs = nums(record.vertices_x, undefined, `${path}.vertices_x`);
  const zs = nums(record.vertices_z, undefined, `${path}.vertices_z`);
  if (xs.length !== zs.length || xs.length < 3) throw new Error(`Malformed optimized RoomPlan JSON at ${path}.vertices`);
  const center = nums(record.center_xz, 2, `${path}.center_xz`);
  const edges = Array.isArray(record.edges) ? record.edges : [];
  return {
    identifier: str(record.id, `${path}.id`),
    label: str(record.label_automated, `${path}.label_automated`),
    category: str(record.category, `${path}.category`),
    story: typeof record.story === 'number' ? record.story : 0,
    area: num(record.area, `${path}.area`),
    floorHeight: num(record.floor_height, `${path}.floor_height`),
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
  if (root.format_version !== 1) throw new Error(`Unsupported optimized RoomPlan format version ${root.format_version}`);

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
    sourceByteCount: buf.length,
    sourceSHA256: sha256(buf),
    originalFilename: originalFilename || null,
    storyAssignmentMethod: 'source-provided', // the source assigns `story` per element/room
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
