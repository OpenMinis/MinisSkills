'use strict';
/**
 * handoff.js — contractor handoff scope: per-room boundary figures, per-level
 * takeoff, the flat quantities[] table and the gaps[] that say what is missing
 * (SPEC §5 G-10).
 *
 * Ported from ArchiPlan `editor/src/lib/skills/handoff.ts` (`handoffScope`,
 * 177 lines) on top of plan-statistics.js (`toPlan`, `roomAreas`), which is the
 * capture-v1 normaliser shared with planStatistics. No TypeScript, no `$lib`.
 *
 * Kept from the source, value for value:
 *   - `measure()`: {value: round3, unit:'m'|'m²', imperial: round1, imperialUnit:'ft'|'ft²'}
 *     (FT = 3.280839895, SQFT = 10.76391042);
 *   - per-room fields floorArea, ceilingArea, ceilingHeight, boundaryWallRun,
 *     boundaryWallAreaGross, boundaryWallAreaNet, boundaryDoorCount,
 *     boundaryWindowCount, photoCount, photos, note;
 *   - per-level fields livingArea, grossArea, wallRun, wallAreaGross,
 *     wallAreaNet, openingArea, doorCount, windowCount, wallCount,
 *     furnitureCount, rooms[], openings[], furniture{category:{count,items}};
 *   - quantities[] with EXACTLY these keys and this order:
 *       floorArea, ceilingArea, wallAreaNetRoom, wallRunRoom,          (per room)
 *       livingAreaLevel, wallAreaNetLevel, wallAreaGrossLevel,
 *       wallRunLevel, doors, windows                                    (per level)
 *     A null measure is skipped (never written as 0), as in the source;
 *   - summary, notes, costs, evidence, assumptions, gaps, codesApplied.
 *
 * Deliberately ours:
 *   - floorArea is the interior/clear area from plan-statistics.js roomAreas
 *     (interior-area.js), never a declared source area;
 *   - ceilingArea comes from the kernels ceiling layer
 *     (ceiling-reconstruct.reconstructCeilingForRoom) and carries its `method`
 *     (flat | knee | section | extrusion | unavailable) — the source assumed a
 *     flat ceiling equal to the floor;
 *   - boundary walls: the source trusted `room.boundaryWallIDs`; when a capture
 *     has no such links we fall back to geometric membership (wall centreline
 *     midpoint inside the room ring, 0.02 m tolerance) and record which rule
 *     was used in `boundaryMethod`;
 *   - every gap the source reports is reported here, plus the ones the source
 *     could not see (opening without a parent wall, room without a polygon,
 *     area refused by interiorRoomArea).
 */

const { toPlan, roomAreas, defaultLevelName, planStatistics } = require('./plan-statistics');
const { reconstructCeilingForRoom } = require('./ceiling-reconstruct');

const DEFAULT_WALL_HEIGHT = 2.4;
const DEFAULT_CEILING_HEIGHT = 2.4;
const DEFAULT_DOOR_HEIGHT = 2.0;
const DEFAULT_WINDOW_HEIGHT = 1.2;
const DEFAULT_SILL = 0.9;
const FT = 3.280839895;
const SQFT = 10.76391042;
const BOUNDARY_TOLERANCE_M = 0.02;

const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const pyRound = (v, digits) => {
  if (!finite(v)) return null;
  const f = Math.pow(10, digits);
  return Math.round((v + (v >= 0 ? 1 : -1) * Number.EPSILON * Math.abs(v)) * f) / f;
};
function measure(metres, kind) {
  if (metres === null || metres === undefined || !finite(metres)) return null;
  const [factor, unit, imperialUnit] = kind === 'length' ? [FT, 'm', 'ft'] : [SQFT, 'm²', 'ft²'];
  return { value: pyRound(metres, 3), unit, imperial: pyRound(metres * factor, 1), imperialUnit };
}
const lower = (value) => (value === undefined || value === null ? 'none' : String(value)).toLowerCase();

