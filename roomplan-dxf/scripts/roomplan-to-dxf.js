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
 *   --author <text>    author in the title block (default: ARCHIFEST)
 *   --scale <text>     scale TEXT in the title block (default: NTS)
 *   --sheet <text>     sheet number/name (default: A-01)
 *   --no-frame         do not draw the frame, title block or north arrow
 *
 * Requires Node.js (no npm dependencies) and python3 with ezdxf.
 * The input file is opened read-only and never modified. Existing outputs
 * are refused unless --force is given.
 */
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
const { buildPlanMeta } = require('./lib/plan-meta');

const USAGE = [
  'Usage: node roomplan-to-dxf.js <input.json|dir> [outDir] [options]',
  'Options:',
  '  --force            overwrite existing outputs',
  '  --geo              include source location/compass (lat, lon in the title block)',
  '  --project <text>   title block project name',
  '  --author <text>    title block author (default: ARCHIFEST)',
  '  --scale <text>     title block scale text (default: NTS)',
  '  --sheet <text>     title block sheet number (default: A-01)',
  '  --no-frame         no frame, title block or north arrow',
].join('\n');

const VALUE_OPTIONS = {
  '--project': 'project',
  '--author': 'author',
  '--scale': 'scale',
  '--sheet': 'sheet',
};

function detectFormat(json) {
  // Optimized/Polycam: top-level "rooms" array where each room carries a
  // pre-computed "label"/"category" and usually "meshInfo".
  if (Array.isArray(json.rooms) && json.rooms.length > 0 &&
      (json.rooms[0].label !== undefined || json.rooms[0].category !== undefined || json.rooms[0].meshInfo !== undefined)) {
    return 'optimized';
  }
  // App-specific export wrapper around raw Apple RoomPlan sessions.
  if (json.captureSessions && Array.isArray(json.captureSessions)) {
    return 'raw';
  }
  // Raw Apple RoomPlan: CapturedStructure-style wrapper (multi-room/story)
  // or a single CapturedRoom (walls/floors/doors/windows/objects at top level).
  if (Array.isArray(json.rooms) || json.walls || json.surfaces || json.objects) {
    return 'raw';
  }
  throw new Error('Unrecognized RoomPlan JSON shape: expected raw CapturedRoom/CapturedStructure (optionally wrapped in captureSessions[].roomplanSessions[]) or optimized "rooms[]" with label/category/meshInfo.');
}

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function parseArgs(argv) {
  const positional = [];
  const flags = {};
  let force = false;
  let geo = false;
  let noFrame = false;
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
    else if (arg === '--no-frame') noFrame = true;
    else if (arg === '-h' || arg === '--help') return { help: true };
    else if (arg.startsWith('-')) throw new Error(`Unknown option: ${arg}\n${USAGE}`);
    else positional.push(arg);
  }
  return { inputPath: positional[0], outDir: positional[1], force, geo, noFrame, flags, extra: positional.slice(2) };
}

/** Filesystem-safe base name for a directory input. */
function safeName(name) {
  return String(name).trim().replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '') || 'scan';
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

  for (const target of [dxfPath, manifestPath]) {
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
  const alignment = applyArchitecturalAlignment(model);

  // Title-block / north-arrow metadata (annotation only — no geometry).
  const planMeta = buildPlanMeta(model, {
    project: args.flags.project || (resolved.inputWasDirectory && !(sourceMeta && sourceMeta.name)
      ? path.basename(path.resolve(args.inputPath))
      : undefined),
    author: args.flags.author,
    scale: args.flags.scale,
    sheet: args.flags.sheet,
    includeGeo: args.geo,
    noFrame: args.noFrame,
    sourceMeta,
  });

  fs.mkdirSync(outDir, { recursive: true });

  const dxfResult = buildDXF(model, { noFrame: args.noFrame, planMeta });
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
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

  console.log(`Input: ${inputPath}${resolved.inputWasDirectory ? ' (from directory)' : ''}`);
  if (sourceMeta) console.log(`Metadata: ${resolved.metaRelative} (${metaFallbackFields.length > 0 ? `fallback: ${metaFallbackFields.join(', ')}` : 'no fallback needed'})`);
  console.log(`Format detected: ${format}`);
  console.log(`Stories: ${manifest.storyCount} (${model.storyAssignmentMethod})`);
  const angleDeg = alignment.angleRad != null ? (alignment.angleRad * 180 / Math.PI).toFixed(2) + '°' : 'n/a';
  console.log(`Architectural alignment: ${angleDeg} (${alignment.method})`);
  console.log(`North arrow: ${planMeta.north.label} ${planMeta.north.degreesClockwiseFromDrawingUp != null ? `(${planMeta.north.degreesClockwiseFromDrawingUp.toFixed(1)}° clockwise from up, ${planMeta.north.described}, ${planMeta.north.basis})` : '(no bearing available)'}`);
  if (args.noFrame) console.log('Sheet frame/title block: disabled (--no-frame)');
  else console.log(`Title block: project "${planMeta.titleBlock.project}", scale "${planMeta.titleBlock.scaleText}", ${planMeta.titleBlock.date}, sheet ${planMeta.titleBlock.sheet}, ${planMeta.titleBlock.drawnBy}`);
  console.log(`DXF written: ${dxfPath} (${manifest.entityCount} entities, ${dxfResult.layers.length} layers)`);
  console.log(`Manifest written: ${manifestPath} (${manifest.warnings.length} warning(s))`);
}

try {
  main();
} catch (err) {
  console.error(`Error: ${err.message}`);
  process.exit(1);
}
