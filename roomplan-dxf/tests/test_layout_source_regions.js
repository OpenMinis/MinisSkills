'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path');
const {place,containsBox,arrow}=require('../scripts/lib/ceiling-layout');
const {decode}=require('../scripts/lib/decode-optimized');const {assignStories}=require('../scripts/lib/story');const {applyArchitecturalAlignment}=require('../scripts/lib/align');const {buildDXF}=require('../scripts/lib/dxf-writer');
const p=[[0,0],[6,0],[6,6],[4,6],[4,2],[2,2],[2,6],[0,6]];
assert(!containsBox(p,[.5,.5,5.5,5.5]),'four interior corners do not prove full containment');
let out=[];const tiny=[[0,0],[.04,0],[.04,.04],[0,.04]];const walls=[{type:'polyline',story:0,layer:'S0_WALL',closed:true,points:[[-1,-1],[1,-1],[1,1],[-1,1]]}];const r=place(tiny,0,'S0_CEILING',walls,out,'SR 1.1  h 0.84');assert.equal(r.status,'unresolved-visible-no-leader');assert(out.some(e=>e.type==='text'&&e.value.includes('0.84')&&e.value.startsWith('UNRESOLVED')));assert(!out.some(e=>e.type==='line'),'blocked route must not draw unsafe leader');
const source='/var/minis/workspace/koraljka/src/optimized_roomplan.json';if(fs.existsSync(source)){
 const raw=fs.readFileSync(source),m=decode(raw,'source.json');assignStories(m);applyArchitecturalAlignment(m);const before=JSON.stringify(m);const a=buildDXF(m,{noFrame:true}),off=buildDXF(m,{noFrame:true,ceilings:false});
 assert.equal(JSON.stringify(m),before,'layout must not mutate source model');
 const select=es=>es.filter(e=>!e.layer.includes('CEILING')&&!e.layer.endsWith('_LABEL'));assert.deepStrictEqual(select(a.plan.entities),select(off.plan.entities),'nonannotation geometry invariant');
 const records=a.ceilingDiagnostics.records;assert.equal(records.filter(r=>r.method==='explicit').length,15,'all supplied alternatives retained');assert(records.some(r=>r.heightM?.min>.83&&r.heightM.min<.85),'true low attic height retained');assert(a.ceilingDiagnostics.warnings.some(w=>w.code==='roomplan.ceiling-source-alternatives'));
 assert(records.filter(r=>r.method==='explicit'&&r.heightM).every(r=>r.label?.includes('SR ')),'each available supplied region has an identifying label');assert(!a.plan.entities.some(e=>e.value==='↓'),'no unicode arrow');assert(a.plan.entities.some(e=>e.role==='downhill-arrow'));
}
console.log('PASS source-region alternatives, low height, model invariance, reflex containment, visible blocked-route fallback, LINE arrows');