/** Odd-even containment, tolerance in metres (same rule as the kernel). */
function inRing(point, ring, tol) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[j], b = ring[i];
    const cross = (b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x);
    const length = Math.hypot(b.x - a.x, b.y - a.y);
    if (length > 0 && Math.abs(cross) / length <= tol) {
      const dot = (point.x - a.x) * (b.x - a.x) + (point.y - a.y) * (b.y - a.y);
      if (dot >= -tol && dot <= length * length + tol) return true;
    }
    if ((a.y > point.y) !== (b.y > point.y) && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

/** Wall record in the shape ceiling-reconstruct expects (no polygonCorners ->
 * flat top edge -> method 'flat'; a sloped wall would need the polygon). */
function ceilingWall(wall) {
  return {
    identifier: wall.id,
    kind: 'wall',
    story: wall.level,
    dimensions: { x: wall.length, y: wall.height, z: wall.thickness },
    transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, wall.start.x, 0, wall.start.y, 1],
    wallThickness: wall.thickness,
  };
}

/**
 * @param {object} input      capture-v1 or ArchiPlan plan.json
 * @param {object} [options]  { title, producer, codes:{key:code}, assets:[names],
 *                              wallConvention }
 * @returns {{ok:boolean, scope:object|null, reason:string|null}}
 */
