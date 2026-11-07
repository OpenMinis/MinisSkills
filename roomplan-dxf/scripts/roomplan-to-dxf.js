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
 * Usage:
 *   node roomplan-to-dxf.js <input.json> [outDir] [--force] [--geo]
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

const USAGE = 'Usage: node roomplan-to-dxf.js <input.json> [outDir] [--force] [--geo]';

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
  let force = false;
  let geo = false;
  for (const arg of argv) {
    if (arg === '--force') force = true;
    else if (arg === '--geo') geo = true;
    else if (arg === '-h' || arg === '--help') return { help: true };
    else if (arg.startsWith('-')) throw new Error(`Unknown option: ${arg}\n${USAGE}`);
    else positional.push(arg);
  }
  return { inputPath: positional[0], outDir: positional[1], force, geo, extra: positional.slice(2) };
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

  const inputPath = args.inputPath;
  const outDir = args.outDir || path.join(path.dirname(inputPath), 'out');
  const baseName = path.basename(inputPath).replace(/\.json$/i, '');
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

  // Story assignment: optimized sources usually carry story already; raw
  // Apple sources need per-room elevation clustering (0.8 m tolerance).
  assignStories(model);

  // DXF-export-only rotation: wall-length-weighted orthogonal circular mean,
  // rounded to the nearest 90 degrees. Stored geometry is never changed.
  const alignment = applyArchitecturalAlignment(model);

  fs.mkdirSync(outDir, { recursive: true });

  const dxfResult = buildDXF(model);
  const emitScript = path.join(__dirname, 'lib', 'dxf-emit.py');
  const emit = spawnSync('python3', [emitScript, dxfPath], {
    input: JSON.stringify(dxfResult.plan),
    encoding: 'utf8',
  });
  if (emit.error) {
    throw new Error(`could not run python3: ${emit.error.message}`);
  }
  if (emit.status !== 0) {
    console.error(emit.stderr || emit.stdout);
    throw new Error(`dxf-emit.py failed (exit ${emit.status}) — DXF not written or not AutoCAD-valid.`);
  }
  if (emit.stderr) process.stderr.write(emit.stderr);

  const manifest = buildManifest(model, dxfResult, { includeGeo: args.geo });
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

  console.log(`Format detected: ${format}`);
  console.log(`Stories: ${manifest.storyCount} (${model.storyAssignmentMethod})`);
  const angleDeg = alignment.angleRad != null ? (alignment.angleRad * 180 / Math.PI).toFixed(2) + '°' : 'n/a';
  console.log(`Architectural alignment: ${angleDeg} (${alignment.method})`);
  console.log(`DXF written: ${dxfPath} (${dxfResult.entityCount} entities, ${dxfResult.layers.length} layers)`);
  console.log(`Manifest written: ${manifestPath} (${manifest.warnings.length} warning(s))`);
}

try {
  main();
} catch (err) {
  console.error(`Error: ${err.message}`);
  process.exit(1);
}
