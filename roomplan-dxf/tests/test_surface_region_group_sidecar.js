'use strict';
/**
 * tests/test_surface_region_group_sidecar.js — AUTO-DISCOVERY of the group
 * confirmation sidecar.
 *
 * `--surface-region-groups <file>` stays the explicit way to hand over a
 * user-confirmed Surface Region grouping. This suite proves what happens when
 * the flag is absent:
 *
 *   1. only the documented names are looked for, most specific first, and the
 *      walk never turns into "any *.json in the folder";
 *   2. the sidecar is still source-SHA256 scoped — a file written for another
 *      capture is NOT applied to this one;
 *   3. an unusable auto-discovered sidecar never breaks a conversion: it is
 *      ignored with a recorded warning and the run finishes with zero groups;
 *   4. an explicit path keeps its strict behaviour (mismatch = hard error);
 *   5. an applied group stays a non-additive reference: member face areas and
 *      their sum are unchanged, the group only adds metadata;
 *   6. group semantics (user-confirmed, >=2 known members, one room/story) are
 *      exactly as strict for a discovered file as for an explicit one.
 *
 * No shipped fixtures: the 6 x 4 m optimized-v1 capture is generated here.
 */
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const CONV = path.join(__dirname, '..', 'scripts', 'roomplan-to-dxf.js');
const sidecar = require(path.join(__dirname, '..', 'scripts', 'lib', 'group-sidecar'));

let checks = 0;
function check(name, fn) {
  try {
    fn();
    checks += 1;
  } catch (e) {
    console.error(`FAIL ${name}: ${e.message}`);
    process.exit(1);
  }
}

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'sr-sidecar-'));
const I4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const T = (x, y, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1];

/** Same 6 x 4 m room, ONE story, TWO supplied ceiling faces split at x = 3. */
function optimizedCapture() {
  const half = (cx) => ({ transform: T(cx, 2.6, 2), polygonCorners: [[-1.5, 0, -2], [1.5, 0, -2], [1.5, 0, 2], [-1.5, 0, 2]] });
  return {
    format_version: 1,
    source: { generator: 'synthetic' },
    walls: [
      { identifier: 'W1', category: { wall: {} }, confidence: { high: {} }, dimensions: [6, 2.5, 0], transform: T(3, 1.25, 0), story: 0 },
      { identifier: 'W2', category: { wall: {} }, confidence: { high: {} }, dimensions: [6, 2.5, 0], transform: T(3, 1.25, 4), story: 0 },
    ],
    rooms: [{
      id: 'R1', label_automated: 'Kuhinja', category: 'kitchen', story: 0, area: 24,
      center_xz: [3, 2], floor_height: 0, vertices_x: [0, 6, 6, 0], vertices_z: [0, 0, 4, 4],
      ceiling: [half(1.5), half(4.5)],
    }],
    doors: [], windows: [], objects: [],
    floors: [{
      identifier: 'F1', category: { floor: {} }, confidence: { high: {} }, dimensions: [6, 4, 0],
      transform: T(3, 0, 2), polygonCorners: [[-3, 0, -2], [3, 0, -2], [3, 0, 2], [-3, 0, 2]], story: 0,
    }],
    alignment_transform: I4,
  };
}

const groupsFor = (sha, members = ['SR R1.1', 'SR R1.2'], id = 'K1') => ({
  sourceSHA256: sha, groups: [{ id, confirmation: 'user-confirmed', members }],
});

let projectSeq = 0;
/** A fresh project directory holding one scan; returns its path. */
function project(name, sidecars) {
  projectSeq += 1;
  const dir = path.join(TMP, `${name}-${projectSeq}`);
  fs.mkdirSync(dir, { recursive: true });
  const text = JSON.stringify(optimizedCapture());
  fs.writeFileSync(path.join(dir, 'roomplan.json'), text);
  for (const [file, body] of Object.entries(sidecars || {})) {
    fs.mkdirSync(path.dirname(path.join(dir, file)), { recursive: true });
    fs.writeFileSync(path.join(dir, file), typeof body === 'string' ? body : JSON.stringify(body));
  }
  return dir;
}

