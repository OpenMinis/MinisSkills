'use strict';
const assert=require('assert');
const {buildReport}=require('../scripts/lib/quantities');
const I=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const points=ps=>ps.map(([x,y])=>({x,y,z:0}));
const wall={kind:'wall',identifier:'w',story:0,transform:I,polygonCorners:points([[0,0],[4,0],[3,3],[0,3]]),dimensions:{x:4,y:3,z:0}};
function opening(x,y,w=1,h=1,id='o'){const t=I.slice();t[12]=x;t[13]=y;return {kind:'door',identifier:id,parentIdentifier:'w',story:0,transform:t,dimensions:{x:w,y:h,z:0}};}
function run(w,os){return buildReport({kind:'raw',sourceSHA256:'synthetic',surfaces:[w,...os],objects:[]});}
function element(r){return r.elements.find(e=>e.kind==='wall');}
let checks=0;const check=f=>{f();checks++;};
const tiny=element(run(wall,[opening(1,.5-2e-7)]));
check(()=>assert(Math.abs(tiny.netArea.value-9.5000002)<1e-10));
check(()=>assert.strictEqual(tiny.netArea.coverage,'complete'));
check(()=>assert.strictEqual(tiny.netArea.status,'estimated'));
check(()=>assert.strictEqual(tiny.openingDiagnostics[0].clippingApplied,true));
check(()=>assert(tiny.openingDiagnostics[0].outsideAreaM2>0));
check(()=>assert.strictEqual(element(run(wall,[opening(1,.5-2e-6)])).netArea.value,null));
// Inside the wall bounding box but outside the actual sloped boundary.
check(()=>assert.strictEqual(element(run(wall,[opening(3.4,2)])).netArea.value,null));
const concave={...wall,polygonCorners:points([[0,0],[4,0],[4,3],[3,3],[3,1],[1,1],[1,3],[0,3]])};
// Vertices lie in the two arms, but the edge crosses the missing notch.
check(()=>assert.strictEqual(element(run(concave,[opening(2,2,3.6,.5)])).netArea.value,null));
check(()=>assert.strictEqual(element(run(wall,[opening(1,1),opening(1,1,1,1,'o2')])).netArea.value,null));
const off=opening(1,.5-2e-7);off.transform[14]=.02;
check(()=>assert.strictEqual(element(run(wall,[off])).netArea.value,null));
const other=opening(1,.5-2e-7);other.story=1;
check(()=>assert.strictEqual(element(run(wall,[other])).netArea.value,null));
const supplied=opening(1,.5-2e-7);supplied.polygonCorners=points([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]]);
check(()=>assert.strictEqual(element(run(wall,[supplied])).netArea.value,null));
const huge={...wall,polygonCorners:points([[0,0],[40,0],[39,3],[0,3]])};
check(()=>assert.strictEqual(element(run(huge,[opening(20,.5-5e-7,30)])).netArea.value,null));
const partial=run(wall,[opening(1,.5-2e-6)]);
check(()=>assert.strictEqual(partial.totals.wallAreaNet.coverage,'partial'));
function rotated(y,id){const o=opening(1.5,y,2,.4,id),c=Math.SQRT1_2;o.transform[0]=c;o.transform[1]=c;o.transform[4]=-c;o.transform[5]=c;return o;}
const disjoint=element(run(wall,[rotated(1,'a'),rotated(1.8,'b')]));
check(()=>assert(Math.abs(disjoint.netArea.value-8.9)<1e-10));
check(()=>assert.strictEqual(element(run(wall,[rotated(1,'a'),rotated(1.3,'b')])).netArea.value,null));
// Reversed source order must preserve the exact same separation decision.
check(()=>assert(Math.abs(element(run(wall,[rotated(1.8,'b'),rotated(1,'a')])).netArea.value-8.9)<1e-10));
console.log('focused convex-wall clipping:',checks,'checks passed');
