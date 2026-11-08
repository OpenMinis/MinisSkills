'use strict';
/**
 * Auto-discovery of a Surface Region GROUP confirmation sidecar.
 *
 * `--surface-region-groups <file>` stays the explicit, highest-priority way to
 * hand the converter a user-confirmed grouping. Without that flag the converter
 * also LOOKS for a sidecar beside the scan, using only fixed, documented names —
 * it never scans the directory for anything else and never invents a file name:
 *
 *   1. <scanDir>/<scanBase>.surface-region-groups.json   (scan-specific)
 *   2. <projectDir>/surface-region-groups.json           (project-level)
 *   3. <scanDir>/surface-region-groups.json              (e.g. data/scan.json)
 *
 * Both files are scoped by `sourceSHA256` inside the sidecar. A sidecar written
 * for a DIFFERENT capture is not evidence about this one, so a hash mismatch is
 * not applied. For an auto-discovered file that mismatch is reported as a
 * warning and conversion continues WITHOUT groups (a directory can legitimately
 * hold a sidecar for another scan); an explicit path stays a hard error, because
 * an explicit request that cannot be honoured must never pass silently.
 *
 * Nothing here writes files, contacts the network or mutates the sidecar.
 */
const fs = require('fs');
const path = require('path');

const SIDECAR_SUFFIX = '.surface-region-groups.json';
const SIDECAR_NAME = 'surface-region-groups.json';

function isFile(p) {
  try {
    return fs.statSync(p).isFile();
  } catch (err) {
    return false;
  }
}

/**
 * Every path auto-discovery is allowed to consider, most specific first.
 *
 * @param {string} inputPath raw CLI input (file or directory)
 * @param {{scanPath: string, inputWasDirectory: boolean}} resolved source-input.js result
 * @returns {string[]} absolute candidate paths, de-duplicated, order = priority
 */
function candidates(inputPath, resolved) {
  const scanPath = path.resolve(resolved.scanPath);
  const scanDir = path.dirname(scanPath);
  const base = path.basename(scanPath).replace(/\.json$/i, '');
  const projectDir = resolved.inputWasDirectory ? path.resolve(inputPath) : scanDir;
  const raw = [
    path.join(scanDir, `${base}${SIDECAR_SUFFIX}`),
    path.join(projectDir, SIDECAR_NAME),
    path.join(scanDir, SIDECAR_NAME),
  ];
  const seen = new Set();
  const out = [];
  for (const p of raw) {
    const key = path.resolve(p);
    if (!seen.has(key)) {
      seen.add(key);
      out.push(key);
    }
  }
  return out;
}

/**
 * Look for a sidecar beside the scan.
 *
 * @returns {{path: string|null, present: string[], candidates: string[]}}
 *          `path` is the single file that is used, `present` lists every
 *          candidate that existed (so ambiguity can be reported, not hidden).
 */
function discover(inputPath, resolved) {
  const all = candidates(inputPath, resolved);
  const present = all.filter(isFile);
  return { path: present.length > 0 ? present[0] : null, present, candidates: all };
}

/**
 * Read a sidecar and gate it on the source hash.
 *
 * Only the hash gate lives here: group semantics (user-confirmed confirmation,
 * >=2 known members, one room and story, no duplicate member) stay in
 * buildRegistry, so an auto-discovered file that passes the hash gate is
 * validated exactly as strictly as an explicit one.
 *
 * @returns {{override: object|null, reason: string|null, detail: string|null}}
 */
function load(filePath, sourceSHA256) {
  let text;
  try {
    text = fs.readFileSync(filePath, 'utf8');
  } catch (err) {
    return { override: null, reason: 'sidecar could not be read', detail: err.message };
  }
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    return { override: null, reason: 'sidecar is not valid JSON', detail: err.message };
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { override: null, reason: 'sidecar is not a JSON object', detail: null };
  }
  if (parsed.sourceSHA256 !== sourceSHA256) {
    return {
      override: null,
      reason: 'sidecar sourceSHA256 does not match this scan',
      detail: `sidecar ${parsed.sourceSHA256 == null ? '(missing)' : parsed.sourceSHA256} vs scan ${sourceSHA256}`,
    };
  }
  return { override: parsed, reason: null, detail: null };
}

/** Path shown in reports: relative to the project directory when it is inside it. */
function displayPath(filePath, inputPath, resolved) {
  const root = path.resolve(resolved.inputWasDirectory
    ? inputPath
    : path.dirname(path.resolve(resolved.scanPath)));
  const rel = path.relative(root, path.resolve(filePath));
  return rel && !rel.startsWith('..') ? rel : path.resolve(filePath);
}

module.exports = { candidates, discover, load, displayPath, SIDECAR_NAME, SIDECAR_SUFFIX };
