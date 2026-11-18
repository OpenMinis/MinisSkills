'use strict';
/**
 * plan-statistics.js — gross/net per level, living/gross, roomsWithoutArea and
 * the `statistics` block (SPEC §5 G-9).
 *
 * Ported from ArchiPlan `editor/src/lib/utils/planStatistics.ts`
 * (`planStatistics`, 106 lines) — no TypeScript, no `$lib` alias, no deps.
 *
 * What is taken from the source verbatim:
 *   - the totals formula: wallLength = SUM centreline length,
 *     wallAreaGross = SUM length x wall.height (defaults.ceilingHeight),
 *     footprint = SUM length x wall.thickness (defaults.interiorWallThickness),
 *     openingArea = SUM width x height (door 2.0 / window 1.2 fallback),
 *     livingArea = SUM room areas, grossArea = livingArea + footprint / 2,
 *     wallAreaNet = max(0, wallAreaGross - openingArea);
 *   - counts (roomCount, wallCount, doorCount, windowCount, furnitureCount,
 *     roomsWithoutArea), the level index set {0} U levels, the default level
 *     names, the rooms[] block and the costs{} block (priced items only,
 *     negative prices clamped to 0);
 *   - rounding to 6 decimals, `null` (not 0) wherever a value cannot be known.
 *
 * What is deliberately ours:
 *   - the INPUT is capture-v1 (or ArchiPlan's plan.json, see toPlan()), not the
 *     web `Project` object, so this module has no compiler-specific geometry;
 *   - room floor areas come from `interior-area.js` `interiorRoomArea`
 *     (interior/clear area, wall footprints removed — G-6/G-7), not from the
 *     web's raster fill. Rooms that are no longer enclosed have NO area and are
 *     counted in `roomsWithoutArea`; a floor opening contributes exactly zero
 *     (same rule as the source);
 *   - every number carries provenance (`value`, `status`, `reason`) in the
 *     sibling `areas` / `measure` blocks. A missing number is never 0.
 */

const { interiorRoomArea } = require('./interior-area');

const DEFAULT_CEILING = 2.4;
const DEFAULT_INTERIOR_THICKNESS = 0.12;
const DEFAULT_DOOR_HEIGHT = 2;
const DEFAULT_WINDOW_HEIGHT = 1.2;

const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const pos = (v) => finite(v) && v > 0;
/** ArchiPlan `round`: 6 decimals, non-finite -> 0 (only used on inputs already known). */
const round = (value) => (finite(value) ? Math.round(value * 1e6) / 1e6 : 0);
const key = (id) => String(id).toLowerCase();

function defaultLevelName(index) {
  if (index === 0) return 'Ground Floor';
  if (index < 0) return index === -1 ? 'Basement' : `Basement ${-index}`;
  return `Floor ${index}`;
}

// ---------------------------------------------------------------------------
// input normalisation
// ---------------------------------------------------------------------------

const planXZ = (p) => {
  if (Array.isArray(p) && p.length >= 2 && finite(p[0]) && finite(p[1])) return { x: p[0], y: p[1] };
  if (p && finite(p.x) && finite(p.y)) return { x: p.x, y: p.y };
  if (p && finite(p.x) && finite(p.z)) return { x: p.x, y: p.z };
  return null;
};

/** ring from [{x,z}] | [{x,y}] | [[x,z]]; null when fewer than 3 usable points. */
function ringOf(list) {
  if (!Array.isArray(list)) return null;
  const ring = list.map(planXZ);
  if (ring.length < 3 || ring.some((p) => !p)) return null;
  return ring;
}

/** Column-major planar transform for a wall running from (x0,z0) to (x1,z1). */
function wallTransform(start, end) {
  const dx = end.x - start.x, dz = end.y - start.y;
  const length = Math.hypot(dx, dz);
  if (!finite(length) || length === 0) return null;
  const ux = dx / length, uz = dz / length;
  return [ux, 0, uz, 0, 0, 1, 0, 0, -uz, 0, ux, 0, start.x, 0, start.y, 1];
}

function isCapture(input) {
  return !!input && (input.schemaVersion === 'roomplan.capture/1' ||
    (Array.isArray(input.surfaces) && !Array.isArray(input.walls)));
}

