'use strict';
/**
 * out-md.js — Markdown summary of a report-v1 document (SPEC section 6).
 *
 * One kernel, many outputs: this module READS report-v1 and formats it. It never
 * re-derives geometry and never rounds away a `partial` or an `unavailable`.
 *
 * Rules that matter more than the layout:
 *   - a `partial` measure is printed with its counts (`3/4`), never as a total;
 *   - an `unavailable` measure prints `n/a — <reason>`, never 0 and never blank;
 *   - the ceiling method is printed next to the ceiling number, because a
 *     reconstructed ceiling is not a measured one;
 *   - gaps from the handoff block are a section of their own: what we could not
 *     measure is part of the deliverable, not an appendix.
 *
 * API: renderMarkdown(report, opts={project, date, sourceName}) -> string
 */
const finite = (v) => typeof v === 'number' && Number.isFinite(v);

/** 3 decimals is a takeoff number; 4+ would promise an accuracy we do not have. */
function num(v) {
  if (!finite(v)) return null;
  return v.toFixed(3);
}

/** One measure as text. Never hides `partial`, never turns unknown into zero. */
function m(measure, unit = 'm²') {
  if (!measure || typeof measure !== 'object') return 'n/a — no measure in the report';
  const v = num(measure.value);
  if (v === null) return `n/a — ${measure.reason || 'no reason recorded'}`;
  const parts = [`${v} ${unit}`];
  if (measure.coverage === 'partial') parts.push(`(partial ${finite(measure.included) ? measure.included : '?'}/${finite(measure.expected) ? measure.expected : '?'})`);
  if (measure.status && measure.status !== 'computed') parts.push(`[${measure.status}]`);
  return parts.join(' ');
}

function esc(text) {
  return String(text == null ? '' : text).replace(/\|/g, '\\|');
}

function storyLabelOf(report, story) {
  const found = (report.rooms || []).find((r) => r.story === story);
  return found ? found.label : null;
}

