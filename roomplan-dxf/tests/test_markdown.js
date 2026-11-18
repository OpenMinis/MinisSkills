'use strict';
/**
 * tests/test_markdown.js — scripts/lib/out-md.js renders report-v1 as Markdown.
 *
 * The Markdown summary is a CONSUMER (SPEC section 6): it may format, it may not
 * compute. These checks are therefore about honesty of presentation:
 *   - the project title and the per-story block exist;
 *   - a `partial` total is visibly marked partial and is never printed as a total;
 *   - an `unavailable` measure prints a reason instead of 0;
 *   - assumptions[] and the handoff `gaps[]` get their own sections;
 *   - the provenance legend exists (one sentence per status class).
 */
const assert = require('assert');
const path = require('path');
const LIB = path.join(__dirname, '..', 'scripts', 'lib');
const { buildReport } = require(path.join(LIB, 'quantities'));
const { renderMarkdown } = require(path.join(LIB, 'out-md'));

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

const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
const wall = { identifier: 'w', kind: 'wall', story: 0, dimensions: { x: 4, y: 2.5, z: 0.1 }, transform: I };
// deliberately unlinked: an opening without a parent cannot be netted or painted
const orphan = { identifier: 'd-orphan', kind: 'door', story: 0, parentIdentifier: null, dimensions: { x: 0.9, y: 2.1, z: 0 }, transform: I };
const room = { identifier: 'r1', story: 0, label: 'Soba', area: 10, vertices: [{ x: 0, z: 0 }, { x: 4, z: 0 }, { x: 4, z: 3 }, { x: 0, z: 3 }] };
const capture = { kind: 'optimized', sourceSHA256: 'a'.repeat(64), surfaces: [wall, orphan], objects: [], rooms: [room] };
const report = buildReport(capture, {});
const md = renderMarkdown(report, { project: 'Kuća Test', date: '2026-11-07' });

check('title is the project name', () => assert(/^# Kuća Test — količine/.test(md), md.slice(0, 80)));
check('contract line names report-v1 and capture-v1', () => {
  assert(md.includes('roomplan.report/1'));
  assert(md.includes('roomplan.capture/1'));
});
check('per-story section exists with floor, ceiling+method, walls, paint', () => {
  assert(md.includes('## Po etažama'));
  assert(md.includes('- Pod:'));
  assert(/Strop: .* metoda: /.test(md));
  assert(md.includes('- Zidovi bruto:'));
  assert(md.includes('- Bojanje:'));
});
check('a partial total is marked partial and never presented as a building total', () => {
  assert(report.totals.wallAreaNet.coverage === 'partial', 'fixture must produce a partial net area');
  assert(/\(partial \d+\/\d+\)/.test(md), 'partial counts missing from the Markdown');
  assert(/Nepotpuno/.test(md), 'no incomplete banner');
  assert(md.includes('wallAreaNet'));
});
check('an unavailable measure prints a reason, never 0', () => {
  assert(report.totals.volume.value === null);
  assert(/n\/a — /.test(md), 'unavailable measures must render as "n/a — reason"');
  assert(!/- Pod: 0\.000/.test(md));
});
check('rooms section lists the room with its areas', () => {
  assert(md.includes('## Sobe'));
  assert(md.includes('**Soba**'));
});
check('assumptions section lists every assumption', () => {
  assert(md.includes('## Pretpostavke'));
  for (const a of report.assumptions) assert(md.includes(a.slice(0, 40)), `assumption missing: ${a.slice(0, 40)}`);
});
check('gaps[] from the handoff block have their own section', () => {
  assert(md.includes('## Nedostaci (gaps)'));
  const gaps = (report.handoff && report.handoff.gaps) || [];
  assert(gaps.length > 0, 'handoff produced no gap for this fixture');
  assert(md.includes(String(gaps[0]).slice(0, 30)), 'first gap missing from the Markdown');
});
check('provenance legend is present and explains all five statuses', () => {
  assert(md.includes('## Legenda podrijetla'));
  for (const s of ['supplied', 'computed', 'reconstructed', 'estimated', 'unavailable']) assert(md.includes(`\`${s}\``), `legend missing ${s}`);
});
check('markdown never emits a Markdown table that would imply accuracy', () => {
  assert(!/\n\|.*\|/.test(md), 'unexpected table in the summary');
});
check('rendering is pure: it does not mutate the report', () => {
  const before = JSON.stringify(report);
  renderMarkdown(report, {});
  assert.strictEqual(JSON.stringify(report), before);
});

check('warnings section lists code, severity and message', () => {
  const withWarnings = JSON.parse(JSON.stringify(report));
  withWarnings.warnings = [
    { code: 'roomplan.wall-no-thickness-centerline', message: 'no captured thickness', severity: 'warning' },
    { code: 'roomplan.north-direction-approximate', message: 'approximate bearing', severity: 'info' },
  ];
  const out = renderMarkdown(withWarnings, { project: 'W', date: '2026-11-07' });
  assert(out.includes('roomplan.wall-no-thickness-centerline'), 'warning code missing');
  assert(out.includes('(warning)'), 'severity missing');
  assert(out.includes('(info)'), 'second severity missing');
  assert(!out.includes('_Nema upozorenja._'), 'still claims no warnings');
});

console.log(`markdown: ${checks} checks passed`);
