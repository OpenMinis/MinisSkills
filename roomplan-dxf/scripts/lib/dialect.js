'use strict';
// Content evidence only. Filenames and isolated category/meshInfo are not dialect evidence.
const elementKeys = ['walls', 'floors', 'doors', 'windows', 'openings', 'objects'];
const own = (o,k) => Object.prototype.hasOwnProperty.call(o,k);
function detectDialect(root) {
  if (!root || typeof root !== 'object' || Array.isArray(root)) throw new Error('Unrecognized RoomPlan: root must be an object');
  if (own(root,'format_version')) {
    if (root.format_version !== 1) throw new Error(`Unsupported optimized RoomPlan format version ${root.format_version}`);
    if (root.captureSessions || (Array.isArray(root.rooms) && root.rooms.some(r => r && Array.isArray(r.walls)))) throw new Error('Ambiguous RoomPlan: explicit optimized version with raw room/wrapper structure');
    return {kind:'optimized', dialect:'optimized-v1', evidence:['explicit format_version = 1; geometry validated by adapter']};
  }
  const polygonHint = Array.isArray(root.rooms) && root.rooms.some(r => r && (own(r,'vertices_x') || own(r,'vertices_z') || own(r,'label_automated')));
  const optimizedHint = own(root,'alignment_transform') || polygonHint;
  if (optimizedHint) {
    if (root.captureSessions || (Array.isArray(root.rooms) && root.rooms.some(r => r && Array.isArray(r.walls)))) throw new Error('Ambiguous RoomPlan: raw and optimized structures mixed');
    if (!['walls','rooms','floors','doors','windows','openings','objects'].every(k=>Array.isArray(root[k])) || !root.walls.length || !root.rooms.length || !own(root,'alignment_transform')) throw new Error('Malformed/unrecognized legacy optimized RoomPlan: requires walls, room polygons, all element arrays and alignment_transform; no raw fallback');
    return {kind:'optimized',dialect:'optimized-legacy-unversioned',evidence:['no format_version','all element arrays, nonempty walls/rooms, alignment_transform','room polygons and numeric element geometry validated by adapter']};
  }
  const rawRoom = r => r && typeof r==='object' && elementKeys.some(k=>Array.isArray(r[k]) && r[k].length>0) && !own(r,'vertices_x');
  if ([Array.isArray(root.captureSessions),Array.isArray(root.rooms),rawRoom(root)].filter(Boolean).length>1) throw new Error('Ambiguous raw RoomPlan: multiple root room/structure/session shapes');
  if (Array.isArray(root.captureSessions) && root.captureSessions.length && root.captureSessions.every(cs=>cs && Array.isArray(cs.roomplanSessions) && cs.roomplanSessions.length && cs.roomplanSessions.every(rawRoom))) return {kind:'raw',dialect:'apple-session-wrapper',evidence:['captureSessions[].roomplanSessions[] element arrays']};
  if (Array.isArray(root.rooms) && root.rooms.length && root.rooms.every(rawRoom)) return {kind:'raw',dialect:'apple-structure',evidence:['rooms[] with raw element arrays']};
  if (rawRoom(root)) return {kind:'raw',dialect:'apple-room',evidence:['top-level raw element arrays']};
  throw new Error('Unrecognized RoomPlan JSON shape: requires numeric raw element geometry or positively recognized optimized room polygons; filename is not evidence');
}
module.exports = {detectDialect};
