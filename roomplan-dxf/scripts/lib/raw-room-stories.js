'use strict';
/** Metadata only: never changes model.rooms, element stories or geometry. */
function rawRooms(root) {
 if(Array.isArray(root.walls)) return [root];
 if(Array.isArray(root.rooms)) return root.rooms;
 if(Array.isArray(root.captureSessions)) return root.captureSessions.flatMap(c=>c.roomplanSessions||[]);
 return [root];
}
function resolveRawRoomStories(model, root) {
 if(model.kind!=='raw'||!root||typeof root!=='object') return [];
 const elements=[...(model.surfaces||[]),...(model.objects||[])];
 return rawRooms(root).map((room,sourceRoomIndex)=>{
  const linked=elements.filter(e=>e.sourceRoomIndex===sourceRoomIndex);
  const expected=['walls','floors','doors','windows','openings','objects'].reduce((n,k)=>n+(Array.isArray(room[k])?room[k].length:0),0);
  const values=[...new Set(linked.map(e=>e.story))];
  let reason=null;
  if(!linked.length) reason='no decoded elements linked by sourceRoomIndex';
  else if(linked.length!==expected) reason='sourceRoomIndex membership count differs from source room elements';
  else if(!values.every(Number.isSafeInteger)) reason='linked elements have missing or invalid assigned story';
  else if(values.length!==1) reason='conflicting assigned stories among linked elements';
  return {sourceRoomIndex,story:reason?null:values[0],sourceStory:room.story??null,
   storyProvenance:'decoded elements linked by sourceRoomIndex after assignStories',
   storyReason:reason||'all linked decoded elements agree on assigned story'};
 });
}
/** Existing raw statistics/handoff have no measured source-room polygons.
 * Keep their numerical pipeline unchanged and expose that absence explicitly. */
function annotateRawRoomStoryGaps(block, assignments) {
 if(!block) return;
 block.roomStoryAssignments=assignments.map(a=>({...a}));
 block.gaps=[...(block.gaps||[]),...assignments.map(a=>
  `source-room:${a.sourceRoomIndex}: ${a.story==null?'assigned story unavailable ('+a.storyReason+')':'assigned story '+a.story}; raw source-room per-room statistics/quantities unavailable in this block; no room polygon inferred.`)];
}
module.exports={resolveRawRoomStories,annotateRawRoomStoryGaps};
