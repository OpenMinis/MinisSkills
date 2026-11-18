'use strict';
/**
 * tests/test_schema.js — contract check for scripts/lib/schema/{capture,report}-v1.json
 *
 * 1. Both schema documents are valid JSON, declare draft 2020-12, use only
 *    supported keywords and resolve every (internal) $ref.
 * 2. A synthetic optimized capture is pushed through the REAL pipeline
 *    (decode-optimized -> assignStories -> buildCapture / buildReport) and the
 *    output is validated against the matching schema.
 * 3. SPEC.md section 3 fields that the engine does not emit are listed as
 *    PENDING with the exact reason instead of being silently skipped. A PENDING
 *    row never hides a FAIL: FAIL means schema and output disagree.
 *
 * No dependencies: the validator lives in tests/lib/mini-schema.js. The same
 * schemas were additionally checked with python jsonschema 4.23
 * (Draft202012Validator) — see REPORT.md.
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const { validate, checkSchemaDocument } = require('./lib/mini-schema');
const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const { decode } = require(path.join(LIB, 'decode-optimized'));
const { assignStories } = require(path.join(LIB, 'story'));
const { applyArchitecturalAlignment } = require(path.join(LIB, 'align'));
const { buildCapture } = require(path.join(LIB, 'capture-export'));
const { buildReport } = require(path.join(LIB, 'quantities'));

const SCHEMA_DIR = path.join(LIB, 'schema');
const rows = [];
let failures = 0;

function record(id, what, verdict, detail) {
  if (verdict === 'FAIL') failures++;
  rows.push({ id, what, verdict, detail: detail || '' });
}

// ---------------------------------------------------------------- synthetic input
const at = (x, z, rot = 0) => [Math.cos(rot), 0, -Math.sin(rot), 0, 0, 1, 0, 0, Math.sin(rot), 0, Math.cos(rot), 0, x, 0, z, 1];
const GABLE = [[-2, 0], [2, 0], [2, 1.6], [0, 2.5], [-2, 1.6]];
const synthetic = {
  format_version: 1,
  walls: [
    {
      identifier: 'w-gable', category: 'wall', story: 0, dimensions: [4, 2.5, 0.2],
      transform: at(0, -2.5), polygonCorners: GABLE.map(([x, y]) => [x, y, 0]), wall_thickness: 0.2,
    },
    { identifier: 'w-knee', category: 'wall', story: 0, dimensions: [4, 1.6, 0.2], transform: at(0, 2.5), wall_thickness: 0.2 },
  ],
  floors: [{
    identifier: 'floor-a', category: 'floor', story: 0, transform: at(0, 0),
    polygonCorners: [[-2, 0, -2.5], [2, 0, -2.5], [2, 0, 2.5], [-2, 0, 2.5]],
  }],
  doors: [{ identifier: 'door-1', parentIdentifier: 'w-knee', category: 'door', story: 0, dimensions: [0.9, 2.1, 0], transform: at(0, 2.38) }],
  windows: [{ identifier: 'win-1', parentIdentifier: 'w-knee', category: 'window', story: 0, dimensions: [1.2, 1.1, 0], transform: at(0, 2.38) }],
  openings: [],
  objects: [{ identifier: 'obj-1', category: 'chair', story: 0, dimensions: [0.5, 0.9, 0.5], transform: at(0, 0) }],
  rooms: [{
    id: 'room-a', category: 'livingRoom', label_automated: 'Living', story: 0,
    area: 22, floor_height: 0,
    vertices_x: [-2, 2, 2, -2], vertices_z: [-2.5, -2.5, 2.5, 2.5], center_xz: [0, 0],
    edges: [['w-gable'], ['w-knee']], doors: ['door-1'], windows: ['win-1'], openings: [],
  }],
  alignment_transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
};

let capture;
let report;
let captureSchema;
let reportSchema;
try {
  const bytes = Buffer.from(JSON.stringify(synthetic), 'utf8');
  const model = decode(bytes, 'synthetic-schema-check.json');
  assignStories(model);
  report = buildReport(model, synthetic);
  applyArchitecturalAlignment(model);
  capture = buildCapture(model, synthetic, { includeGeo: false });
  // Optional: write the exact documents that were validated, so an external
  // draft 2020-12 validator (python jsonschema) can re-check them.
  if (process.env.ROOMPLAN_SCHEMA_DUMP) {
    fs.mkdirSync(process.env.ROOMPLAN_SCHEMA_DUMP, { recursive: true });
    fs.writeFileSync(path.join(process.env.ROOMPLAN_SCHEMA_DUMP, 'synthetic.capture.json'), JSON.stringify(capture, null, 1));
    fs.writeFileSync(path.join(process.env.ROOMPLAN_SCHEMA_DUMP, 'synthetic.report.json'), JSON.stringify(report, null, 1));
  }
} catch (e) {
  record('T-00', 'synthetic capture -> capture-export + buildReport pipeline', 'FAIL', e.message);
}

// ------------------------------------------------------ 1. schema documents
for (const [id, file, key] of [['S-CAP', 'capture-v1.json', 'captureSchema'], ['S-REP', 'report-v1.json', 'reportSchema']]) {
  const p = path.join(SCHEMA_DIR, file);
  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(p, 'utf8'));
    record(`${id}.1`, `${file} is valid JSON`, 'PASS');
  } catch (e) {
    record(`${id}.1`, `${file} is valid JSON`, 'FAIL', e.message);
    continue;
  }
  const problems = checkSchemaDocument(doc);
  record(`${id}.2`, `${file} is draft 2020-12, internal $refs only, supported keywords`, problems.length ? 'FAIL' : 'PASS', problems.slice(0, 4).join(' | '));
  if (key === 'captureSchema') captureSchema = doc; else reportSchema = doc;
}

// ------------------------------------------------- 2. real output vs schema
function digest(errors) {
  return errors.slice(0, 6).map((e) => `${e.path}: ${e.message}`).join(' | ') || '';
}
if (capture && captureSchema) {
  const errs = validate(captureSchema, capture);
  record('V-CAP', 'buildCapture output conforms to capture-v1', errs.length ? 'FAIL' : 'PASS', digest(errs));
} else record('V-CAP', 'buildCapture output conforms to capture-v1', 'FAIL', 'no document produced');

if (report && reportSchema) {
  const errs = validate(reportSchema, report);
  record('V-REP', 'buildReport output conforms to report-v1', errs.length ? 'FAIL' : 'PASS', digest(errs));
} else record('V-REP', 'buildReport output conforms to report-v1', 'FAIL', 'no document produced');

// -------------------------- 3. what actually got exercised (anti-false-pass)
if (capture) {
  record('V-CAP.coverage', 'capture carries surfaces/objects/rooms and a sha256',
    capture.surfaces.length === 5 && capture.objects.length === 1 && capture.rooms.length === 1 && /^[0-9a-f]{64}$/.test(capture.source.sha256) ? 'PASS' : 'FAIL',
    `surfaces=${capture.surfaces.length} objects=${capture.objects.length} rooms=${capture.rooms.length}`);
}
if (report) {
  const known = ['floorArea', 'wallAreaGross', 'wallAreaNet', 'paintArea', 'ceilingArea'].every((k) => report.totals[k] && typeof report.totals[k].value === 'number');
  record('V-REP.coverage', 'report totals carry numeric measures for floor/wall gross/wall net/paint/ceiling',
    known ? 'PASS' : 'FAIL', `floor=${report.totals.floorArea.value} wallGross=${report.totals.wallAreaGross.value} wallNet=${report.totals.wallAreaNet.value} ceiling=${report.totals.ceilingArea.value}`);
  record('V-REP.measures', 'every element quantity is a {value, status, coverage, included, expected, reason} measure',
    report.elements.every((e) => e.area && ['value', 'status', 'coverage', 'included', 'expected', 'reason'].every((k) => k in e.area)) ? 'PASS' : 'FAIL');
  record('V-REP.null', 'unknown is null, never zero',
    report.totals.volume.value === null && report.totals.volume.status === 'unavailable' ? 'PASS' : 'FAIL',
    `volume=${JSON.stringify(report.totals.volume.value)} status=${report.totals.volume.status}`);
}

// ---------------------- 4. the gaps P1 recorded are CLOSED (0 pending by design)
// C-1 (report shape), C-2 (capture shape), C-5 (paintArea), C-6 (status vs
// coverage) and C-7 (captureSchema) were fixed in P4. Nothing here may go back
// to PENDING: a missing canonical field is a FAIL, because a PENDING row used to
// hide a contract break behind a comment.
const ok = (id, what, cond, detail) => record(id, what, cond ? 'PASS' : 'FAIL', detail || '');

if (report) {
  ok('P-01', 'report schemaVersion is exactly "roomplan.report/1"', report.schemaVersion === 'roomplan.report/1', report.schemaVersion);
  const TOTAL_KEYS = ['floorArea', 'ceilingArea', 'wallAreaGross', 'wallAreaNet', 'openingArea', 'wallLength', 'paintArea', 'livingArea', 'roomsWithoutArea'];
  const missingTotals = TOTAL_KEYS.filter((k) => !(report.totals[k] && 'value' in report.totals[k]));
  ok('P-02', 'totals use the SPEC section 3 names', missingTotals.length === 0, missingTotals.length ? `missing ${missingTotals.join(', ')}` : TOTAL_KEYS.join(', '));
  const COUNTS = ['roomCount', 'wallCount', 'doorCount', 'windowCount', 'objectCount'];
  ok('P-02b', 'totals.counts carries roomCount/wallCount/doorCount/windowCount/objectCount',
    COUNTS.every((k) => Number.isInteger(report.totals.counts[k])), JSON.stringify(report.totals.counts));
  const MEASURE_KEYS = ['value', 'status', 'coverage', 'included', 'expected', 'reason'];
  const allMeasures = [...Object.values(report.totals).filter((v) => v && typeof v === 'object' && 'status' in v), ...report.elements.map((e) => e.area)];
  ok('P-03', 'every measure carries status/coverage/included/expected (section 4)',
    allMeasures.every((m) => MEASURE_KEYS.every((k) => k in m)), `${allMeasures.length} measures checked`);
  ok('P-04', 'report carries assumptions[] (strings)',
    Array.isArray(report.assumptions) && report.assumptions.length > 0 && report.assumptions.every((a) => typeof a === 'string'),
    `${(report.assumptions || []).length} assumption(s)`);
  ok('P-05', 'warnings carry {code, message, severity}',
    report.warnings.every((w) => w.code && w.message && w.severity), `${report.warnings.length} warning(s)`);
  ok('P-06', 'element ids are `id`, never `key`', report.elements.every((e) => typeof e.id === 'string' && !('key' in e)),
    report.elements.map((e) => e.id).slice(0, 3).join(', '));
  ok('P-06b', 'element room references are `roomRefs`, never `roomMemberships`',
    report.elements.every((e) => Array.isArray(e.roomRefs) && !('roomMemberships' in e)), 'roomRefs[]');
  ok('P-07', 'report records the capture contract it consumed (C-7)',
    report.source.captureSchema === 'roomplan.capture/1', `captureSchema=${report.source.captureSchema}`);
  ok('P-09', 'statistics and handoff blocks are carried inside report-v1 (section 6)',
    ('statistics' in report) && ('handoff' in report), `statistics=${report.statistics ? 'object' : 'null'} handoff=${report.handoff ? 'object' : 'null'}`);

  // an explicit (supplied) ceiling is not in the main fixture, so probe it
  const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const explicitCapture = {
    kind: 'optimized', surfaces: [], objects: [],
    rooms: [{
      identifier: 'r-explicit', story: 0, area: 36, floorHeight: 3,
      vertices: [{ x: -3, z: -3 }, { x: 3, z: -3 }, { x: 3, z: 3 }, { x: -3, z: 3 }],
      ceiling: [{ polygon: [[-2, -2], [2, -2], [2, 2], [-2, 2]], transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 3, 0, 1] }],
    }],
  };
  explicitCapture.rooms[0].ceilingCurrent = explicitCapture.rooms[0].ceiling;
  const explicitRoom = buildReport(explicitCapture, {}).rooms[0];
  const CEIL_METHODS = ['supplied', 'knee', 'section', 'extrusion', 'flat', 'unavailable'];
  const em = explicitRoom && explicitRoom.ceilingArea;
  ok('P-08', 'ceilingMethod enum is supplied|knee|section|extrusion|flat|unavailable (a supplied ceiling is never called "explicit")',
    em && CEIL_METHODS.includes(em.method) && (em.value === null ? em.method === 'unavailable' : em.method === 'supplied'),
    `method=${em && em.method} value=${em && em.value} status=${em && em.status}`);
}
if (capture) {
  const missing = ['units', 'axes', 'stories', 'raw'].filter((k) => !(k in capture));
  ok('P-10', 'capture exposes units/axes/stories/raw (section 3)', missing.length === 0, missing.length ? `missing ${missing.join(', ')}` : `units=${capture.units} axes=${JSON.stringify(capture.axes)} stories=${capture.stories.length} raw.opaque=${capture.raw.opaque.length}`);
  ok('P-11', 'capture source carries filename/sha256/bytes/dialect/dialectEvidence',
    capture.source && typeof capture.source.sha256 === 'string' && 'bytes' in capture.source && 'dialect' in capture.source && Array.isArray(capture.source.dialectEvidence),
    `dialect=${capture.source.dialect} bytes=${capture.source.bytes}`);
  ok('P-12', 'dialect is inside source, never at the top level', !('dialect' in capture) && 'dialect' in capture.source, 'capture.dialect removed');
  const everyProv = (list) => (list || []).every((r) => r.provenance && r.provenance.status && r.provenance.coverage && r.provenance.reason);
  ok('P-13', 'every surface/object/room carries provenance{status,coverage,reason}',
    everyProv(capture.surfaces) && everyProv(capture.objects) && everyProv(capture.rooms),
    `surfaces=${capture.surfaces.length} objects=${capture.objects.length} rooms=${capture.rooms.length}`);
  ok('P-14', 'rooms use polygonXZ/declaredArea, never vertices/area (C-2)',
    capture.rooms.every((r) => ('polygonXZ' in r) && ('declaredArea' in r) && !('vertices' in r) && !('area' in r)), 'polygonXZ + declaredArea');
}

// ------------------------------------------------------------------- output
const w = [15, 58, 9, 0];
const pad = (s, n) => String(s).padEnd(n);
console.log('\n=== schema contract: tests/test_schema.js ===');
console.log(`${pad('ID', w[0])}${pad('CHECK', w[1])}${pad('VERDICT', w[2])}DETAIL`);
for (const r of rows) {
  console.log(`${pad(r.id, w[0])}${pad(r.what.length > 58 ? r.what.slice(0, 55) + '...' : r.what, w[1])}${pad(r.verdict, w[2])}${r.detail}`);
}
const count = (v) => rows.filter((r) => r.verdict === v).length;
console.log(`\nschema-contract: ${count('PASS')} passed, ${count('PENDING')} pending, ${count('FAIL')} failed, ${rows.length} checks`);
if (failures) {
  console.error('\nFAIL: schema and engine output disagree — see rows above.');
  process.exit(1);
}
