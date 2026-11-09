'use strict';
/**
 * Builds the sheet furniture metadata (title block + north arrow + per-story
 * labels) that dxf-emit.py draws AROUND the plan.
 *
 * Rules that matter:
 *   - the title block adds no geometry and never moves room geometry;
 *   - the scale is TEXT ONLY ("NTS" by default). Nothing here claims a
 *     printed sheet scale, because the source scan has no known plot scale;
 *   - coordinates are only printed when --geo is passed, otherwise the
 *     location cell reads "location withheld". --place <text> always wins:
 *     it is the only way to put a human place name on the sheet, because
 *     RoomPlan/Polycam metadata carries no place name and Apple Maps offers
 *     no reverse geocoding (search/route/eta only). This converter never
 *     sends coordinates to any web service on its own;
 *   - north is drawn whenever a heading exists, including a project-level
 *     `headingDegrees` from meta.json. That case is flagged approximate in
 *     the manifest (a project heading is a usable orientation, not a
 *     surveyed bearing). "N?" is drawn ONLY when no heading exists at all;
 *   - orientation is not location: the north arrow uses the heading whether
 *     or not --geo is passed. --geo governs coordinates only.
 */

const DEFAULT_AUTHOR = 'roomplan-dxf';
const DEFAULT_SCALE_TEXT = 'NTS';
const DEFAULT_SHEET = 'A-01';
const NORTH_CONFIDENCE_THRESHOLD = 0.8;

/** Nominal glyph width as a fraction of text height — the single width
 * estimator shared by the title-block fitter (dxf-emit.py) and the test. */
const CHAR_WIDTH_RATIO = 0.6;

