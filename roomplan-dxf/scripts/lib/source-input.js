'use strict';
/**
 * Input resolution for the converter.
 *
 * Accepts either a single JSON file (legacy behaviour, unchanged) or a
 * project DIRECTORY as produced by scan-export tools. In a directory one
 * scan is picked by fixed priority and, optionally, a `meta.json` beside it:
 *
 *   scan: optimized_roomplan.json > roomplan.json > data/scan.json > scan.json
 *   meta: meta.json > data/meta.json
 *
 * Nothing is ever written here — files are opened read-only. Ambiguous
 * directories (more than one scan candidate) are resolved by the documented
 * priority and reported, never guessed silently.
 */
const fs = require('fs');
const path = require('path');

const SCAN_CANDIDATES = ['optimized_roomplan.json', 'roomplan.json', path.join('data', 'scan.json'), 'scan.json'];
const META_CANDIDATES = ['meta.json', path.join('data', 'meta.json')];

function isDirectory(p) {
  try {
    return fs.statSync(p).isDirectory();
  } catch (err) {
    return false;
  }
}

function isFile(p) {
  try {
    return fs.statSync(p).isFile();
  } catch (err) {
    return false;
  }
}

function rel(root, p) {
  const out = path.relative(root, p);
  return out === '' ? path.basename(p) : out;
}

/**
 * Resolve the converter input.
 *
 * @param {string} inputPath file or directory
 * @returns {{scanPath: string, scanRelative: string, metaPath: string|null,
 *            metaRelative: string|null, inputWasDirectory: boolean,
 *            otherScanCandidates: string[]}}
 */
function resolveInput(inputPath) {
  if (!isDirectory(inputPath)) {
    if (!isFile(inputPath)) throw new Error(`Input not found: ${inputPath}`);
    return {
      scanPath: inputPath,
      scanRelative: path.basename(inputPath),
      metaPath: null,
      metaRelative: null,
      inputWasDirectory: false,
      otherScanCandidates: [],
    };
  }

  const found = SCAN_CANDIDATES
    .map((candidate) => path.join(inputPath, candidate))
    .filter((candidate) => isFile(candidate));

  if (found.length === 0) {
    throw new Error(
      `No RoomPlan scan found in directory ${inputPath}. Looked for: ${SCAN_CANDIDATES.join(', ')}. ` +
      'Pass the JSON file itself if it has another name.'
    );
  }

  const metaFound = META_CANDIDATES
    .map((candidate) => path.join(inputPath, candidate))
    .filter((candidate) => isFile(candidate));

  return {
    scanPath: found[0],
    scanRelative: rel(inputPath, found[0]),
    metaPath: metaFound.length > 0 ? metaFound[0] : null,
    metaRelative: metaFound.length > 0 ? rel(inputPath, metaFound[0]) : null,
    inputWasDirectory: true,
    otherScanCandidates: found.slice(1).map((candidate) => rel(inputPath, candidate)),
  };
}

/** Seconds between 1970-01-01 and 2001-01-01 (Core Data / Apple reference date). */
const APPLE_EPOCH_OFFSET_SECONDS = 978307200;

/**
 * Normalise a `createdAt` value to an ISO calendar date (YYYY-MM-DD).
 *
 * Observed exports use two conventions and neither is labelled:
 *   - plain Unix epoch seconds (>= 1e9),
 *   - Apple/Core Data reference-date seconds since 2001-01-01 (< 1e9).
 * Anything unparseable returns null; no date is invented.
 */
function normaliseCreatedAt(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return null;
  const unixSeconds = value >= 1e9 ? value : value + APPLE_EPOCH_OFFSET_SECONDS;
  const ms = unixSeconds * 1000;
  if (!Number.isFinite(ms)) return null;
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return null;
  // Reject absurd values rather than printing a nonsense date in a title block.
  if (date.getUTCFullYear() < 1990 || date.getUTCFullYear() > 2200) return null;
  return {
    iso: date.toISOString().slice(0, 10),
    convention: value >= 1e9 ? 'unix-epoch-seconds' : 'apple-reference-date-seconds',
  };
}

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/**
 * Read an optional `meta.json` (Polycam-style project metadata).
 * Only the documented fields are read; everything else is ignored.
 *
 * @param {string|null} metaPath
 * @returns {object|null}
 */
function readMeta(metaPath) {
  if (!metaPath) return null;
  const buf = fs.readFileSync(metaPath);
  let root;
  try {
    root = JSON.parse(buf.toString('utf8'));
  } catch (err) {
    throw new Error(`meta.json is not valid JSON: ${metaPath} — ${err.message}`);
  }
  if (!root || typeof root !== 'object' || Array.isArray(root)) {
    throw new Error(`meta.json must be a JSON object: ${metaPath}`);
  }
  const validate = require('./validate');
  for (const [key,min,max] of [['latitude',-90,90],['longitude',-180,180],['headingDegrees',-360,360]]) if(root[key]!=null) validate.number(root[key],`meta.${key}`,min,max);
  const createdAt = normaliseCreatedAt(root.createdAt);
  return {
    path: metaPath,
    filename: path.basename(metaPath),
    name: typeof root.name === 'string' && root.name.trim() !== '' ? root.name.trim() : null,
    latitude: finiteNumber(root.latitude),
    longitude: finiteNumber(root.longitude),
    headingDegrees: finiteNumber(root.headingDegrees),
    floorAreaSquareMetres: finiteNumber(root.floorAreaSquareMetres),
    wallAreaSquareMetres: finiteNumber(root.wallAreaSquareMetres),
    roomCount: Number.isInteger(root.roomCount) ? root.roomCount : null,
    theId: typeof root.id === 'string' ? root.id : null,
    createdAtRaw: finiteNumber(root.createdAt),
    createdAt,
  };
}

/**
 * Fill scan metadata from `meta.json` ONLY where the scan itself carries no
 * value. Existing scan values always win — meta.json is a fallback, never an
 * override, so the drawing is never georeferenced by assumption.
 *
 * @param {object} model decoded capture model
 * @param {object|null} meta readMeta() result
 * @returns {string[]} list of field names taken from meta.json
 */
function applyMetaFallback(model, meta) {
  const fallbackFields = [];
  if (!meta) return fallbackFields;
  if (!model.meta) model.meta = {};

  if (model.meta.latitude == null && model.meta.longitude == null && meta.latitude != null && meta.longitude != null) {
    model.meta.latitude = meta.latitude;
    model.meta.longitude = meta.longitude;
    model.meta.altitude = null;
    fallbackFields.push('latitude', 'longitude');
  }
  if (model.meta.orientationDegrees == null && meta.headingDegrees != null) {
    model.meta.orientationDegrees = meta.headingDegrees;
    // meta.json carries no confidence: it is a project-level heading, not a
    // per-scan compass measurement, so no confidence may be claimed for it.
    model.meta.orientationConfidence = null;
    model.meta.orientationUncertaintyDegrees = null;
    model.meta.orientationSource = 'meta.json';
    fallbackFields.push('orientationDegrees');
  }
  return fallbackFields;
}

module.exports = {
  SCAN_CANDIDATES,
  META_CANDIDATES,
  resolveInput,
  readMeta,
  applyMetaFallback,
  normaliseCreatedAt,
  isDirectory,
};
