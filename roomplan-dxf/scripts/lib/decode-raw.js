'use strict';
/**
 * Decoder for Apple's own RoomPlan JSON (CapturedRoom / CapturedStructure export),
 * ported from Sources/RoomPlanRaw/AppleRoomPlanJSONDecoder.swift.
 *
 * Accepts:
 *  - a single CapturedRoom object: { walls, floors, doors, windows, openings, objects, story? }
 *  - a CapturedStructure export: { rooms: [CapturedRoom, ...] }
 *  - an app-specific wrapper: { captureSessions: [ { roomplanSessions: [CapturedRoom, ...] } ] }
 *
 * IMPORTANT: polygonCorners and transform are kept exactly as decoded (local,
 * untransformed) — Swift's RoomPlanRawProjector applies `surface.transform`
 * and the architectural-alignment transform together at projection time
 * (composed(alignment, surface.transform)), not at decode time. Pre-applying
 * transform here would double-transform once align.js/dxf-writer.js run.
 */
const crypto = require('crypto');
const validate = require('./validate');
const {detectDialect} = require('./dialect');

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

const SURFACE_KINDS = ['walls', 'floors', 'doors', 'windows', 'openings'];

function num(v, path) {
  if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error(`Malformed raw RoomPlan JSON at ${path}`);
  return v;
}
function nums(arr, count, path) {
  if (!Array.isArray(arr) || (count != null && arr.length !== count)) {
    throw new Error(`Malformed raw RoomPlan JSON at ${path}`);
  }
  return arr.map((v, i) => num(v, `${path}[${i}]`));
}
function str(v, path) {
  if (typeof v !== 'string' || v.length === 0) throw new Error(`Malformed raw RoomPlan JSON at ${path}`);
  return v;
}
function tagged(v,path,fallback=null) {
  if(v==null) return fallback;
  if(typeof v==='string' && v.length) return v;
  if(v && typeof v==='object' && !Array.isArray(v) && Object.keys(v).length===1) return Object.keys(v)[0];
  throw new Error(`Malformed raw RoomPlan JSON at ${path}: expected unambiguous tag`);
}
function dims(v, path) {
  const a = nums(v, 3, path);
  return { x: a[0], y: a[1], z: a[2] };
}
function points(arr, path) {
  if (!Array.isArray(arr)) throw new Error(`Malformed raw RoomPlan JSON at ${path}`);
  return arr.map((p, i) => {
    const a = nums(p, 3, `${path}[${i}]`);
    return { x: a[0], y: a[1], z: a[2] };
  });
}

/**
 * Locate the room-record list inside whatever wrapper shape the source uses.
 * Ported from AppleRoomPlanJSONDecoder.roomRecords(in:).
 */