function todayISO() {
  const now = new Date();
  const yyyy = String(now.getFullYear()).padStart(4, '0');
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * Bearing offset (degrees, clockwise from drawing up) introduced by the
 * architectural-alignment matrix when the model frame is projected onto the
 * sheet. A model-frame bearing b appears on the sheet as b + delta.
 *
 * Derivation: project() maps a world point (x, y, z) to the sheet point
 * (x, -z), so a world direction's sheet bearing is atan2(sx, sy). Applying
 * the alignment matrix to the model X axis gives column 0, whose sheet
 * bearing is atan2(m[0], -m[2]); the X axis itself is at 90 deg, hence
 * delta = atan2(m[0], -m[2]) - 90. For a rotation about +Y by `a` this is
 * exactly -a, which is what the wall geometry shows in practice.
 */
function alignmentBearingOffset(alignment) {
  const m = alignment && alignment.matrix;
  if (!Array.isArray(m) || m.length !== 16 || !m.every(Number.isFinite)) return 0;
  const delta = (Math.atan2(m[0], -m[2]) * 180) / Math.PI - 90;
  if (!Number.isFinite(delta)) return 0;
  return ((delta + 180) % 360 + 360) % 360 - 180;
}

function normaliseDegrees(value) {
  return ((value % 360) + 360) % 360;
}

/**
 * Story (floor) label used in the title block's "Kat" row.
 *   0 -> Prizemlje, 1 -> "1. kat", 2 -> "2. kat", negative -> Podrum.
 * More than one basement level keeps its depth: "Podrum (2)".
 */
function storyLabel(story) {
  const n = Number.isFinite(story) ? Math.trunc(story) : 0;
  if (n === 0) return 'Prizemlje';
  if (n > 0) return `${n}. kat`;
  return n === -1 ? 'Podrum' : `Podrum (${-n})`;
}

function formatCoordinate(value) {
  // ~11 m at the equator for 4 decimals: short enough for a title block,
  // precise enough to identify the building, not a substitute for a survey.
  return value.toFixed(4);
}

/**
 * @param {object} model decoded model (with meta + optional sourceMeta)
 * @param {object} opts { project, author, scale, sheet, place, includeGeo,
 *   noFrame, sourceMeta, northFlip, story }
 * @returns {{titleBlock: object, north: object, warnings: object[]}}
 */
function buildPlanMeta(model, opts) {
  const options = opts || {};
  const sourceMeta = options.sourceMeta || null;
  const meta = model.meta || {};
  const warnings = [];

  const project = (options.project && String(options.project).trim()) ||
    (sourceMeta && sourceMeta.name) ||
    String(model.originalFilename || 'Untitled scan').replace(/\.json$/i, '');
  const author = (options.author && String(options.author).trim()) || DEFAULT_AUTHOR;
  const scaleText = (options.scale && String(options.scale).trim()) || DEFAULT_SCALE_TEXT;
  const sheet = (options.sheet && String(options.sheet).trim()) || DEFAULT_SHEET;
  const date = (sourceMeta && sourceMeta.createdAt && sourceMeta.createdAt.iso) || todayISO();

  const hasGeo = meta.latitude != null && meta.longitude != null;
  const place = options.place != null ? String(options.place).trim() : '';

  // Location cell resolution order: explicit --place > --geo coordinates >
  // withheld. There is no automatic reverse geocoding anywhere in this tool.
  let locationText;
  let locationSource;
  if (place) {
    locationText = place;
    locationSource = options.placeSource || 'place';
  } else if (options.includeGeo && hasGeo) {
    locationText = `${formatCoordinate(meta.latitude)}, ${formatCoordinate(meta.longitude)}`;
    locationSource = 'geo';
  } else {
    locationText = 'location withheld';
    locationSource = 'withheld';
  }

  if (options.includeGeo && !hasGeo && !place) {
    warnings.push({
      code: 'roomplan.geo-requested-without-coordinates',
      message: '--geo was requested but the scan/meta carry no latitude/longitude, so the location cell reads "location withheld".',
    });
  }

  // ---- north -------------------------------------------------------------
  const orientationSource = meta.orientationSource || (meta.orientationDegrees != null ? 'scan' : 'none');
  const confidence = meta.orientationConfidence != null ? meta.orientationConfidence : null;
  const uncertainty = meta.orientationUncertaintyDegrees != null ? meta.orientationUncertaintyDegrees : null;
  const heading = meta.orientationDegrees != null && Number.isFinite(meta.orientationDegrees)
    ? normaliseDegrees(meta.orientationDegrees)
    : null;
  // The alignment matrix rotates the model frame onto the sheet; a model
  // bearing b lands on the sheet at b + bearingOffset. Without this the arrow
  // would be off by the alignment angle (e.g. 8 deg on a rotated scan).
  const bearingOffset = alignmentBearingOffset(model.architecturalAlignment);

  // North-flip (DEFAULT ON). The previous formula was
  //     sheetBearing = 180 - heading + bearingOffset
  // and it drew the arrow exactly 180 deg wrong on a real drawing: that scan
  // (heading 42.352 deg, alignment offset 27.629 deg) produced 165.3 deg when
  // the vendor plan showed ~345 deg. Dropping the 180 deg term fixes it:
  //     sheetBearing = (bearingOffset - heading) mod 360
  // which is algebraically 360 - heading + bearingOffset. The assumption is
  // recorded in the manifest (`northArrow.flip180`) and can be disabled with
  // --no-north-flip, which restores the legacy formula verbatim.
  // The flip is the DEFAULT FOR EVERY DIALECT (re-checked on 2026-11-08):
  //     sheetBearing = (bearingOffset - heading) mod 360
  // Optimized (Polycam) exports: reproduced the vendor plan on an anonymized regression example.
  // Raw Apple capture: an anonymized reference example's own generated plan looked 180 deg away
  // from our unflipped arrow; flipped, the needle lands at 174.2 deg and the
  // user confirmed that is the orientation their plan needs. Dialect is only
  // recorded, never used to switch the formula silently.
  const dialectKind = /^optimized/.test(String(model.dialect || '')) ? 'optimized' : 'raw';
  const northFlip = options.northFlip !== false;
  const degrees = heading == null
    ? null
    : normaliseDegrees(northFlip ? bearingOffset - heading : 180 - heading + bearingOffset);

  const reasons = [];
  let approximate = false;
  if (degrees == null) {
    reasons.push('no compass/orientation value in the scan or meta.json');
  } else {
    if (orientationSource === 'meta.json') {
      approximate = true;
      reasons.push('bearing comes from meta.json headingDegrees (project metadata), not from a per-scan compass reading');
    }
    if (confidence == null) {
      if (orientationSource !== 'meta.json') {
        approximate = true;
        reasons.push('no compass confidence value in the source');
      }
    } else if (confidence < NORTH_CONFIDENCE_THRESHOLD) {
      approximate = true;
      reasons.push(`compass confidence ${confidence} is below ${NORTH_CONFIDENCE_THRESHOLD}`);
    }
    if (uncertainty != null && uncertainty > 10) {
      approximate = true;
      reasons.push(`compass uncertainty ${uncertainty}° exceeds 10°`);
    }
  }

  const known = degrees != null;
  const basis = known ? (orientationSource === 'meta.json' ? 'meta.headingDegrees' : 'scan.orientation') : 'none';
  const north = {
    // A heading from meta.json is a real orientation and is drawn as "N";
    // `described` records how much weight the sheet's reader may put on it.
    described: known ? (approximate ? 'approx' : 'source-provided') : 'unknown',
    basis,
    sourceHeadingDegrees: heading,
    alignmentBearingOffsetDegrees: Number(bearingOffset.toFixed(4)),
    degreesClockwiseFromDrawingUp: degrees,
    label: known ? 'N' : 'SMJER NEPOZNAT',
    // A rose without a needle when the direction is unknown: no false north.
    needle: known,
    dialectKind,
    source: orientationSource,
    confidence,
    uncertaintyDegrees: uncertainty,
    approximate,
    reasons,
    usedWithoutGeo: true,
    // The 180 deg flip is an explicit, reversible assumption, never silent.
    flip180: northFlip,
    formula: northFlip
      ? 'sheetBearing = (alignmentBearingOffset - heading) mod 360'
      : 'sheetBearing = (180 - heading + alignmentBearingOffset) mod 360 (unflipped, --no-north-flip)',
    formulaRationale: northFlip
      ? 'flipped form: the default for every dialect; numeric regression convention; not an independently verified site orientation'
      : 'unflipped form: kept only as --no-north-flip; it drew an anonymized reference example 180 deg wrong',
    rotationConvention: 'degrees clockwise from drawing up (+Y); the drawing up direction is the DXF +Y axis, i.e. plan north is +Y when the value is 0',
  };

  if (!known) {
    warnings.push({
      code: 'roomplan.north-direction-unknown',
      message: 'No compass/orientation metadata in the source. The sheet draws an EMPTY rose with the words "SMJER NEPOZNAT" and no needle: a needle at any angle would be a bearing the data does not support. North must be established independently.',
    });
  } else if (approximate) {
    warnings.push({
      code: 'roomplan.north-direction-approximate',
      message: `North arrow is APPROXIMATE (${basis}; ${degrees.toFixed(1)}° clockwise from drawing up): ${reasons.join('; ')}. It is a usable drawing annotation, not a surveying bearing.`,
    });
  }
  if (known && orientationSource === 'meta.json') {
    warnings.push({
      code: 'roomplan.north-heading-from-meta',
      message: 'Orientation comes from meta.json headingDegrees (project metadata) because the scan carries no compass reading; the north arrow uses it without --geo, because orientation is not a location.',
    });
  }
  if (known && northFlip) {
    warnings.push({
      code: 'roomplan.north-flip-applied',
      message: 'North arrow uses the flipped formula sheetBearing = (alignmentBearingOffset - heading) mod 360: the unflipped form was 180° off on a real drawing checked against the vendor plan. Pass --no-north-flip to restore the legacy formula.',
    });
  }

  if (scaleText.toUpperCase() === 'NTS') {
    warnings.push({
      code: 'roomplan.scale-not-to-scale',
      message: 'Title block scale reads "NTS": the scan has no known plot scale, so the drawing is not a measured, plottable layout. Any paper scale must be established independently.',
    });
  }
  if (place && locationSource === 'place') {
    warnings.push({
      code: 'roomplan.place-from-cli',
      message: `Location cell shows the free-text place "${place}" given with --place. It is a drawing annotation typed by the operator: never geocoded, never verified, and it overrides --place-lookup and --geo coordinates.`,
    });
  }

  const story = Number.isFinite(options.story) ? Math.trunc(options.story) : 0;
  const kat = storyLabel(story);

  // A very long project name is allowed here; dxf-emit.py truncates it to the
  // project cell (one line, never wrapped, never overlapping the next cell).
  const sourceNote = [
    `Source: ${model.kind === 'optimized' ? 'optimized/Polycam-style' : 'raw Apple'} RoomPlan JSON`,
    'DXF R2018, metres',
    'title block scale is textual, not a paper layout',
    'not a measured survey',
  ].join(' · ');

  return {
    titleBlock: {
      project,
      story,
      storyLabel: kat,
      author,
      drawnBy: `by ${author}`,
      scaleText,
      date,
      sheet,
      locationText,
      locationSource,
      sourceNote,
      frame: !options.noFrame,
    },
    north,
    warnings,
    // Flattened payload handed to dxf-emit.py (one object, no nesting).
    dxfMeta: {
      project,
      story,
      storyLabel: kat,
      author,
      drawnBy: `by ${author}`,
      scaleText,
      date,
      sheet,
      locationText,
      locationSource,
      sourceNote,
      north,
    },
  };
}

module.exports = {
  buildPlanMeta,
  alignmentBearingOffset,
  normaliseDegrees,
  storyLabel,
  DEFAULT_AUTHOR,
  DEFAULT_SCALE_TEXT,
  DEFAULT_SHEET,
  NORTH_CONFIDENCE_THRESHOLD,
  CHAR_WIDTH_RATIO,
  todayISO,
};