function renderMarkdown(report, opts = {}) {
  if (!report || typeof report !== 'object') throw new Error('out-md: a report-v1 document is required');
  const L = [];
  const project = opts.project || (report.source && report.source.sha256 ? `roomplan-dxf ${String(report.source.sha256).slice(0, 8)}` : 'roomplan-dxf takeoff');
  const totals = report.totals || {};
  const assumptions = Array.isArray(report.assumptions) ? report.assumptions : [];
  const warnings = Array.isArray(report.warnings) ? report.warnings : [];
  const gaps = (report.handoff && Array.isArray(report.handoff.gaps)) ? report.handoff.gaps : [];
  const stories = [...new Set((report.rooms || []).map((r) => r.story))].sort((a, b) => (a ?? 0) - (b ?? 0));

  // ------------------------------------------------------------- title
  L.push(`# ${esc(project)} — količine`);
  L.push('');
  L.push(`Kontrakt: \`${report.schemaVersion || 'roomplan.report/1'}\` · capture \`${(report.source && report.source.captureSchema) || 'roomplan.capture/1'}\` · dijalekt \`${(report.source && report.source.dialect) || 'nepoznat'}\`${opts.date ? ` · ${esc(opts.date)}` : ''}`);
  L.push('');
  const partial = Object.entries(totals).filter(([, v]) => v && typeof v === 'object' && v.coverage === 'partial' && v.value !== null).map(([k]) => k);
  const CORE = ['floorArea', 'ceilingArea', 'wallAreaGross', 'wallAreaNet', 'openingArea', 'wallLength', 'paintArea', 'livingArea'];
 const unavailable = CORE.filter((k) => totals[k] && totals[k].value === null);
  L.push(partial.length || unavailable.length
    ? `> **Nepotpuno.** Djelomično: ${partial.length ? partial.join(', ') : '—'}. Neizmjereno: ${unavailable.length ? unavailable.join(', ') : '—'}. Ove vrijednosti nisu građevinske ukupne vrijednosti.`
    : '> Sva zbrojena polja u ovom sažetku su potpuna za dekodirane elemente; to još nije tvrdnja o cijeloj zgradi.');
  L.push('');

  // ---------------------------------------------------------- per story
  const storyTotals = new Map();
  for (const s of report.stories || []) storyTotals.set(s.story, s.totals);
  if (stories.length) {
    L.push('## Po etažama');
    L.push('');
    for (const story of stories) {
      const t = storyTotals.get(story) || totals;
      const label = storyLabelOf(report, story) || (story === 0 ? 'Prizemlje' : `${story}. etaža`);
      L.push(`### ${esc(label)} (${story === null ? 'bez oznake' : story})`);
      L.push('');
      L.push(`- Pod: ${m(t.floorArea)}`);
      const rooms = (report.rooms || []).filter((r) => r.story === story);
      const methods = [...new Set(rooms.map((r) => (r.ceilingArea && r.ceilingArea.method) || 'unavailable'))];
      L.push(`- Strop: ${m(t.ceilingArea)} — metoda: ${methods.join(', ') || 'unavailable'}`);
      L.push(`- Zidovi bruto: ${m(t.wallAreaGross)} | neto: ${m(t.wallAreaNet)}`);
      L.push(`- Bojanje: ${m(t.paintArea)} (trgovačko pravilo, prag ${report.conventions && report.conventions.paintFreeOpeningM2 != null ? report.conventions.paintFreeOpeningM2 : 3} m²)`);
      L.push('');
    }
  }

  // -------------------------------------------------------------- rooms
  L.push('## Sobe');
  L.push('');
  if (!(report.rooms || []).length) L.push('_Nijedna soba nije dekodirana u ovom izvoru._');
  for (const r of report.rooms || []) {
    const name = r.label || r.identifier;
    const bits = [];
    bits.push(`pod ${m(r.declaredArea != null ? r.declaredArea : r.polygonArea)}`);
    if (r.polygonArea && r.declaredArea && finite(r.polygonMinusDeclared) && Math.abs(r.polygonMinusDeclared) > 0.01) {
      bits.push(`poligon−deklarirano ${num(r.polygonMinusDeclared)} m²`);
    }
    if (r.ceilingArea) bits.push(`strop ${m(r.ceilingArea)} (${r.ceilingArea.method || 'unavailable'})`);
    L.push(`- **${esc(name)}** — ${bits.join(' · ')}`);
    if (r.ceilingArea && r.ceilingArea.value == null) L.push(`  - strop: ${m(r.ceilingArea)}`);
  }
  L.push('');

  // ----------------------------------------------------------- warnings
  L.push('## Upozorenja');
  L.push('');
  if (!warnings.length) L.push('_Nema upozorenja._');
  for (const w of warnings) L.push(`- \`${esc(w.code)}\` (${esc(w.severity || 'warning')}): ${esc(w.message || '')}`);
  L.push('');

  // --------------------------------------------------------------- gaps
  L.push('## Nedostaci (gaps)');
  L.push('');
  if (!gaps.length) L.push('_Handoff ne prijavljuje nedostatke._');
  for (const g of gaps) L.push(`- ${esc(typeof g === 'string' ? g : JSON.stringify(g))}`);
  L.push('');

  // -------------------------------------------------------- assumptions
  L.push('## Pretpostavke');
  L.push('');
  if (!assumptions.length) L.push('_Nijedna pretpostavka nije zabilježena._');
  for (const a of assumptions) L.push(`- ${esc(a)}`);
  L.push('');

  // ------------------------------------------------------------- legend
  L.push('## Legenda podrijetla');
  L.push('');
  L.push('`supplied` = preuzeto iz izvora i nije preračunato; `computed` = izračunato iz provjerene geometrije; `reconstructed` = izvedeno iz modela (npr. strop iz profila zidova); `estimated` = izvedeno iz eksplicitne pretpostavke; `unavailable` = iz ovog izvora nije moguće znati. `complete`/`partial` govori je li nešto izmjereno za sve očekivane elemente — `partial` zbroj nikad nije ukupna vrijednost zgrade.');
  L.push('');
  if(report.surfaceRegions){
    const sr=report.surfaceRegions;
    L.push('## Surface Regions (SR) — reference, ne dodatne količine','',esc(sr.quantityBasis),'');
    L.push('| SR | Podrijetlo | Izvor | Površina izvora m² (referenca) |','|---|---|---|---:|');
    for(const r of sr.regions)L.push(`| ${esc(r.id)} | ${esc(r.origin)} | ${esc(JSON.stringify(r.sourceRefs))} | ${r.areaM2==null?'n/a':r.areaM2.toFixed(10)} |`);
    for(const g of sr.groups)L.push(`\n${esc(g.id)}: ${esc(g.confirmation)}, ${g.faceCount} faces, ${esc(g.members.join(', '))}; area reference ${g.areaM2}; bend ${g.bendAngleDegrees??'unknown'} degrees. Not an additional quantity; no flattening.`);
    if(sr.groupsSource)L.push('',`Potvrda grupa: ${esc(sr.groupsSource.mode)}${sr.groupsSource.relative?` (${esc(String(sr.groupsSource.relative).replace(/^(?:[A-Za-z]:[\\/]|[\\/]).*[\\/]/, ''))})`:''}; potvrđenih grupa ${sr.groupsSource.confirmedGroupCount??0}. Bez potvrde grupa nema, a izostanak potvrde nije tvrdnja da plohe nisu ista kosina.`);
    L.push('');
  }
  return L.join('\n');
}

module.exports = { renderMarkdown };
