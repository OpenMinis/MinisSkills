#!/usr/bin/env node
'use strict';
/**
 * roomplan-to-dxf.js — command-line entry point.
 *
 * Converts Apple RoomPlan JSON (raw CapturedRoom / CapturedStructure, or a
 * wrapper carrying captureSessions[].roomplanSessions[]) or an
 * Optimized/Polycam-style export (format_version: 1) into:
 *
 *   <outDir>/<name>.dxf            AutoCAD R2018 (AC1032) drawing, metres
 *   <outDir>/<name>.roomplan.json  diagnostics manifest (always lossy:true)
 *
 * The input may be a single JSON file or a project DIRECTORY. In a directory
 * one scan is chosen by priority — optimized_roomplan.json, roomplan.json,
 * data/scan.json, scan.json — and an optional meta.json / data/meta.json
 * supplies the project name, location, heading and scan date.
 *
 * Usage:
 *   node roomplan-to-dxf.js <input.json|dir> [outDir] [options]
 *
 * Options:
 *   --force            overwrite existing outputs
 *   --geo              copy source location/compass into the manifest and
 *                      print "lat, lon" in the title block
 *   --project <text>   project name in the title block
 *   --author <text>    author in the title block (default: roomplan-dxf)
 *   --scale <text>     scale TEXT in the title block (default: NTS)
 *   --sheet <text>     sheet number/name (default: A-01)
 *   --no-frame         do not draw the frame, title block or north arrow
 *
 * Requires Node.js (no npm dependencies) and python3 with ezdxf.
 * The input file is opened read-only and never modified. Existing outputs
 * are refused unless --force is given.
 */
const { buildReport, quantitiesCSV } = require('./lib/quantities');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const { decode: decodeRawFile } = require('./lib/decode-raw');
const { decode: decodeOptimizedFile } = require('./lib/decode-optimized');
const { assignStories } = require('./lib/story');
const { applyArchitecturalAlignment } = require('./lib/align');
const { buildDXF } = require('./lib/dxf-writer');
const { buildManifest } = require('./lib/manifest');
const { resolveInput, readMeta, applyMetaFallback } = require('./lib/source-input');
const groupSidecar = require('./lib/group-sidecar');
const { buildPlanMeta, storyLabel } = require('./lib/plan-meta');
const {detectDialect} = require('./lib/dialect');
const {buildCapture} = require('./lib/capture-export');
const { renderMarkdown } = require('./lib/out-md');
const { buildUsda } = require('./lib/usda-export');
const { writeUsdz } = require('./lib/usdz-writer');

const USAGE = [
  'Usage: node roomplan-to-dxf.js <input.json|dir> [outDir] [options]',
  'Options:',
  '  --force            overwrite existing outputs',
  '  --model            also write source-space <name>.capture.json (geo redacted unless --geo)',
  '  --ceilings         dashed orange ceiling plane, ridge/fall line, method and',
  '                     floor-relative height for every room (DEFAULT ON)',
  '  --no-ceilings      disable DXF ceiling annotations only; later toggle wins',
  '  --usdz-ceilings    opt in to USDZ ceiling meshes (default OFF)',
  '  --no-usdz-ceilings disable USDZ ceiling meshes; independent of DXF',
  '  --report           also write <name>.report.json (totals, elements, statistics, handoff) and <name>.quantities.csv',
  '  --md               also write <name>.md, a Markdown summary of report-v1 (implies --report)',
  '  --usdz             also write <name>.usdz, an AR Quick Look model (RoomPlan geometry in metres)',
  '  --geo              include source location/compass (lat, lon in the title block)',
  '  --project <text>   title block project name',
  '  --author <text>    title block author (default: roomplan-dxf)',
  '  --scale <text>     title block scale text (default: NTS)',
  '  --sheet <text>     title block sheet number (default: A-01)',
  '  --place <text>     title block location text (free text, highest priority)',
  '  --place-lookup     reverse-geocode the scan coordinates once via the local',
  '                     Apple `apple-location geocode` helper (opt-in; falls back',
  '                     to coordinates or "location withheld")',
  '  --north-flip       north = (alignmentOffset - heading) mod 360 (default)',
  '  --no-north-flip    legacy north = 180 - heading + alignmentOffset',
  '  --no-frame         no frame, title block or north arrow (stories not separated)',
  '  --surface-region-groups <file>  user-confirmed Surface Region groups (JSON,',
  '                     source-SHA256 scoped). Without this flag the converter',
  '                     auto-discovers <scan>.surface-region-groups.json or',
  '                     surface-region-groups.json beside the scan; a sidecar for',
  '                     a different capture is ignored with a warning',
].join('\n');