function roomRecords(root) {
  if (root.walls) return [root];
  if (Array.isArray(root.rooms)) {
    if (root.rooms.length === 0) throw new Error('Malformed raw RoomPlan JSON at rooms');
    return root.rooms;
  }
  if (Array.isArray(root.captureSessions)) {
    if (root.captureSessions.length === 0) throw new Error('Malformed raw RoomPlan JSON at captureSessions');
    let out = [];
    for (const cs of root.captureSessions) {
      if (!Array.isArray(cs.roomplanSessions) || cs.roomplanSessions.length === 0) {
        throw new Error('Malformed raw RoomPlan JSON at captureSessions[].roomplanSessions');
      }
      out = out.concat(cs.roomplanSessions);
    }
    return out;
  }
  return [root];
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

/**
 * Per-room floor elevation estimate: median of floor transform world-Y
 * (translation row 13), falling back to median wall-bottom Y when a room has
 * no floors. Ported from AppleRoomPlanJSONDecoder.floorElevation(_:).
 */
function floorElevation(room) {
  const floors = Array.isArray(room.floors) ? room.floors : [];
  const floorYs = floors
    .map((f) => (Array.isArray(f.transform) && f.transform.length === 16 ? f.transform[13] : null))
    .filter((v) => typeof v === 'number' && Number.isFinite(v));
  if (floorYs.length > 0) return median(floorYs);

  const walls = Array.isArray(room.walls) ? room.walls : [];
  const wallBottoms = walls
    .map((w) => {
      if (!Array.isArray(w.transform) || w.transform.length !== 16) return null;
      if (!Array.isArray(w.dimensions) || w.dimensions.length !== 3) return null;
      return w.transform[13] - w.dimensions[1] / 2;
    })
    .filter((v) => typeof v === 'number' && Number.isFinite(v));
  return wallBottoms.length > 0 ? median(wallBottoms) : null;
}

/**
 * Ported from AppleRoomPlanJSONDecoder.storyAssignments(for:). Returns
 * { stories: (number|null)[], method: string|null } — one entry per room.
 * A single-room capture always gets story=null (per-surface `story` field,
 * if present, is used as-is by surface()/object() below).
 */
function storyAssignments(rooms) {
  if (rooms.length <= 1) return { stories: [null], method: null };

  const sourceStories = rooms.map((room) => {
    const records = [];
    for (const kind of SURFACE_KINDS) {
      if (Array.isArray(room[kind])) records.push(...room[kind]);
    }
    if (Array.isArray(room.objects)) records.push(...room.objects);
    const values = records
      .filter((r) => r && typeof r === 'object' && typeof r.story === 'number')
      .map((r) => r.story);
    if (values.length === 0) return null;
    const first = values[0];
    return values.every((v) => v === first) ? first : null;
  });

  if (sourceStories.every((v) => v !== null) && new Set(sourceStories).size > 1) {
    return { stories: sourceStories, method: 'source story values' };
  }

  const elevations = rooms.map(floorElevation);
  if (!elevations.every((v) => v !== null)) {
    return { stories: rooms.map(() => null), method: null };
  }

  const withIndex = elevations.map((e, i) => [i, e]);
  withIndex.sort((a, b) => (a[1] - b[1]) || (a[0] - b[0]));

  const stories = new Array(rooms.length).fill(0);
  let story = 0;
  let clusterValues = [withIndex[0][1]];
  stories[withIndex[0][0]] = story;
  for (let k = 1; k < withIndex.length; k++) {
    const [idx, elevation] = withIndex[k];
    const clusterMean = clusterValues.reduce((a, b) => a + b, 0) / clusterValues.length;
    if (elevation - clusterMean > 0.8) {
      story += 1;
      clusterValues = [elevation];
    } else {
      clusterValues.push(elevation);
    }
    stories[idx] = story;
  }
  return { stories, method: 'multiroom floor-elevation clustering (0.8 m tolerance)' };
}

function decodeSurface(record, kind, path, storyOverride) {
  validate.element(record,path);
  const identifier = str(record.identifier, `${path}.identifier`);
  const category = tagged(record.category,`${path}.category`,kind);
  const confidence = tagged(record.confidence,`${path}.confidence`);
  const story = storyOverride != null ? storyOverride : num(record.story, `${path}.story`);
  const transform = nums(record.transform, 16, `${path}.transform`);
  let curve = null;
  if (record.curve && typeof record.curve === 'object') {
    curve = {
      centerX: num(record.curve.centerX ?? record.curve.center_x, `${path}.curve.centerX`),
      centerZ: num(record.curve.centerZ ?? record.curve.center_z, `${path}.curve.centerZ`),
      radius: num(record.curve.radius, `${path}.curve.radius`),
      startAngleRadians: num(record.curve.startAngleRadians ?? record.curve.start_angle, `${path}.curve.startAngleRadians`),
      endAngleRadians: num(record.curve.endAngleRadians ?? record.curve.end_angle, `${path}.curve.endAngleRadians`),
    };
  }
  let isOpen = null;
  if (kind === 'doors' && record.category && record.category.door) {
    isOpen = !!record.category.door.isOpen;
  }
  return {
    identifier,
    sourceRecordIndex: path,
    parentIdentifier: record.parentIdentifier || null,
    kind: kind.replace(/s$/, ''), // 'walls' -> 'wall'
    category,
    confidence,
    sourceStory: record.story ?? null,
    sourceStoryProvenance: record.story == null ? 'absent' : 'source record',
    story,
    dimensions: dims(record.dimensions, `${path}.dimensions`),
    transform, // kept local/untransformed — see module docstring
    polygonCorners: points(record.polygonCorners || [], `${path}.polygonCorners`), // kept local — projected at align/write time
    curve,
    isOpen,
  };
}

function decodeObject(record, path, storyOverride) {
  validate.element(record,path);
  const identifier = str(record.identifier, `${path}.identifier`);
  const category = tagged(record.category,`${path}.category`,'object');
  const confidence = tagged(record.confidence,`${path}.confidence`);
  const story = storyOverride != null ? storyOverride : num(record.story, `${path}.story`);
  return {
    identifier,
    sourceRecordIndex: path,
    parentIdentifier: record.parentIdentifier || null,
    category,
    confidence,
    sourceStory: record.story ?? null,
    sourceStoryProvenance: record.story == null ? 'absent' : 'source record',
    story,
    dimensions: dims(record.dimensions, `${path}.dimensions`),
    transform: nums(record.transform, 16, `${path}.transform`),
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
  if(dialect.kind !== 'raw') throw new Error('Expected raw Apple RoomPlan geometry');
  validate.geo(root);

  const rooms = roomRecords(root);
  validate.sourceGeometry(rooms);
  rooms.forEach((room,i)=>{
    for(const key of [...SURFACE_KINDS,'objects']) if(room[key]!=null&&!Array.isArray(room[key])) validate.fail(`rooms[${i}].${key}`,'expected array');
    if(room.referenceOriginTransform!=null) validate.matrix(room.referenceOriginTransform,`rooms[${i}].referenceOriginTransform`);
  });
  const assignment = storyAssignments(rooms);

  let surfaces = [];
  let objects = [];
  rooms.forEach((room, i) => {
    const prefix = rooms.length === 1 ? '' : `rooms[${i}].`;
    const storyOverride = assignment.stories[i];
    for (const kind of SURFACE_KINDS) {
      const arr = Array.isArray(room[kind]) ? room[kind] : [];
      arr.forEach((r, j) => {
        const surface = decodeSurface(r, kind, `${prefix}${kind}[${j}]`, storyOverride);
        surface.sourceRoomIndex = i;
        surface.sourceRoomIdentifier = room.identifier ?? room.id ?? null;
        surfaces.push(surface);
      });
    }
    const objs = Array.isArray(room.objects) ? room.objects : [];
    objs.forEach((r, j) => {
      const object = decodeObject(r, `${prefix}objects[${j}]`, storyOverride);
      object.sourceRoomIndex = i;
      object.sourceRoomIdentifier = room.identifier ?? room.id ?? null;
      objects.push(object);
    });
  });

  return {
    kind: 'raw',
    dialect: dialect.dialect,
    dialectEvidence: dialect.evidence,
    sourceByteCount: buf.length,
    sourceSHA256: sha256(buf),
    originalFilename: originalFilename || null,
    storyAssignmentMethod: assignment.method, // null means story came straight from each record's own `story` field
    surfaces,
    objects,
    rooms: null, // raw format has no pre-computed room polygons/labels
    meta: { roomCount: rooms.length,
      latitude: root.latLonAlt?.latitude ?? null, longitude: root.latLonAlt?.longitude ?? null, altitude: root.latLonAlt?.altitude ?? null,
      orientationDegrees: root.orientation?.orientation_degrees ?? null, orientationUncertaintyDegrees: root.orientation?.uncertainty_degrees ?? null, orientationConfidence: root.orientation?.confidence ?? null },
  };
}

module.exports = { decode };
