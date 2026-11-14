'use strict';
/**
 * Architectural alignment for DXF export.
 *
 * It computes a single geometric rotation (as a 4x4 transform, composed
 * with each surface's own transform before projection) from wall directions
 * alone. It is not a screen-orientation rule.
 *
 * For the optimized format, there is no computed alignment: the
 * source's own `alignment_transform` is used verbatim (see decode-optimized.js).
 */
const { multiply, identity } = require('./transform');

/**
 * @param {object[]} wallSurfaces decoded wall surfaces (kind === 'wall', untransformed)
 * @returns {{ matrix: number[], angleRad: number, method: string }}
 */
function computeArchitecturalAlignment(wallSurfaces) {
  let cosine = 0, sine = 0;
  for (const w of wallSurfaces) {
    if (w.curve) continue; // curved walls are excluded from the estimate
    const m = w.transform;
    if (!Array.isArray(m) || m.length !== 16 || !m.every(Number.isFinite)) continue;
    const length = w.dimensions && typeof w.dimensions.x === 'number' ? w.dimensions.x : NaN;
    if (!Number.isFinite(length) || length <= 0) continue;
    // atan2(-m[2], m[0]) — the minus on m[2] is required.
    const angle = Math.atan2(-m[2], m[0]);
    cosine += length * Math.cos(4 * angle);
    sine += length * Math.sin(4 * angle);
  }
  if (Math.hypot(cosine, sine) <= 1e-9) {
    return { matrix: identity(), angleRad: 0, method: 'no-walls-found (identity alignment)' };
  }
  const yaw = Math.atan2(sine, cosine) / 4;
  if (Math.abs(yaw) <= 1e-12) {
    return { matrix: identity(), angleRad: 0, method: 'identity (yaw below threshold)' };
  }
  const c = Math.cos(yaw), s = Math.sin(yaw);
  const matrix = [
    c, 0, s, 0,
    0, 1, 0, 0,
    -s, 0, c, 0,
    0, 0, 0, 1,
  ];
  return {
    matrix,
    angleRad: yaw,
    method: `wall-length-weighted orthogonal circular mean (${wallSurfaces.length} wall(s) considered)`,
  };
}

/**
 * @param {object} model decoded + story-assigned model
 * @returns {{ matrix: number[], angleRad: number, method: string }} the alignment used;
 *   also stashed on model.architecturalAlignment for the manifest.
 */
function applyArchitecturalAlignment(model) {
  let alignment;
  if (model.kind === 'optimized') {
    // Optimized: alignment is source-provided (meta.alignmentTransform);
    // the capture's alignmentTransform is used as-is.
    const m = (model.meta && model.meta.alignmentTransform) || identity();
    alignment = { matrix: m, angleRad: null, method: 'source-provided alignment_transform' };
  } else {
    const walls = model.surfaces.filter((s) => s.kind === 'wall');
    alignment = computeArchitecturalAlignment(walls);
  }
  model.architecturalAlignment = alignment;
  return alignment;
}

module.exports = { computeArchitecturalAlignment, applyArchitecturalAlignment, multiply };
