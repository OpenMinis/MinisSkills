'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),crypto=require('crypto');
const base=path.resolve(__dirname,'..');
const {decode}=require('../scripts/lib/decode-raw');
const {assignStories}=require('../scripts/lib/story');
const {applyArchitecturalAlignment}=require('../scripts/lib/align');
const {buildCapture}=require('../scripts/lib/capture-export');
const {buildReport}=require('../scripts/lib/quantities');
const {resolveRawRoomStories}=require('../scripts/lib/raw-room-stories');
const files=process.argv.slice(2);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const results=[];
for(const file of files){
 const bytes=fs.readFileSync(file),root=JSON.parse(bytes),m=decode(bytes,path.basename(file));assignStories(m);
 assert.strictEqual(m.rooms,null);
 const before=JSON.stringify(m),rootBefore=JSON.stringify(root);
 const metadata=resolveRawRoomStories(m,root);
 assert.deepStrictEqual(metadata.map(r=>r.story),[0,1]);
 assert.deepStrictEqual(metadata.map(r=>r.sourceStory),[0,0]);
 const report=buildReport(m,root);
 assert.strictEqual(JSON.stringify(m),before,'report mutated model');
 assert.strictEqual(JSON.stringify(root),rootBefore,'report mutated source');
 assert.deepStrictEqual(report.rooms.map(r=>r.story),[0,1]);
 assert.deepStrictEqual(report.rooms.map(r=>r.sourceStory),[0,0]);
 for(const block of [report.statistics,report.handoff]){
  assert(block);assert.deepStrictEqual(block.roomStoryAssignments,metadata);
  for(const r of metadata)assert(block.gaps.some(g=>g.includes('source-room:'+r.sourceRoomIndex+': assigned story '+r.story)));
 }
 const copy=structuredClone(m);applyArchitecturalAlignment(copy);
 const capture=buildCapture(copy,root);
 assert.deepStrictEqual(capture.rooms.map(r=>r.story),[0,1]);
 assert.deepStrictEqual(capture.rooms.map(r=>r.sourceStory),[0,0]);
 assert.deepStrictEqual(capture.rooms.map(r=>r.storyReason),metadata.map(r=>r.storyReason));
 assert.deepStrictEqual(resolveRawRoomStories({...m,surfaces:[...m.surfaces].reverse(),objects:[...m.objects].reverse()},root),metadata,'relied on element order');
 const conflict=structuredClone(m),linked=conflict.surfaces.filter(e=>e.sourceRoomIndex===0);
 assert(linked.length>1);linked[0].story=99;
 const c=resolveRawRoomStories(conflict,root);
 assert.strictEqual(c[0].story,null);assert.match(c[0].storyReason,/conflicting/);assert.strictEqual(c[1].story,1);
 const cr=buildReport(conflict,root);assert.strictEqual(cr.rooms[0].story,null);assert.match(cr.rooms[0].storyReason,/conflicting/);
 for(const block of [cr.statistics,cr.handoff])assert(block.gaps.some(g=>g.includes('source-room:0: assigned story unavailable (conflicting')));
 applyArchitecturalAlignment(conflict);assert.strictEqual(buildCapture(conflict,root).rooms[0].story,null);
 const missing=structuredClone(m);missing.surfaces=missing.surfaces.filter(e=>e.sourceRoomIndex!==0);missing.objects=missing.objects.filter(e=>e.sourceRoomIndex!==0);
 assert.match(resolveRawRoomStories(missing,root)[0].storyReason,/no decoded elements/);
 const invalid=structuredClone(m);invalid.surfaces[0].story=null;assert.strictEqual(resolveRawRoomStories(invalid,root)[0].story,null);
 assert.strictEqual(sha(fs.readFileSync(file)),sha(bytes),'input changed');
 results.push({file,sha256:sha(bytes),rooms:metadata,totals:report.totals,statisticsTotals:report.statistics.totals});
 if(process.env.STORY_RESULT_DIR){
  const out=process.env.STORY_RESULT_DIR;fs.mkdirSync(out,{recursive:true});const prefix=results.length===1?'Aug19':'Sep23';
  fs.writeFileSync(path.join(out,prefix+'.report.json'),JSON.stringify(report,null,2));
  fs.writeFileSync(path.join(out,prefix+'.capture.json'),JSON.stringify(capture,null,2));
 }
}
// Index, not identifier: source room identifiers can be absent or duplicated.
const root={rooms:[{story:0,walls:[{}]},{story:0,walls:[{}]}]};
const m={kind:'raw',rooms:null,surfaces:[{identifier:'same',sourceRoomIndex:1,story:1},{identifier:'same',sourceRoomIndex:0,story:0}],objects:[]};
assert.deepStrictEqual(resolveRawRoomStories(m,root).map(r=>r.story),[0,1]);
assert.strictEqual(resolveRawRoomStories({...m,surfaces:[...m.surfaces,{sourceRoomIndex:0,story:0}]},root)[0].story,null);
assert.deepStrictEqual(resolveRawRoomStories({kind:'optimized'},{}),[]);
console.log(JSON.stringify({ok:true,realInputs:results},null,2));