const VALUE_OPTIONS = {
  '--project': 'project',
  '--author': 'author',
  '--scale': 'scale',
  '--sheet': 'sheet',
  '--place': 'place',
  '--surface-region-groups': 'surfaceRegionGroups',
};

function detectFormat(json) { return detectDialect(json).kind; }

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function parseArgs(argv) {
  const positional = [];
  const flags = {};
  let force = false;
  let geo = false;
  let exportModel = false;
  let noFrame = false;
  // North-flip is ON by default for every dialect: the unflipped formula drew
  // the arrow 180 deg wrong on real drawings (an anonymized regression example and an anonymized reference example).
  // null = not passed explicitly, so the default applies and nothing is echoed.
  let northFlip = null;
  let placeLookup = false;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    let key = arg;
    let inlineValue = null;
    const eq = arg.indexOf('=');
    if (arg.startsWith('--') && eq !== -1) {
      key = arg.slice(0, eq);
      inlineValue = arg.slice(eq + 1);
    }
    if (VALUE_OPTIONS[key]) {
      let value = inlineValue;
      if (value == null) {
        value = argv[i + 1];
        if (value == null || value.startsWith('--')) {
          throw new Error(`Option ${key} needs a value\n${USAGE}`);
        }
        i += 1;
      }
      if (value.trim() === '') throw new Error(`Option ${key} needs a non-empty value`);
      flags[VALUE_OPTIONS[key]] = value;
    } else if (arg === '--force') force = true;
    else if (arg === '--geo') geo = true;
    else if (arg === '--model') exportModel = true;
    else if (arg === '--report') flags.report = true;
    else if (arg === '--md') flags.md = true;
    else if (arg === '--usdz') flags.usdz = true;
    else if (arg === '--usdz-ceilings') flags.usdzCeilings = true;
    else if (arg === '--no-usdz-ceilings') flags.usdzCeilings = false;
    else if (arg === '--ceilings') flags.ceilings = true;
    else if (arg === '--no-ceilings') flags.ceilings = false;
    else if (arg === '--no-frame') noFrame = true;
    else if (arg === '--place-lookup') placeLookup = true;
    else if (arg === '--no-place-lookup') placeLookup = false;
    else if (arg === '--north-flip') northFlip = true;
    else if (arg === '--no-north-flip') northFlip = false;
    else if (arg === '-h' || arg === '--help') return { help: true };
    else if (arg.startsWith('-')) throw new Error(`Unknown option: ${arg}\n${USAGE}`);
    else positional.push(arg);
  }
  return { inputPath: positional[0], outDir: positional[1], force, geo, exportModel, noFrame, northFlip,
           placeLookup, flags, extra: positional.slice(2) };
}

/** Filesystem-safe base name for a directory input. */
function safeName(name) {
  return String(name).trim().replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '') || 'scan';
}

/**
 * One-shot reverse geocode of the scan coordinates through the LOCAL Apple
 * helper `apple-location geocode` (CoreLocation/MapKit on the device).
 *
 *   - never called unless the operator passed --place-lookup;
 *   - never called without coordinates;
 *   - a missing helper or a failed lookup is reported as a warning and the
 *     title block falls back to coordinates (with --geo) or "location
 *     withheld" — it can never abort a conversion;
 *   - no third-party geocoding service is ever contacted.
 */