/** Run the CLI on a project directory; returns {status, stdout, stderr, report, md, sha}. */
function run(dir, extra) {
  const out = path.join(dir, `out-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const args = [CONV, dir, out, '--report', '--md'].concat(extra || []);
  const res = spawnSync('node', args, { encoding: 'utf8' });
  const base = path.basename(dir);
  const reportPath = path.join(out, `${base}.report.json`);
  const report = fs.existsSync(reportPath) ? JSON.parse(fs.readFileSync(reportPath, 'utf8')) : null;
  const mdPath = path.join(out, `${base}.md`);
  return {
    status: res.status,
    stdout: res.stdout || '',
    stderr: res.stderr || '',
    report,
    md: fs.existsSync(mdPath) ? fs.readFileSync(mdPath, 'utf8') : null,
    sha: report && report.surfaceRegions ? report.surfaceRegions.sourceSHA256 : null,
  };
}

const warnCodes = (report) => (report.warnings || []).map((w) => w.code);

/* ------------------------------------------------------- 1. candidate names */

check('candidate names are fixed, documented and most-specific-first', () => {
  const list = sidecar.candidates('/p/scan', { scanPath: '/p/scan/roomplan.json', inputWasDirectory: true });
  assert.deepStrictEqual(list, [
    '/p/scan/roomplan.surface-region-groups.json',
    '/p/scan/surface-region-groups.json',
  ]);
});

check('a scan under data/ also looks in the project root, never for other file names', () => {
  const list = sidecar.candidates('/p', { scanPath: '/p/data/scan.json', inputWasDirectory: true });
  assert.deepStrictEqual(list, [
    '/p/data/scan.surface-region-groups.json',
    '/p/surface-region-groups.json',
    '/p/data/surface-region-groups.json',
  ]);
  assert(list.every((p) => p.endsWith(sidecar.SIDECAR_NAME)), 'every candidate ends with the documented name');
});

check('duplicate candidates are collapsed (file input inside its own folder)', () => {
  const list = sidecar.candidates('/p/scan.json', { scanPath: '/p/scan.json', inputWasDirectory: false });
  assert.strictEqual(list.length, new Set(list).size);
  assert.strictEqual(list.length, 2);
});

/* ------------------------------------------------------------- 2. discovery */

check('discovery reports EVERY present sidecar, so ambiguity is visible', () => {
  const dir = project('discover', {
    'surface-region-groups.json': groupsFor('x'),
    'roomplan.surface-region-groups.json': groupsFor('x'),
  });
  const found = sidecar.discover(dir, { scanPath: path.join(dir, 'roomplan.json'), inputWasDirectory: true });
  assert.strictEqual(found.present.length, 2);
  assert.strictEqual(found.path, path.join(dir, 'roomplan.surface-region-groups.json'));
});

check('discovery finds nothing in an empty project and stops at a directory of that name', () => {
  const dir = project('empty');
  fs.mkdirSync(path.join(dir, 'surface-region-groups.json'));
  const found = sidecar.discover(dir, { scanPath: path.join(dir, 'roomplan.json'), inputWasDirectory: true });
  assert.strictEqual(found.path, null);
  assert.deepStrictEqual(found.present, []);
});

/* ------------------------------------------------------------- 3. hash gate */

check('load applies a matching-hash sidecar and refuses a mismatch', () => {
  const dir = project('hash', { 'surface-region-groups.json': groupsFor('a'.repeat(64)) });
  const file = path.join(dir, 'surface-region-groups.json');
  const ok = sidecar.load(file, 'a'.repeat(64));
  assert(ok.override, 'matching hash must be applied');
  assert.strictEqual(ok.reason, null);
  const bad = sidecar.load(file, 'b'.repeat(64));
  assert.strictEqual(bad.override, null);
  assert(/sourceSHA256 does not match/.test(bad.reason), bad.reason);
});

check('load refuses unreadable, non-JSON, non-object and array sidecars', () => {
  const dir = project('broken', {
    'bad.surface-region-groups.json': '{oops',
    'arr.surface-region-groups.json': JSON.stringify([{ sourceSHA256: 'x' }]),
    'num.surface-region-groups.json': JSON.stringify(7),
  });
  const at = (f) => sidecar.load(path.join(dir, f), 'x');
  assert(/could not be read/.test(at('missing.surface-region-groups.json').reason));
  assert(/not valid JSON/.test(at('bad.surface-region-groups.json').reason));
  assert(/not a JSON object/.test(at('arr.surface-region-groups.json').reason));
  assert(/not a JSON object/.test(at('num.surface-region-groups.json').reason));
});

/* -------------------------------------------------------- 4. CLI: no group */

const plain = run(project('plain'));
check('CLI without a group sidecar: zero groups, provenance "none", exit 0', () => {
  assert.strictEqual(plain.status, 0, plain.stderr);
  assert.deepStrictEqual(plain.report.surfaceRegions.groups, []);
  assert.strictEqual(plain.report.surfaceRegions.groupsSource.mode, 'none');
  assert.strictEqual(plain.report.surfaceRegions.groupsSource.confirmedGroupCount, 0);
});

/* -------------------------------------------------- 5. CLI: auto-discovery */

const autoDir = project('auto', { 'surface-region-groups.json': groupsFor(plain.sha) });
const auto = run(autoDir);
check('CLI auto-discovers the project-level sidecar and records its provenance', () => {
  assert.strictEqual(auto.status, 0, auto.stderr);
  const sr = auto.report.surfaceRegions;
  assert.strictEqual(sr.groups.length, 1);
  assert.strictEqual(sr.groups[0].id, 'K1');
  assert.strictEqual(sr.groupsSource.mode, 'auto-discovered');
  assert.strictEqual(sr.groupsSource.relative, 'surface-region-groups.json');
  assert.strictEqual(sr.groupsSource.confirmedGroupCount, 1);
  assert(!warnCodes(auto.report).includes('roomplan.surface-region-groups-sidecar-ignored'), 'a valid sidecar must not be reported as ignored');
});

check('an auto-discovered group is a reference, not a quantity: face areas unchanged', () => {
  const before = plain.report.surfaceRegions.regions.map((r) => [r.id, r.areaM2]);
  const after = auto.report.surfaceRegions.regions.map((r) => [r.id, r.areaM2]);
  assert.deepStrictEqual(after, before, 'grouping must not touch any face area');
  const g = auto.report.surfaceRegions.groups[0];
  assert.strictEqual(g.faceCount, 2);
  assert(Math.abs(g.areaM2 - 24) < 1e-9, `group area is the reference sum, got ${g.areaM2}`);
  assert.strictEqual(g.bendAngleDegrees, 0, 'two coplanar halves have a 0 degree bend');
  assert.strictEqual(auto.report.totals ? auto.report.totals.ceilingArea.value : null, plain.report.totals ? plain.report.totals.ceilingArea.value : null, 'grouping must not change the ceiling total');
});

check('the Markdown report names the confirmation source', () => {
  assert(auto.md, 'md missing');
  assert(/Potvrda grupa: auto-discovered/.test(auto.md), 'confirmation provenance missing from the Markdown');
});

/* ------------------------------------------- 6. CLI: scan-specific wins, ambiguity */

const bothDir = project('both', {
  'surface-region-groups.json': groupsFor(plain.sha, ['SR R1.1', 'SR R1.2'], 'PROJECT'),
  'roomplan.surface-region-groups.json': groupsFor(plain.sha, ['SR R1.1', 'SR R1.2'], 'SCAN'),
});
const both = run(bothDir);
check('two sidecars: the scan-specific one wins and the ambiguity is warned about', () => {
  assert.strictEqual(both.status, 0, both.stderr);
  assert.deepStrictEqual(both.report.surfaceRegions.groups.map((g) => g.id), ['SCAN']);
  assert(warnCodes(both.report).includes('roomplan.surface-region-groups-sidecar-ambiguous'), 'ambiguity must be recorded');
});

/* ------------------------------------- 7. CLI: stale / broken sidecar ignored */

const staleDir = project('stale', { 'surface-region-groups.json': groupsFor('f'.repeat(64)) });
const stale = run(staleDir);
check('a sidecar for ANOTHER capture is ignored with a warning, conversion still succeeds', () => {
  assert.strictEqual(stale.status, 0, stale.stderr);
  assert.deepStrictEqual(stale.report.surfaceRegions.groups, []);
  assert.strictEqual(stale.report.surfaceRegions.groupsSource.mode, 'none');
  const w = (stale.report.warnings || []).find((x) => x.code === 'roomplan.surface-region-groups-sidecar-ignored');
  assert(w, 'missing ignored-sidecar warning');
  assert(/sourceSHA256 does not match/.test(w.message), w.message);
});

const brokenDir = project('brokencli', { 'surface-region-groups.json': '{not json' });
const brokenRun = run(brokenDir);
check('unparsable auto-discovered sidecar does not fail the conversion', () => {
  assert.strictEqual(brokenRun.status, 0, brokenRun.stderr);
  assert.deepStrictEqual(brokenRun.report.surfaceRegions.groups, []);
  assert(warnCodes(brokenRun.report).includes('roomplan.surface-region-groups-sidecar-ignored'));
});

/* --------------------------------------------- 8. CLI: explicit stays strict */

const explicitDir = project('explicit', { 'surface-region-groups.json': groupsFor(plain.sha, ['SR R1.1', 'SR R1.2'], 'AUTO') });
const explicitFile = path.join(TMP, 'explicit-groups.json');
fs.writeFileSync(explicitFile, JSON.stringify(groupsFor(plain.sha, ['SR R1.1', 'SR R1.2'], 'EXPLICIT')));
const explicitRun = run(explicitDir, ['--surface-region-groups', explicitFile]);
check('an explicit path wins over the auto-discovered file', () => {
  assert.strictEqual(explicitRun.status, 0, explicitRun.stderr);
  assert.deepStrictEqual(explicitRun.report.surfaceRegions.groups.map((g) => g.id), ['EXPLICIT']);
  assert.strictEqual(explicitRun.report.surfaceRegions.groupsSource.mode, 'explicit');
});

const wrongFile = path.join(TMP, 'explicit-wrong.json');
fs.writeFileSync(wrongFile, JSON.stringify(groupsFor('0'.repeat(64))));
const wrongRun = run(project('explicitbad'), ['--surface-region-groups', wrongFile]);
check('an explicit sidecar with the wrong hash is a HARD error (never a silent skip)', () => {
  assert.notStrictEqual(wrongRun.status, 0, 'explicit mismatch must fail');
  assert(/source SHA256 mismatch/i.test(wrongRun.stderr), wrongRun.stderr.slice(0, 400));
});

/* -------------------------------- 9. CLI: same strict group rules when discovered */

const unknownMemberDir = project('unknown', { 'surface-region-groups.json': groupsFor(plain.sha, ['SR R1.1', 'SR R9.9']) });
const unknownMember = run(unknownMemberDir);
check('a discovered group naming an unknown face fails like an explicit one', () => {
  assert.notStrictEqual(unknownMember.status, 0, 'unknown member must fail');
  assert(/Unknown or multiply grouped Surface Region/.test(unknownMember.stderr), unknownMember.stderr.slice(0, 400));
});

const unconfirmedDir = project('unconfirmed', {
  'surface-region-groups.json': { sourceSHA256: plain.sha, groups: [{ id: 'K1', members: ['SR R1.1', 'SR R1.2'] }] },
});
const unconfirmed = run(unconfirmedDir);
check('a discovered group without user confirmation is refused, never assumed', () => {
  assert.notStrictEqual(unconfirmed.status, 0, 'missing confirmation must fail');
  assert(/Only user-confirmed groups/.test(unconfirmed.stderr), unconfirmed.stderr.slice(0, 400));
});

console.log(`surface-region group sidecar: ${checks}/${checks} checks passed`);