function handoff(input, options) {
  const opts = options || {};
  const plan = toPlan(input, opts);
  if (plan.error) return { ok: false, scope: null, reason: plan.error };

  const codes = opts.codes && typeof opts.codes === 'object' ? opts.codes : {};
  const assets = Array.isArray(opts.assets) ? opts.assets.slice() : null;
  const areas = roomAreas(plan, opts);
  const wallById = new Map(plan.walls.map((w) => [lower(w.id), w]));
  const gaps = [];
  const quantities = [];

  const addQuantity = (key, description, metres, kind, level, room, count) => {
    const item = { key, description, level: level == null ? null : level, room: room == null ? null : room };
    if (count != null) {
      Object.assign(item, { quantity: count, unit: 'count' });
    } else {
      const m = measure(metres, kind);
      if (!m) return; // ArchiPlan: unknown measure is skipped, never written as zero
      Object.assign(item, { quantity: m.value, unit: m.unit, imperialQuantity: m.imperial, imperialUnit: m.imperialUnit });
    }
    if (key in codes) item.code = codes[key];
    quantities.push(item);
  };

  const assumptions = [
    'Wall runs are centreline lengths; wall areas are run × height with doors and windows deducted for the net figure.',
    'Ceiling area comes from the kernel ceiling layer (reconstructCeilingForRoom) and carries its method; floor area is the interior/clear area, not the declared plan area.',
    "A wall shared by two rooms appears in both rooms' boundary figures; use level totals for material takeoff.",
  ];

  // An opening whose parent wall is absent belongs to no level and no room: say
  // so once, for the whole plan, instead of dropping it silently.
  for (const o of plan.openings) {
    if (!o.parentFound) gaps.push(`Opening '${o.id}' (${o.kind}) references wall '${o.wallID}' which is not in the plan; it is not counted in any level or room total.`);
  }

  const levelIndices = [...new Set([
    0,
    ...plan.levels.map((l) => l.index),
    ...plan.walls.map((w) => w.level),
    ...plan.rooms.map((r) => r.level),
    ...plan.furniture.map((f) => f.level),
  ])].sort((a, b) => a - b);
  const named = new Map(plan.levels.map((l) => [l.index, l.name]));

  const levelEntries = [];
  for (const index of levelIndices) {
    const name = named.has(index) ? named.get(index) : defaultLevelName(index);
    const levelWalls = plan.walls.filter((w) => w.level === index);
    const wallIds = new Set(levelWalls.map((w) => lower(w.id)));
    const levelOpenings = plan.openings.filter((o) => o.wallID != null && wallIds.has(lower(o.wallID)));
    const levelRooms = plan.rooms.filter((r) => r.level === index);
    const levelFurniture = plan.furniture.filter((f) => f.level === index);

    const run = levelWalls.reduce((s, w) => s + w.length, 0);
    const gross = levelWalls.reduce((s, w) => s + w.length * w.height, 0);
    const openingArea = levelOpenings.reduce((s, o) => s + (o.width || 0) * o.height, 0);
    const net = Math.max(gross - openingArea, 0);

    // living/gross per level: unknown when no room on the level has an area
    let living = null;
    for (const room of levelRooms) {
      const area = areas.get(lower(room.id));
      if (room.floorOpening || !area || area.value == null) continue;
      living = (living || 0) + area.value;
    }
    const footprint = levelWalls.reduce((s, w) => s + w.length * w.thickness, 0);
    const grossArea = living == null ? null : living + footprint / 2;

    const roomEntries = [];
    for (const room of levelRooms) {
      const rname = room.name != null ? room.name : 'Unnamed room';
      const a = areas.get(lower(room.id));
      const area = a && a.value != null ? a.value : null;

      // Boundary walls: source links first, geometric membership as fallback.
      let boundaryWalls = [];
      let boundaryMethod = 'none';
      if (Array.isArray(room.boundaryWallIDs) && room.boundaryWallIDs.length) {
        boundaryWalls = room.boundaryWallIDs.map((id) => wallById.get(lower(id))).filter(Boolean);
        boundaryMethod = 'supplied boundaryWallIDs';
        for (const id of room.boundaryWallIDs) {
          if (!wallById.has(lower(id))) gaps.push(`Room '${rname}' (${name}) lists boundary wall '${id}' which is not in the plan.`);
        }
      } else if (room.polygon) {
        boundaryWalls = levelWalls.filter((w) => inRing({ x: (w.start.x + w.end.x) / 2, y: (w.start.y + w.end.y) / 2 }, room.polygon, BOUNDARY_TOLERANCE_M));
        boundaryMethod = `geometric membership: wall centreline midpoint inside the room ring, tolerance ${BOUNDARY_TOLERANCE_M} m`;
      }

      let boundaryRun = null, boundaryGross = null, boundaryNet = null;
      let boundaryOpenings = [];
      if (boundaryWalls.length) {
        boundaryRun = boundaryWalls.reduce((s, w) => s + w.length, 0);
        boundaryGross = boundaryWalls.reduce((s, w) => s + w.length * w.height, 0);
        const idSet = new Set(boundaryWalls.map((w) => lower(w.id)));
        boundaryOpenings = plan.openings.filter((o) => o.wallID != null && idSet.has(lower(o.wallID)));
        const deduct = boundaryOpenings.reduce((s, o) => s + (o.width || 0) * o.height, 0);
        boundaryNet = Math.max(boundaryGross - deduct, 0);
      }

      const height = room.ceilingHeight != null ? room.ceilingHeight : plan.defaults.ceilingHeight;

      // Ceiling of this room from OUR ceiling layer, area = interior floor area.
      let ceilingArea = null, ceilingMethod = null;
      if (room.floorOpening) {
        ceilingMethod = 'unavailable';
      } else if (!boundaryWalls.length || area == null) {
        ceilingMethod = 'unavailable';
      } else {
        const rec = reconstructCeilingForRoom(boundaryWalls.map(ceilingWall), area);
        ceilingArea = finite(rec.ceilingArea) ? rec.ceilingArea : null;
        ceilingMethod = rec.method || 'unavailable';
      }

      const photos = room.photos.slice();
      roomEntries.push({
        name: rname,
        type: room.type != null ? room.type : null,
        floorOpening: room.floorOpening === true,
        floorArea: measure(area, 'area'),
        ceilingArea: room.floorOpening ? null : measure(ceilingArea, 'area'),
        ceilingMethod,
        ceilingHeight: measure(height, 'length'),
        boundaryWallRun: measure(boundaryRun, 'length'),
        boundaryWallAreaGross: measure(boundaryGross, 'area'),
        boundaryWallAreaNet: measure(boundaryNet, 'area'),
        boundaryDoorCount: boundaryOpenings.filter((o) => o.kind === 'door').length,
        boundaryWindowCount: boundaryOpenings.filter((o) => o.kind === 'window').length,
        boundaryWallCount: boundaryWalls.length,
        boundaryMethod,
        boundaryWallIDs: boundaryWalls.map((w) => w.id),
        photoCount: photos.length,
        photos,
        note: room.note != null ? room.note : null,
      });

      if (area == null && !room.floorOpening) {
        gaps.push(`Room '${rname}' (${name}) has no measured floor area; its label is outside any closed boundary${a && a.reason ? ` (${a.reason})` : ''}.`);
      }
      if (!photos.length) gaps.push(`Room '${rname}' (${name}) has no photos.`);
      if (!room.floorOpening) {
        addQuantity('floorArea', `Floor area, ${rname}`, area, 'area', name, rname);
        addQuantity('ceilingArea', `Ceiling area, ${rname}`, ceilingArea, 'area', name, rname);
        addQuantity('wallAreaNetRoom', `Wall area net of openings, ${rname} boundary`, boundaryNet, 'area', name, rname);
        addQuantity('wallRunRoom', `Wall run, ${rname} boundary`, boundaryRun, 'length', name, rname);
      }
    }

    const openingsSchedule = levelOpenings.map((o) => {
      const wall = o.wallID != null ? wallById.get(lower(o.wallID)) : null;
      return {
        kind: o.kind || null,
        style: null,
        width: measure(o.width, 'length'),
        height: measure(o.height, 'length'),
        sillHeight: o.kind === 'window' ? measure(o.sillHeight != null ? o.sillHeight : DEFAULT_SILL, 'length') : null,
        wallHeight: wall ? measure(wall.height, 'length') : null,
        positionAlongWall: o.position != null ? o.position : null,
        price: finite(o.price) ? o.price : null,
      };
    });
    const inventory = new Map();
    for (const item of levelFurniture) {
      const category = item.category != null ? item.category : 'unknown';
      if (!inventory.has(category)) inventory.set(category, { count: 0, items: [] });
      const bucket = inventory.get(category);
      bucket.count += 1;
      bucket.items.push({
        width: measure(item.width, 'length'),
        depth: measure(item.depth, 'length'),
        height: item.height != null ? measure(item.height, 'length') : null,
        note: item.note != null ? item.note : null,
        price: finite(item.price) ? item.price : null,
        photoCount: item.photos.length,
      });
    }
    const furnitureBlock = {};
    for (const category of [...inventory.keys()].sort()) furnitureBlock[category] = inventory.get(category);

    levelEntries.push({
      index,
      name,
      livingArea: measure(living, 'area'),
      grossArea: measure(grossArea, 'area'),
      wallRun: measure(run, 'length'),
      wallAreaGross: measure(gross, 'area'),
      wallAreaNet: measure(net, 'area'),
      openingArea: measure(openingArea, 'area'),
      doorCount: levelOpenings.filter((o) => o.kind === 'door').length,
      windowCount: levelOpenings.filter((o) => o.kind === 'window').length,
      wallCount: levelWalls.length,
      furnitureCount: levelFurniture.length,
      rooms: roomEntries,
      openings: openingsSchedule,
      furniture: furnitureBlock,
    });
    addQuantity('livingAreaLevel', `Living area, ${name}`, living, 'area', name);
    addQuantity('wallAreaNetLevel', `Wall area net of openings, ${name}`, net, 'area', name);
    addQuantity('wallAreaGrossLevel', `Wall area gross, ${name}`, gross, 'area', name);
    addQuantity('wallRunLevel', `Wall run, ${name}`, run, 'length', name);
    addQuantity('doors', `Doors, ${name}`, null, null, name, null, levelOpenings.filter((o) => o.kind === 'door').length);
    addQuantity('windows', `Windows, ${name}`, null, null, name, null, levelOpenings.filter((o) => o.kind === 'window').length);
  }

  const priced = [...plan.openings.filter((o) => finite(o.price)), ...plan.furniture.filter((f) => finite(f.price))];
  const costs = priced.length ? {
    pricedItemCount: priced.length,
    pricedTotal: pyRound(priced.reduce((s, i) => s + Math.max(i.price, 0), 0), 2),
    unpricedItemCount: plan.openings.length + plan.furniture.length - priced.length,
    note: 'User-entered prices with no currency; not an estimate.',
  } : null;

  const referenced = new Set();
  for (const item of [...plan.rooms, ...plan.furniture]) for (const p of item.photos) referenced.add(p);
  const missing = assets ? [...referenced].filter((n) => !assets.includes(n)).sort() : [];
  for (const name of missing) gaps.push(`Photo '${name}' is referenced but not included in the package.`);
  if (!plan.rooms.length) gaps.push('No room labels: per-room quantities are unavailable; only level totals are reported.');
  if (!plan.walls.length) gaps.push('Plan has no walls.');

  // Building-level living/gross come from the same statistics block planStatistics
  // exports (ArchiPlan handoff reads stats.totals for exactly this), so the two
  // modules can never disagree. Unknown stays null: no rooms, no living area.
  const stats = planStatistics(input, opts).statistics;
  const totalRun = plan.walls.reduce((s, w) => s + w.length, 0);
  const knownLevels = levelEntries.filter((l) => l.wallAreaNet && finite(l.wallAreaNet.value));
  const scope = {
    title: plan.title != null ? plan.title : 'Untitled plan',
    producer: plan.producer != null ? plan.producer : null,
    units: { metric: 'metres and square metres', imperial: 'feet and square feet, rounded to 0.1' },
    summary: {
      levelCount: levelEntries.length,
      roomCount: plan.rooms.length,
      wallCount: plan.walls.length,
      doorCount: plan.openings.filter((o) => o.kind === 'door').length,
      windowCount: plan.openings.filter((o) => o.kind === 'window').length,
      furnitureCount: plan.furniture.length,
      livingArea: measure(plan.rooms.length && stats ? stats.totals.livingArea : null, 'area'),
      grossArea: measure(plan.rooms.length && stats ? stats.totals.grossArea : null, 'area'),
      wallRun: measure(totalRun, 'length'),
      wallAreaNet: measure(knownLevels.length ? knownLevels.reduce((s, l) => s + l.wallAreaNet.value, 0) : null, 'area'),
      roomsWithPhotos: plan.rooms.filter((r) => r.photos.length).length,
      photoFileCount: assets ? plan.rooms.concat(plan.furniture).flatMap((i) => i.photos).filter((p) => assets.includes(p)).length : null,
    },
    levels: levelEntries,
    quantities,
    notes: {
      planNotes: plan.planNotes != null ? plan.planNotes : null,
      pinnedNotes: plan.notes.filter((n) => n.text).map((n) => n.text),
      wallNotes: [],
      roomNotes: plan.rooms.filter((r) => r.note).map((r) => ({ room: r.name != null ? r.name : null, note: r.note })),
      furnitureNotes: plan.furniture.filter((f) => f.note).map((f) => ({ category: f.category != null ? f.category : null, note: f.note })),
    },
    costs,
    evidence: { missingPhotos: missing, unreferencedFiles: assets ? assets.filter((a) => !referenced.has(a)).sort() : [] },
    assumptions,
    gaps,
    codesApplied: [...new Set(Object.keys(codes).filter((k) => quantities.some((q) => q.key === k)))].sort(),
    conventions: {
      contract: plan.contract,
      floorArea: 'interior-area.js interiorRoomArea (clear area, wall footprints removed)',
      ceilingArea: 'ceiling-reconstruct.reconstructCeilingForRoom, method reported per room',
      boundaryToleranceM: BOUNDARY_TOLERANCE_M,
      quantityKeys: ['floorArea', 'ceilingArea', 'wallAreaNetRoom', 'wallRunRoom', 'livingAreaLevel', 'wallAreaNetLevel', 'wallAreaGrossLevel', 'wallRunLevel', 'doors', 'windows'],
      unknownPolicy: 'a measure that cannot be known is omitted from quantities and reported in gaps[]; unknown is never 0',
    },
  };
  return { ok: true, scope, reason: null };
}

module.exports = { handoff, measure, inRing, HANDOFF_DEFAULTS: { DEFAULT_WALL_HEIGHT, DEFAULT_CEILING_HEIGHT, DEFAULT_DOOR_HEIGHT, DEFAULT_WINDOW_HEIGHT, DEFAULT_SILL, BOUNDARY_TOLERANCE_M } };
