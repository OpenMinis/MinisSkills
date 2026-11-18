'use strict';
/**
 * Story (floor level) assignment.
 *
 * For the raw Apple format, story assignment now happens entirely inside
 * decode-raw.js (per-room logic — using each room's own explicit `story` values
 * when multiple distinct values exist, else clustering rooms by median floor
 * elevation with an 0.8m tolerance). This module is a light pass-through
 * that only fills in a human-readable method label when the decoder left it
 * null (single-room capture, or per-surface `story` used as-is).
 *
 * For the optimized format, story is always source-provided — nothing
 * to do here either.
 */
function assignStories(model) {
  if (model.storyAssignmentMethod == null) {
    model.storyAssignmentMethod = 'source story field (single room / per-surface)';
  }
  const stories = new Set();
  for (const s of model.surfaces) stories.add(s.story);
  for (const o of model.objects) stories.add(o.story);
  model.meta = model.meta || {};
  model.meta.storyCount = stories.size;
  return model;
}

module.exports = { assignStories };
