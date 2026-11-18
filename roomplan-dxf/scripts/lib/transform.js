'use strict';
/**
 * 4x4 column-major transform helpers, matching RoomPlan/ARKit convention
 * (the layout Apple ARKit uses for simd_float4x4):
 *   m[0..2]=X axis, m[4..6]=Y axis, m[8..10]=Z axis, m[12..14]=translation.
 */

function apply(m, p) {
  return {
    x: m[0] * p.x + m[4] * p.y + m[8] * p.z + m[12],
    y: m[1] * p.x + m[5] * p.y + m[9] * p.z + m[13],
    z: m[2] * p.x + m[6] * p.y + m[10] * p.z + m[14],
  };
}

function multiply(a, b) {
  // returns a * b  (apply b first, then a) — column-major 4x4
  const r = new Array(16).fill(0);
  for (let col = 0; col < 4; col++) {
    for (let row = 0; row < 4; row++) {
      let sum = 0;
      for (let k = 0; k < 4; k++) sum += a[k * 4 + row] * b[col * 4 + k];
      r[col * 4 + row] = sum;
    }
  }
  return r;
}

function identity() {
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
}

// Rotation about world Y axis (ARKit up axis) by `radians`, as a column-major 4x4.
function rotationY(radians) {
  const c = Math.cos(radians), s = Math.sin(radians);
  return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1];
}

function isFiniteVec(arr) {
  return Array.isArray(arr) && arr.every((v) => typeof v === 'number' && Number.isFinite(v));
}

// Translation column accessors (column-major 4x4: indices 12,13,14 = tx,ty,tz).
function worldX(m) { return m[12]; }
function worldY(m) { return m[13]; }
function worldZ(m) { return m[14]; }

// Rotate a 2D point (x,z) on the ground plane by a precomputed cos/sin pair.
// Positive angle = counter-clockwise when viewed from +Y looking down (ARKit convention).
function apply2D(x, z, cos, sin) {
  return [x * cos - z * sin, x * sin + z * cos];
}

// Ground-plane point -> DXF/CAD (x, y) pair: (x, -z). The minus on Z is
// load-bearing — without it the whole plan is mirrored.
function project(p) {
  return { x: p.x, y: -p.z };
}

module.exports = { apply, multiply, identity, rotationY, isFiniteVec, worldX, worldY, worldZ, apply2D, project };