/**
 * Normalise either contract to the flat, plan-shaped record set this module and
 * handoff.js consume:
 *   walls[]      { id, start{x,y}, end{x,y}, height, thickness, level }
 *   openings[]   { id, wallID, kind, width, height, sillHeight, position,
 *                  level (inherited from the parent wall) }
 *   furniture[]  { id, category, level, width, depth, height, price, note, photos }
 *   rooms[]      { id, name, level, polygon, holes, ceilingHeight, floorOpening,
 *                  photos, note, price, source }
 *   levels[]     { index, name }
 *   defaults{}   { ceilingHeight, interiorWallThickness }
 *
 * capture-v1 walls carry a 4x4 transform + dimensions; the plan centreline is
 * transform origin -> origin + dimensions.x along the local X axis, wall height
 * is dimensions.y, thickness is wallThickness (else dimensions.z). Openings are
 * attached through parentIdentifier, exactly as capture-v1 records them.
 */
function toPlan(input, options) {
  const opts = options || {};
  if (!input || typeof input !== 'object') return { error: 'no input object' };
  const capture = isCapture(input);
  const rawWalls = capture ? (input.surfaces || []).filter((s) => s && s.kind === 'wall') : (input.walls || []);
  const rawOpenings = capture ? (input.surfaces || []).filter((s) => s && (s.kind === 'door' || s.kind === 'window' || s.kind === 'opening')) : (input.openings || []);
  const rawObjects = capture ? (input.objects || []) : (input.furniture || []);
  const rawRooms = input.rooms || [];
  const rawLevels = input.levels || [];
  const defaults = {
    ceilingHeight: finite(input.defaults && input.defaults.ceilingHeight) ? input.defaults.ceilingHeight : DEFAULT_CEILING,
    interiorWallThickness: finite(input.defaults && input.defaults.interiorWallThickness)
      ? input.defaults.interiorWallThickness : DEFAULT_INTERIOR_THICKNESS,
  };

  const walls = [];
  for (const w of rawWalls) {
    let start = null, end = null, height = null, thickness = null, level = 0;
    if (capture) {
      const t = w.transform;
      if (!Array.isArray(t) || t.length !== 16 || !t.every(finite)) continue;
      const d = w.dimensions || {};
      if (!pos(d.x)) continue;
      start = { x: t[12], y: t[14] };
      end = { x: t[12] + t[0] * d.x, y: t[14] + t[2] * d.x };
      height = finite(d.y) ? d.y : null;
      thickness = pos(w.wallThickness) ? w.wallThickness : pos(d.z) ? d.z : null;
      level = Number.isSafeInteger(w.story) ? w.story : 0;
    } else {
      start = planXZ(w.start);
      end = planXZ(w.end);
      if (!start || !end) continue;
      height = finite(w.height) ? w.height : null;
      thickness = pos(w.thickness) ? w.thickness : null;
      level = Number.isSafeInteger(w.level) ? w.level : 0;
    }
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    if (!finite(length) || length <= 0) continue;
    walls.push({
      id: String(w.identifier != null ? w.identifier : w.id != null ? w.id : `wall:${walls.length}`),
      start, end, length,
      height: height != null ? height : defaults.ceilingHeight,
      heightSource: height != null ? (capture ? 'source.dimensions.y' : 'source.height') : 'defaults.ceilingHeight',
      thickness: thickness != null ? thickness : defaults.interiorWallThickness,
      thicknessSource: thickness != null ? (capture ? 'source.wallThickness' : 'source.thickness') : 'defaults.interiorWallThickness',
      level,
      curve: capture ? (w.curve || null) : (w.curvePoint ? { curvePoint: w.curvePoint } : null),
    });
  }

  const wallById = new Map(walls.map((w) => [key(w.id), w]));
  const openings = [];
  for (const o of rawOpenings) {
    const wallID = capture ? o.parentIdentifier : o.wallID != null ? o.wallID : o.parentIdentifier;
    const d = o.dimensions || {};
    const width = capture ? (finite(d.x) ? d.x : null) : (finite(o.width) ? o.width : null);
    const height = capture ? (finite(d.y) ? d.y : null) : (finite(o.height) ? o.height : null);
    const kind = o.kind || 'opening';
    openings.push({
      id: String(o.identifier != null ? o.identifier : o.id != null ? o.id : `opening:${openings.length}`),
      wallID: wallID != null ? String(wallID) : null,
      kind,
      width,
      // ArchiPlan: opening.height ?? (door ? 2.0 : 1.2)
      height: height != null ? height : kind === 'door' ? DEFAULT_DOOR_HEIGHT : DEFAULT_WINDOW_HEIGHT,
      heightSource: height != null ? 'source' : kind === 'door' ? 'DEFAULT_DOOR_HEIGHT' : 'DEFAULT_WINDOW_HEIGHT',
      sillHeight: finite(o.sillHeight) ? o.sillHeight : null,
      position: finite(capture ? o.positionAlongWall : o.position) ? (capture ? o.positionAlongWall : o.position) : null,
      level: (() => {
        const parent = wallID != null ? wallById.get(key(wallID)) : null;
        if (parent) return parent.level;
        return Number.isSafeInteger(capture ? o.story : o.level) ? (capture ? o.story : o.level) : 0;
      })(),
      parentFound: wallID != null && wallById.has(key(wallID)),
    });
  }

  const furniture = [];
  for (const f of rawObjects) {
    const d = f.dimensions || {};
    const level = Number.isSafeInteger(capture ? f.story : f.level) ? (capture ? f.story : f.level) : 0;
    furniture.push({
      id: String(f.identifier != null ? f.identifier : f.id != null ? f.id : `object:${furniture.length}`),
      category: f.category || null,
      level,
      width: capture ? (finite(d.x) ? d.x : null) : (finite(f.width) ? f.width : null),
      depth: capture ? (finite(d.z) ? d.z : finite(d.y) ? d.y : null) : (finite(f.depth) ? f.depth : null),
      height: capture ? (finite(d.y) ? d.y : null) : (finite(f.height) ? f.height : null),
      price: finite(f.price) ? f.price : null,
      note: f.note != null ? f.note : null,
      photos: Array.isArray(f.photos) ? f.photos : [],
    });
  }

  const rooms = [];
  for (const r of rawRooms) {
    const polygon = ringOf(r.polygon) || ringOf(r.polygonXZ) || ringOf(r.vertices);
    const rawHoles = Array.isArray(r.holes) ? r.holes : [];
    const holeRings = rawHoles.map(ringOf);
    // An unusable hole is NOT dropped (that would silently enlarge the room);
    // the room is refused instead.
    const holes = holeRings.filter(Boolean);
    const holesInvalid = holeRings.some((h) => !h);
    rooms.push({
      id: String(r.identifier != null ? r.identifier : r.id != null ? r.id : `room:${rooms.length}`),
      name: r.name != null ? r.name : r.label != null ? r.label : null,
      level: Number.isSafeInteger(capture ? r.story : r.level) ? (capture ? r.story : r.level) : 0,
      polygon,
      holes,
      holesInvalid,
      ceilingHeight: finite(r.ceilingHeight) ? r.ceilingHeight : null,
      floorOpening: r.floorOpening === true,
      photos: Array.isArray(r.photos) ? r.photos : [],
      note: r.note != null ? r.note : null,
      price: finite(r.price) ? r.price : null,
      boundaryWallIDs: Array.isArray(r.boundaryWallIDs) ? r.boundaryWallIDs : null,
      type: r.type != null ? r.type : r.category != null ? r.category : null,
      declaredArea: finite(r.area) ? r.area : null,
    });
  }

  const levels = [];
  for (const l of rawLevels) {
    const index = Number.isSafeInteger(l.index) ? l.index : Number.isSafeInteger(l.story) ? l.story : null;
    if (index == null) continue;
    levels.push({ index, name: l.name != null ? l.name : l.label != null ? l.label : defaultLevelName(index) });
  }

  return {
    contract: capture ? 'roomplan.capture/1' : 'archiplan.plan',
    walls, openings, furniture, rooms, levels, defaults,
    title: opts.title != null ? opts.title : input.title != null ? input.title : null,
    producer: opts.producer != null ? opts.producer : input.producer != null ? input.producer : null,
    planNotes: input.planNotes != null ? input.planNotes : null,
    notes: Array.isArray(input.notes) ? input.notes : [],
    underlay: input.underlay || null,
  };
}