function lookupPlace(meta) {
  const lat = meta && meta.latitude;
  const lon = meta && meta.longitude;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return { status: 'no-coordinates' };
  }
  const probe = spawnSync('sh', ['-c', 'command -v apple-location'], { encoding: 'utf8' });
  if (probe.status !== 0 || !String(probe.stdout || '').trim()) {
    return { status: 'unavailable' };
  }
  const started = Date.now();
  const res = spawnSync('apple-location',
    ['geocode', '--lat', String(lat), '--lng', String(lon), '--compact'],
    { encoding: 'utf8', timeout: 20000 });
  if (res.error || res.status !== 0) {
    return { status: 'failed', detail: String(res.stderr || res.error || 'apple-location exited non-zero').trim().slice(0, 200) };
  }
  let parsed = null;
  try {
    const line = String(res.stdout || '').trim().split('\n').filter((l) => l.trim().startsWith('{')).pop();
    parsed = JSON.parse(line);
  } catch (err) {
    return { status: 'failed', detail: 'could not parse apple-location JSON output' };
  }
  const address = parsed && parsed.data && Array.isArray(parsed.data.addresses)
    ? parsed.data.addresses[0] : null;
  if (!address) return { status: 'failed', detail: 'apple-location returned no address' };
  const head = address.name || address.street || null;
  const locality = address.locality || null;
  const text = [head, locality].filter(Boolean).join(', ');
  if (!text) return { status: 'failed', detail: 'address had no name/street/locality' };
  return { status: 'ok', text, source: 'apple-location',
           fields: { name: address.name || null, street: address.street || null,
                     locality: address.locality || null,
                     administrativeArea: address.administrative_area || null,
                     country: address.country || null },
           elapsedMs: Date.now() - started };
}

function placeLookupWarnings(result) {
  if (!result) return [];
  if (result.status === 'ok') {
    return [{
      code: 'roomplan.place-lookup-applied',
      message: 'The "Lokacija" cell was filled by reverse geocoding the scan coordinates once with the local Apple `apple-location geocode` helper. It is a best-effort locality, not a verified address, and no non-Apple service was contacted.',
    }];
  }
  if (result.status === 'unavailable') {
    return [{
      code: 'roomplan.place-lookup-unavailable',
      message: '--place-lookup was requested but the `apple-location` helper is not available on this system; the location cell fell back to coordinates (--geo) or "location withheld".',
    }];
  }
  if (result.status === 'no-coordinates') {
    return [{
      code: 'roomplan.place-lookup-no-coordinates',
      message: '--place-lookup was requested but the scan/meta carry no latitude/longitude, so no lookup was attempted and the location cell reads "location withheld".',
    }];
  }
  return [{
    code: 'roomplan.place-lookup-failed',
    message: `--place-lookup failed (${result.detail || 'unknown error'}); the location cell fell back to coordinates (--geo) or "location withheld". The conversion itself is unaffected.`,
  }];
}

