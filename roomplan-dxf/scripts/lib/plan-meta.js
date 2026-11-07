'use strict';
/**
 * Builds the sheet furniture metadata (title block + north arrow) that
 * dxf-emit.py draws AROUND the plan.
 *
 * Rules that matter:
 *   - the title block adds no geometry and never moves room geometry;
 *   - the scale is TEXT ONLY ("NTS" by default). Nothing here claims a
 *     printed sheet scale, because the source scan has no known plot scale;
 *   - coordinates are only printed when --geo is passed, otherwise the
 *     location cell reads "location withheld";
 *   - north is drawn whenever a heading exists, including a project-level
 *     `headingDegrees` from meta.json. That case is labelled "meta" and
 *     flagged approximate in the manifest (a project heading is a usable
 *     orientation, not a surveyed bearing). "N?" is drawn ONLY when no
 *     heading exists at all;
 *   - orientation is not location: the north arrow uses the heading whether
 *     or not --geo is passed. --geo governs coordinates only.
 */

const DEFAULT_AUTHOR = 'ARCHIFEST';
const DEFAULT_SCALE_TEXT = 'NTS';
const DEFAULT_SHEET = 'A-01';
const NORTH_CONFIDENCE_THRESHOLD = 0.8;

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

function formatCoordinate(value) {
  // ~11 m at the equator for 4 decimals: short enough for a title block,
  // precise enough to identify the building, not a substitute for a survey.
  return value.toFixed(4);
}

/**
 * @param {object} model decoded model (with meta + optional sourceMeta)
 * @param {object} opts { project, author, scale, sheet, includeGeo, noFrame, sourceMeta }
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
  let locationText;
  if (options.includeGeo && hasGeo) {
    locationText = `${formatCoordinate(meta.latitude)}, ${formatCoordinate(meta.longitude)}`;
  } else {
    locationText = 'location withheld';
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
  // Empirical relation, verified against the vendor's own PDF floorplan and
  // its DXF north arrow (references/title-block.md): in the model frame north
  // sits at (180 - headingDegrees). The alignment rotation then maps it onto
  // the sheet. Residual spread between the two vendor artefacts is < 0.5 deg;
  // the arrow is still labelled approximate because it comes from metadata.
  const degrees = heading == null ? null : normaliseDegrees(180 - heading + bearingOffset);

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
    label: known ? 'N' : 'N?',
    source: orientationSource,
    confidence,
    uncertaintyDegrees: uncertainty,
    approximate,
    reasons,
    usedWithoutGeo: true,
    rotationConvention: 'degrees clockwise from drawing up (+Y); the drawing up direction is the DXF +Y axis, i.e. plan north is +Y when the value is 0',
  };

  if (!known) {
    warnings.push({
      code: 'roomplan.north-direction-unknown',
      message: 'No compass/orientation metadata in the source, so the north arrow is drawn as "N?" pointing up by convention only. Do not read a bearing from this sheet.',
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

  if (scaleText.toUpperCase() === 'NTS') {
    warnings.push({
      code: 'roomplan.scale-not-to-scale',
      message: 'Title block scale reads "NTS": the scan has no known plot scale, so the drawing is not a measured, plottable layout. Any paper scale must be established independently.',
    });
  }

  const sourceNote = [
    `Source: ${model.kind === 'optimized' ? 'optimized/Polycam-style' : 'raw Apple'} RoomPlan JSON`,
    'DXF R2018, metres',
    'title block scale is textual, not a paper layout',
    'not a measured survey',
  ].join(' · ');

  return {
    titleBlock: {
      project,
      author,
      drawnBy: `by ${author}`,
      scaleText,
      date,
      sheet,
      locationText,
      sourceNote,
      frame: !options.noFrame,
    },
    north,
    warnings,
    // Flattened payload handed to dxf-emit.py (one object, no nesting).
    dxfMeta: {
      project,
      author,
      drawnBy: `by ${author}`,
      scaleText,
      date,
      sheet,
      locationText,
      sourceNote,
      north,
    },
  };
}

module.exports = {
  buildPlanMeta,
  DEFAULT_AUTHOR,
  DEFAULT_SCALE_TEXT,
  DEFAULT_SHEET,
  NORTH_CONFIDENCE_THRESHOLD,
  todayISO,
};
