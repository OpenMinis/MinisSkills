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
  const known = ['floorAreaM2', 'wallGrossAreaM2', 'ceilingAreaM2'].every((k) => report.totals[k] && typeof report.totals[k].value === 'number');
  record('V-REP.coverage', 'report totals carry numeric measures for floor/wall gross/ceiling',
    known ? 'PASS' : 'FAIL', `floor=${report.totals.floorAreaM2.value} wallGross=${report.totals.wallGrossAreaM2.value} ceiling=${report.totals.ceilingAreaM2.value}`);
  record('V-REP.measures', 'every element quantity is a {value, coverage, reason} measure object',
    report.elements.every((e) => e.grossAreaM2 && 'value' in e.grossAreaM2 && 'coverage' in e.grossAreaM2 && 'reason' in e.grossAreaM2) ? 'PASS' : 'FAIL');
  record('V-REP.null', 'unknown is null, never zero',
    report.totals.openingAreaM2.value === null && report.totals.openingAreaM2.status === 'unavailable' ? 'PASS' : 'FAIL',
    `openingAreaM2=${JSON.stringify(report.totals.openingAreaM2.value)} status=${report.totals.openingAreaM2.status}`);
}

// ------------------------------------------- 4. documented SPEC/engine gaps
const pend = (id, what, reason) => record(id, what, 'PENDING', reason);

if (report) {
  if (report.schemaVersion !== 'roomplan.report/1') {
    pend('P-01', 'report schemaVersion is pattern "roomplan.report/1"', `engine emits "${report.schemaVersion}" (quantities.js buildReport literal); schema accepts both, code unchanged by instruction`);
  } else record('P-01', 'report schemaVersion is pattern "roomplan.report/1"', 'PASS');

  if (!('floorArea' in report.totals) && 'floorAreaM2' in report.totals) {
    pend('P-02', 'totals use the SPEC §3 names (floorArea, wallAreaGross, wallAreaNet, openingArea, wallLength, paintArea, livingArea, roomCount, wallCount, …)',
      'engine names them floorAreaM2/wallGrossAreaM2/wallNetAreaM2/openingAreaM2; wallLength, paintArea, livingArea and roomsWithoutArea are not computed at all');
  } else record('P-02', 'totals use the SPEC §3 names', 'PASS');

  const st = report.elements[0] && report.elements[0].grossAreaM2;
  if (st && st.status === undefined) {
    pend('P-03', 'every measure carries status (§4)', 'single-element measures carry {value, coverage, reason} only; status is added by sum() for subtotals');
  } else record('P-03', 'every measure carries status (§4)', 'PASS');

  if (!Array.isArray(report.assumptions)) {
    pend('P-04', 'report carries assumptions[]', 'buildReport emits conventions.caveat instead of a top-level assumptions array');
  } else record('P-04', 'report carries assumptions[]', 'PASS');

  if (!report.warnings.length) {
    record('P-05', 'warnings carry {code, message, severity}', 'PASS', 'fixture produced no warning (check vacuous)');
  } else if (report.warnings.some((w) => w.message === undefined || w.severity === undefined)) {
    pend('P-05', 'warnings carry {code, message, severity}', `engine warns ${JSON.stringify(report.warnings.map((w) => Object.keys(w)))}; message/severity absent, schema requires code only`);
  } else record('P-05', 'warnings carry {code, message, severity}', 'PASS');

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
  if (explicitRoom && explicitRoom.ceilingAreaM2 && explicitRoom.ceilingAreaM2.method === 'explicit') {
    pend('P-06', 'ceilingMethod enum is supplied|knee|section|extrusion|flat|unavailable', `engine reports method 'explicit' for a supplied ceiling polygon (status '${explicitRoom.ceilingAreaM2.status}'); schema accepts it as the SPEC word 'supplied'`);
  } else record('P-06', 'ceilingMethod enum contains only SPEC values', 'PASS', `explicit ceiling method=${explicitRoom && explicitRoom.ceilingAreaM2.method}`);
}
if (capture) {
  const missing = ['units', 'axes', 'stories', 'raw'].filter((k) => !(k in capture));
  if (missing.length) {
    pend('P-07', 'capture exposes units/axes/stories/raw (§3)', `adapter does not emit ${missing.join(', ')}; schema keeps them optional and the facts live in conventions/sourceAxes, surfaces[].story and completeness`);
  } else record('P-07', 'capture exposes units/axes/stories/raw (§3)', 'PASS');
  if (!cap_surfaceProvenance(capture)) {
    pend('P-08', 'every capture surface carries provenance (§3/§4)', 'capture-export emits identifierProvenance/sourceStoryProvenance but no per-surface provenance{status,coverage,reason}');
  } else record('P-08', 'every capture surface carries provenance', 'PASS');
}
function cap_surfaceProvenance(c) {
  return (c.surfaces || []).every((s) => s.provenance && s.provenance.status);
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