// ---------------------------------------------------------------------------
// room areas
// ---------------------------------------------------------------------------

/**
 * Interior floor area per room (m^2) with provenance.
 * Returns Map<lowercased room id, {value, status, reason}>.
 * A floor opening is 0 by contract (same as the source), not "unknown".
 */
function roomAreas(plan, options) {
  const opts = options || {};
  const out = new Map();
  for (const room of plan.rooms) {
    // ArchiPlan measures a room against its OWN floor's walls (project.floors[i].walls),
    // never against the whole building: a wall two storeys up must not cut this room.
    const wallFootprints = plan.walls.filter((w) => w.level === room.level)
      .map((w) => ({ start: w.start, end: w.end, thickness: w.thickness, curvePoint: w.curve && w.curve.curvePoint ? w.curve.curvePoint : undefined }));
    if (room.floorOpening) {
      out.set(key(room.id), { value: 0, status: 'computed', reason: 'floor opening: contributes zero by contract (ArchiPlan planStatistics.ts)' });
      continue;
    }
    if (room.holesInvalid) {
      out.set(key(room.id), { value: null, status: 'unavailable', reason: 'room hole polygon is invalid; the room is refused rather than measured without its hole' });
      continue;
    }
    if (!room.polygon) {
      out.set(key(room.id), {
        value: null, status: 'unavailable',
        reason: 'room has no closed polygon in the source; a label outside every closed boundary has no measured area (counted in roomsWithoutArea)',
      });
      continue;
    }
    let value;
    try {
      value = interiorRoomArea(room.polygon, room.holes, wallFootprints, {
        units: 'm', wallConvention: opts.wallConvention || 'centerline',
      });
    } catch (e) {
      value = null;
      out.set(key(room.id), { value: null, status: 'unavailable', reason: `interiorRoomArea threw: ${e.message}` });
      continue;
    }
    if (!finite(value)) {
      out.set(key(room.id), {
        value: null, status: 'unavailable',
        reason: 'interiorRoomArea refused the room (invalid ring, non-positive wall thickness, ambiguous outward normal or over budget)',
      });
      continue;
    }
    out.set(key(room.id), {
      value,
      status: 'computed',
      reason: `interiorRoomArea scanline integration, ${opts.wallConvention || 'centerline'} wall convention; wall footprints (union) removed`,
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// statistics block (ArchiPlan planStatistics.ts)
// ---------------------------------------------------------------------------

/**
 * @param {object} input  capture-v1, or ArchiPlan plan.json shape
 * @param {object} [options] { title, producer, wallConvention }
 * @returns {{ok:boolean, statistics:object|null, reason:string|null,
 *            areas:object, gaps:string[], conventions:object, plan:object|null}}
 *   `statistics` is the ArchiPlan block (version/units/totals/levels/rooms/costs)
 *   or null with `reason` when the input cannot produce one at all.
 */
function planStatistics(input, options) {
  const plan = toPlan(input, options);
  if (plan.error) {
    return { ok: false, statistics: null, reason: plan.error, areas: {}, gaps: [], conventions: null, plan: null };
  }
  if (!plan.walls.length && !plan.rooms.length && !plan.openings.length) {
    return {
      ok: false, statistics: null, reason: 'no walls, rooms or openings in the input; a statistics block of zeros would be a guess',
      areas: {}, gaps: [], conventions: null, plan,
    };
  }
  const areas = roomAreas(plan, options);
  const gaps = [];
  for (const room of plan.rooms) {
    const a = areas.get(key(room.id));
    if (a && a.value == null) gaps.push(`Room '${room.name || room.id}' has no measured floor area: ${a.reason}`);
  }

  const levelOf = (item) => (Number.isSafeInteger(item.level) ? item.level : 0);

  function totals(ws, os, fs, rs) {
    let wallLength = 0, wallAreaGross = 0, footprint = 0, openingArea = 0, living = 0, without = 0;
    for (const wall of ws) {
      wallLength += wall.length;
      wallAreaGross += wall.length * wall.height;
      footprint += wall.length * wall.thickness;
    }
    for (const opening of os) openingArea += (opening.width || 0) * opening.height;
    for (const room of rs) {
      if (room.floorOpening === true) continue;
      const area = areas.get(key(room.id));
      if (!area || area.value == null) without += 1;
      else living += area.value;
    }
    return {
      livingArea: round(living),
      grossArea: round(living + footprint / 2),
      wallAreaGross: round(wallAreaGross),
      wallAreaNet: round(Math.max(wallAreaGross - openingArea, 0)),
      openingArea: round(openingArea),
      wallLength: round(wallLength),
      roomCount: rs.length,
      wallCount: ws.length,
      doorCount: os.filter((o) => o.kind === 'door').length,
      windowCount: os.filter((o) => o.kind === 'window').length,
      furnitureCount: fs.length,
      roomsWithoutArea: without,
    };
  }

  const indices = new Set([0, ...plan.walls.map(levelOf), ...plan.rooms.map(levelOf), ...plan.furniture.map(levelOf),
    ...plan.levels.map((l) => l.index)]);
  const named = new Map(plan.levels.map((l) => [l.index, l.name]));
  const levels = [...indices].sort((a, b) => a - b).map((index) => ({
    index,
    name: named.get(index) != null ? named.get(index) : defaultLevelName(index),
    totals: totals(
      plan.walls.filter((w) => levelOf(w) === index),
      plan.openings.filter((o) => o.level === index),
      plan.furniture.filter((f) => levelOf(f) === index),
      plan.rooms.filter((r) => levelOf(r) === index),
    ),
  }));

  const priced = (items) => items.filter((item) => finite(item.price));
  const priceSum = (items) => items.reduce((total, item) => total + Math.max(item.price, 0), 0);
  const pricedOpenings = priced(plan.openings);
  const pricedFurniture = priced(plan.furniture);

  const statistics = {
    version: 1,
    units: 'metres',
    totals: totals(plan.walls, plan.openings, plan.furniture, plan.rooms),
    levels,
    rooms: plan.rooms.map((room) => {
      const area = areas.get(key(room.id));
      const block = {
        id: room.id,
        name: room.name,
        level: levelOf(room),
        ceilingHeight: round(room.ceilingHeight != null ? room.ceilingHeight : plan.defaults.ceilingHeight),
        floorOpening: room.floorOpening === true,
      };
      // ArchiPlan omits floorArea when it is unknown — it never writes 0.
      if (area && area.value != null) block.floorArea = round(area.value);
      return block;
    }),
    costs: {
      openingCost: round(priceSum(pricedOpenings)),
      furnitureCost: round(priceSum(pricedFurniture)),
      totalCost: round(priceSum(pricedOpenings) + priceSum(pricedFurniture)),
      pricedOpeningCount: pricedOpenings.length,
      pricedFurnitureCount: pricedFurniture.length,
    },
  };

  const areaDump = {};
  for (const room of plan.rooms) {
    const a = areas.get(key(room.id));
    areaDump[room.id] = { value: a ? (a.value == null ? null : round(a.value)) : null, status: a ? a.status : 'unavailable', reason: a ? a.reason : 'room not evaluated' };
  }

  return {
    ok: true,
    statistics,
    reason: null,
    areas: areaDump,
    gaps,
    conventions: {
      units: 'metres',
      livingArea: 'interior/clear area from interior-area.js interiorRoomArea; wall footprint union removed; never the declared source area',
      grossArea: 'livingArea + footprint/2, footprint = SUM wallLength x wall thickness',
      wallArea: 'wallAreaGross = SUM length x height (wall height, else defaults.ceilingHeight); wallAreaNet = max(0, gross - openingArea)',
      openingArea: 'SUM width x height; door 2.0 m / window 1.2 m used only when the source has no height',
      roomsWithoutArea: 'rooms with no measured area (no closed polygon, refused or floorOpening excluded from living) are counted, never estimated',
      rounding: '6 decimals, as planStatistics.ts round()',
      contract: plan.contract,
    },
    plan,
  };
}

module.exports = {
  planStatistics,
  toPlan,
  roomAreas,
  wallTransform,
  defaultLevelName,
  DEFAULT_CEILING,
  DEFAULT_INTERIOR_THICKNESS,
  DEFAULT_DOOR_HEIGHT,
  DEFAULT_WINDOW_HEIGHT,
  round,
};