function runEmit(emitScript, dxfPath, plan) {
  const emit = spawnSync('python3', [emitScript, dxfPath], {
    input: JSON.stringify(plan),
    encoding: 'utf8',
  });
  if (emit.error) throw new Error(`could not run python3: ${emit.error.message}`);
  if (emit.status !== 0) {
    console.error(emit.stderr || emit.stdout);
    throw new Error(`dxf-emit.py failed (exit ${emit.status}) — DXF not written or not AutoCAD-valid.`);
  }
  if (emit.stderr) process.stderr.write(emit.stderr);
  // One-line JSON summary: final entity count including sheet furniture.
  const line = String(emit.stdout || '').trim().split('\n').filter((l) => l.trim().startsWith('{')).pop();
  if (!line) return null;
  try {
    return JSON.parse(line);
  } catch (err) {
    return null;
  }
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
  if (args.help) {
    console.log(USAGE);
    return;
  }
  if (!args.inputPath) {
    console.error(USAGE);
    process.exit(1);
  }
  if (args.extra && args.extra.length > 0) {
    console.error(`Unexpected argument: ${args.extra[0]}\n${USAGE}`);
    process.exit(1);
  }

  const resolved = resolveInput(args.inputPath);
  const inputPath = resolved.scanPath;
  const outDir = args.outDir || path.join(resolved.inputWasDirectory ? path.resolve(args.inputPath) : path.dirname(inputPath), 'out');
  const baseName = resolved.inputWasDirectory
    ? safeName(path.basename(path.resolve(args.inputPath)))
    : path.basename(inputPath).replace(/\.json$/i, '');
  const dxfPath = path.join(outDir, `${baseName}.dxf`);
  const manifestPath = path.join(outDir, `${baseName}.roomplan.json`);

  const capturePath = path.join(outDir, `${baseName}.capture.json`);
  const reportPath = path.join(outDir, `${baseName}.report.json`);
  const csvPath = path.join(outDir, `${baseName}.quantities.csv`);
  const mdPath = path.join(outDir, `${baseName}.md`);
  // --usdz is independent of --model/--report/--md: it only needs the decoded model.
  const usdzPath = path.join(outDir, `${baseName}.usdz`);
  const targets = [dxfPath, manifestPath, ...(args.exportModel ? [capturePath] : []), ...(args.flags.usdz ? [usdzPath] : []), ...(args.flags.report || args.flags.md ? [reportPath, ...(args.flags.report ? [csvPath] : []), ...(args.flags.md ? [mdPath] : [])] : [])];
  const protectedFiles = [inputPath, resolved.metaPath].filter(Boolean).map(p => fs.realpathSync(p));
  for (const target of targets) {
    if (fs.existsSync(target) && protectedFiles.some(p => {
      const a=fs.statSync(p), b=fs.statSync(target);
      return fs.realpathSync(target)===p || (a.dev===b.dev && a.ino===b.ino);
    })) throw new Error('Refusing output alias of source input/metadata, even with --force');
    if (fs.existsSync(target) && !args.force) {
      console.error(`Refusing to overwrite existing file: ${target}\nUse --force or choose another output directory.`);
      process.exit(2);
    }
  }

  const raw = fs.readFileSync(inputPath);
  const json = JSON.parse(raw.toString('utf8'));
  const format = detectFormat(json);

  const model = format === 'raw' ? decodeRawFile(raw, path.basename(inputPath)) : decodeOptimizedFile(raw, path.basename(inputPath));
  model.originalFilename = path.basename(inputPath);
  model.sourceSHA256 = sha256(raw);

  // Optional meta.json: fallback only, never an override of scan values.
  const sourceMeta = readMeta(resolved.metaPath);
  const metaFallbackFields = applyMetaFallback(model, sourceMeta);
  if (sourceMeta) model.sourceMeta = sourceMeta;

  // Story assignment: optimized sources usually carry story already; raw
  // Apple sources need per-room elevation clustering (0.8 m tolerance).
  assignStories(model);

  // DXF-export-only rotation: wall-length-weighted orthogonal circular mean,
  // rounded to the nearest 90 degrees. Stored geometry is never changed.
  const wantReport = args.flags.report === true || args.flags.md === true;
  const quantityReport = wantReport ? buildReport(model, json) : null;
  if (quantityReport && sourceMeta && Number.isFinite(sourceMeta.floorAreaSquareMetres)) {
    quantityReport.sourceReferences.floorAreaSquareMetres = sourceMeta.floorAreaSquareMetres;
  }
  const alignment = applyArchitecturalAlignment(model);
  const normalizedCapture = args.exportModel ? buildCapture(model, json, {includeGeo:args.geo, metaFallbackFields, metaBytes:resolved.metaPath ? fs.readFileSync(resolved.metaPath) : null}) : null;

  // Optional one-shot reverse geocode (opt-in, local Apple helper only).
  let placeLookup = null;
  let placeText = args.flags.place;
  if (args.placeLookup) {
    placeLookup = lookupPlace(model.meta || {});
    if (!placeText && placeLookup.status === 'ok') placeText = placeLookup.text;
  }

  // Title-block / north-arrow metadata (annotation only — no geometry).
  const planMeta = buildPlanMeta(model, {
    project: args.flags.project || (resolved.inputWasDirectory && !(sourceMeta && sourceMeta.name)
      ? path.basename(path.resolve(args.inputPath))
      : undefined),
    author: args.flags.author,
    scale: args.flags.scale,
    sheet: args.flags.sheet,
    place: placeText,
    placeSource: args.flags.place ? 'place' : (placeText ? 'place-lookup' : undefined),
    includeGeo: args.geo,
    noFrame: args.noFrame,
    northFlip: args.northFlip,
    sourceMeta,
  });

  fs.mkdirSync(outDir, { recursive: true });

  if (resolved.metaSkipped) planMeta.warnings.push({
    code: 'roomplan.meta-not-attributed',
    message: `meta.json at ${resolved.metaSkipped.path} was not used: ${resolved.metaSkipped.reason}. No orientation was invented from it.`,
  });

  planMeta.placeLookup = placeLookup;
  for (const w of placeLookupWarnings(placeLookup)) planMeta.warnings.push(w);

  // Surface Region GROUPS: explicit path wins. Without it a sidecar beside the
  // scan is auto-discovered by fixed name; a sidecar for a DIFFERENT capture is
  // ignored with a warning (never applied, never silently dropped).
  let srOverride = null;
  const srSource = { mode: 'none', path: null, relative: null };
  if (args.flags.surfaceRegionGroups) {
    const srFile = path.resolve(args.flags.surfaceRegionGroups);
    srOverride = JSON.parse(fs.readFileSync(srFile, 'utf8'));
    Object.assign(srSource, { mode: 'explicit', path: groupSidecar.displayPath(srFile, args.inputPath, resolved), relative: groupSidecar.displayPath(srFile, args.inputPath, resolved) });
  } else {
    const found = groupSidecar.discover(args.inputPath, resolved);
    if (found.present.length > 1) planMeta.warnings.push({
      code: 'roomplan.surface-region-groups-sidecar-ambiguous',
      message: `${found.present.length} Surface Region group sidecars sit beside this scan (${found.present.map((p) => groupSidecar.displayPath(p, args.inputPath, resolved)).join(', ')}); the most specific one was used: ${groupSidecar.displayPath(found.path, args.inputPath, resolved)}.`,
    });
    if (found.path) {
      const loaded = groupSidecar.load(found.path, model.sourceSHA256);
      if (loaded.override) {
        srOverride = loaded.override;
        Object.assign(srSource, { mode: 'auto-discovered', path: groupSidecar.displayPath(found.path, args.inputPath, resolved), relative: groupSidecar.displayPath(found.path, args.inputPath, resolved) });
      } else {
        planMeta.warnings.push({
          code: 'roomplan.surface-region-groups-sidecar-ignored',
          message: `Auto-discovered Surface Region group sidecar ${groupSidecar.displayPath(found.path, args.inputPath, resolved)} was not applied: ${loaded.reason}${loaded.detail ? ` (${loaded.detail})` : ''}. No group is confirmed for this scan; groups stay empty rather than borrowing a confirmation for other source geometry.`,
        });
      }
    }
  }
  const dxfResult = buildDXF(model, { noFrame: args.noFrame, planMeta, ceilings:args.flags.ceilings!==false, surfaceRegionGroups:srOverride, sourceSHA256:model.sourceSHA256 });
  const surfaceRegions = require('./lib/surface-regions').buildRegistry(dxfResult.ceilingDiagnostics.records || [], model.sourceSHA256, srOverride);
  // Provenance of the grouping: which file confirmed it, or that none did.
  surfaceRegions.groupsSource = Object.assign({}, srSource, {
    sourceSHA256: model.sourceSHA256,
    confirmedGroupCount: surfaceRegions.groups.length,
  });
  dxfResult.ceilingDiagnostics.surfaceRegions = surfaceRegions;
  model.surfaceRegions = surfaceRegions; // same non-additive registry for optional USDZ metadata
  if(quantityReport){quantityReport.ceilingDiagnostics=dxfResult.ceilingDiagnostics;quantityReport.surfaceRegions=surfaceRegions;}
  for(const warning of dxfResult.ceilingDiagnostics.warnings||[])planMeta.warnings.push(warning);

  // USDZ (optional, independent of every other output). It is built here so
  // that any geometry it had to skip is recorded in the manifest warnings.
  let usdzResult = null;
  let usda = null;
  if (args.flags.usdz) {
    usda = buildUsda(model, {
      ceilings: args.flags.usdzCeilings === true,
      thickness: 0.16, // metres, Apple's assumed wall thickness
      doc: `${planMeta.titleBlock.project || baseName} - RoomPlan capture, metres, Y up (textures and UVs not exported)`,
    });
    for (const w of usda.warnings || []) planMeta.warnings.push({ code: w.code, message: w.message, severity: 'warning' });
  }

  // Story labels for the title block's "Kat" row and for the per-story sheets.
  // The single-sheet case must know its floor BEFORE the sheet is emitted, and
  // plan.meta is the same object as planMeta.dxfMeta, so patching it here is
  // enough for dxf-emit.py.
  const planStories = dxfResult.plan.stories || [];
  for (const s of planStories) s.label = storyLabel(s.story);
  if (planStories.length === 1) {
    planMeta.titleBlock.story = planStories[0].story;
    planMeta.titleBlock.storyLabel = planStories[0].label;
    planMeta.dxfMeta.story = planStories[0].story;
    planMeta.dxfMeta.storyLabel = planStories[0].label;
  }
  planMeta.dxfMeta.storyCount = planStories.length;
  planMeta.titleBlock.storyCount = planStories.length;

  const emitScript = path.join(__dirname, 'lib', 'dxf-emit.py');
  const emitted = runEmit(emitScript, dxfPath, dxfResult.plan);

  const manifest = buildManifest(model, dxfResult, {
    includeGeo: args.geo,
    planMeta: args.noFrame ? null : planMeta,
    sourceMeta,
    metaRelative: resolved.metaRelative,
    metaFallbackFields,
    otherScanCandidates: resolved.otherScanCandidates,
    scanRelative: resolved.scanRelative,
    inputWasDirectory: resolved.inputWasDirectory,
    emitted,
  });
  manifest.ceilingDiagnostics=dxfResult.ceilingDiagnostics;
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  if (quantityReport) {
    // The manifest owns the warnings collected during decoding/conversion; the
    // report-v1 contract requires them too. Merge once, with severity, so a
    // consumer never reads "no warnings" while the manifest lists eight.
    const seen = new Set((quantityReport.warnings || []).map((w) => `${w.code}|${w.message}|${w.roomIdentifier ?? ''}`));
    for (const w of manifest.warnings || []) {
      // Ceiling diagnostics carry `reason`, unlike decoder warnings. Preserve
      // their context and normalize the message before deduplicating.
      const message = w.message || w.reason || w.code;
      const key = `${w.code}|${message}|${w.roomIdentifier ?? ''}`;
      if (seen.has(key)) continue;
      seen.add(key);
      (quantityReport.warnings = quantityReport.warnings || []).push({
        ...w,
        code: w.code,
        message,
        severity: w.severity || 'warning',
      });
    }
    fs.writeFileSync(reportPath, JSON.stringify(quantityReport, null, 2) + '\n');
    if (args.flags.report === true) fs.writeFileSync(csvPath, quantitiesCSV(quantityReport));
    console.log(`Quantities report written: ${reportPath}${args.flags.report ? `; CSV: ${csvPath}` : ''}`);
    if (args.flags.md) {
      fs.writeFileSync(mdPath, renderMarkdown(quantityReport, { project: planMeta.titleBlock.project, date: planMeta.titleBlock.date }));
      console.log(`Markdown summary written: ${mdPath}`);
    }
  }
  if (normalizedCapture) fs.writeFileSync(capturePath, JSON.stringify(normalizedCapture, null, 2));
  if (usda) {
    usdzResult = writeUsdz(usdzPath, Object.entries(usda.files).map(([name, data]) => ({ name, data })));
  }

  console.log(`Input: ${inputPath}${resolved.inputWasDirectory ? ' (from directory)' : ''}`);
  if (sourceMeta) console.log(`Metadata: ${resolved.metaRelative} (${metaFallbackFields.length > 0 ? `fallback: ${metaFallbackFields.join(', ')}` : 'no fallback needed'})`);
  console.log(`Format detected: ${format} (${model.dialect})`);
  if (normalizedCapture) console.log(`Normalized model written: ${capturePath}`);
  console.log(`Stories: ${manifest.storyCount} (${model.storyAssignmentMethod})`);
  const angleDeg = alignment.angleRad != null ? (alignment.angleRad * 180 / Math.PI).toFixed(2) + '°' : 'n/a';
  console.log(`Architectural alignment: ${angleDeg} (${alignment.method})`);
  console.log(`North arrow: ${planMeta.north.label} ${planMeta.north.degreesClockwiseFromDrawingUp != null ? `(${planMeta.north.degreesClockwiseFromDrawingUp.toFixed(1)}° clockwise from up, ${planMeta.north.described}, ${planMeta.north.basis})` : '(no bearing in source: empty rose, no needle)'}`);
  if (planMeta.north.sourceHeadingDegrees != null) {
    console.log(`North formula: ${planMeta.north.formula} (heading ${planMeta.north.sourceHeadingDegrees.toFixed(2)}°, alignment offset ${planMeta.north.alignmentBearingOffsetDegrees}°)${args.northFlip === false ? ' [--no-north-flip]' : args.northFlip === true ? ' [--north-flip]' : ''}`);
  }
  if (args.noFrame) console.log('Sheet frame/title block: disabled (--no-frame)');
  else console.log(`Title block: project "${planMeta.titleBlock.project}", scale "${planMeta.titleBlock.scaleText}", ${planMeta.titleBlock.date}, sheet ${planMeta.titleBlock.sheet}, ${planMeta.titleBlock.drawnBy}`);
  if (placeLookup) {
    console.log(`Place lookup: ${placeLookup.status}${placeLookup.status === 'ok' ? ` -> "${placeLookup.text}"` : ''}${placeLookup.detail ? ` (${placeLookup.detail})` : ''}`);
  }
  if (!args.noFrame && planStories.length > 1) {
    console.log(`Sheets: ${planStories.length} (one frame per story, side by side): ${planStories.map((s) => `${s.story}=${s.label}`).join(', ')}`);
  } else if (!args.noFrame && planStories.length === 1) {
    console.log(`Sheet: 1 (Kat: ${planStories[0].label})`);
  }
  console.log(`DXF written: ${dxfPath} (${manifest.entityCount} entities, ${dxfResult.layers.length} layers)`);
  console.log(`Manifest written: ${manifestPath} (${manifest.warnings.length} warning(s))`);
  if (usdzResult) console.log(`USDZ written: ${usdzPath} (${usda.primCount} prims)`);
}

try {
  main();
} catch (err) {
  console.error(`Error: ${err.message}`);
  process.exit(1);
}
