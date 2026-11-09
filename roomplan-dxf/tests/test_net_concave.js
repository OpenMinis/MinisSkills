'use strict';
const assert=require('assert'),fs=require('fs');
const {buildReport,inPolygon}=require('../scripts/lib/quantities');
const {intersect}=require('../scripts/lib/concave-wall-intersection');
const I=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const L=[[0,0],[4,0],[4,1],[1,1],[1,4],[0,4]],U=[[0,0],[4,0],[4,4],[3,4],[3,1],[1,1],[1,4],[0,4]];
const points=p=>p.map(([x,y])=>({x,y,z:0}));
function opening(x,y,w,h,id='o'){const t=I.slice();t[12]=x;t[13]=y;return {kind:'opening',identifier:id,parentIdentifier:'w',story:0,transform:t,dimensions:{x:w,y:h,z:0}};}
function run(poly,os,t=I){return buildReport({kind:'raw',surfaces:[{kind:'wall',identifier:'w',story:0,transform:t,polygonCorners:points(poly)},...os],objects:[]}).elements.find(e=>e.kind==='wall');}
let checks=0;const check=f=>{f();checks++;};const fixtures=[];
for(const wall of [L,U])for(const reverse of [false,true])for(const angle of [0,.37,1.57,2.8]){
 const ring=reverse?wall.slice().reverse():wall;
 const c=Math.cos(angle),s=Math.sin(angle),map=p=>[c*p[0]-s*p[1]+7,s*p[0]+c*p[1]-3];
 for(const o of [opening(.5,2,.5,2),opening(2,.5,2,.5),opening(2,2,3,.5),opening(.5,-2e-7+.25,.5,.5),opening(.5,-2e-6+.25,.5,.5)]){
  const x=o.transform[12],y=o.transform[13],w=o.dimensions.x,h=o.dimensions.y;
  const p=[[x-w/2,y-h/2],[x+w/2,y-h/2],[x+w/2,y+h/2],[x-w/2,y+h/2]];
  const a=intersect(ring.map(map),p.map(map),inPolygon);fixtures.push({wall:ring.map(map),opening:p.map(map),...a});
  check(()=>assert(a.intersectionAreaM2>=0));
 }
 const inside=run(ring,[opening(.5,2,.5,2)]);check(()=>assert(Math.abs(inside.netArea.value-(wall===L?6:9))<1e-10));
 check(()=>assert.strictEqual(run(ring,[opening(2,2,3.6,.5)]).netArea.value,null));
 check(()=>assert(run(ring,[opening(.5,.25-2e-7,.5,.5)]).netArea.value>0));
 check(()=>assert.strictEqual(run(ring,[opening(.5,.25-2e-6,.5,.5)]).netArea.value,null));
 check(()=>assert.strictEqual(run(ring,[opening(.5,2,.5,2),opening(.5,2,.5,1,'b')]).netArea.value,null));
 const off=opening(.5,2,.5,2);off.transform[14]=.02;check(()=>assert.strictEqual(run(ring,[off]).netArea.value,null));
 const other=opening(.5,2,.5,2);other.story=1;check(()=>assert.strictEqual(run(ring,[other]).netArea.value,null));
 // Rigid rotation of both wall and dimensional opening into 3D.
 const t=[c,0,s,0,0,1,0,0,-s,0,c,0,10,20,30,1],o=opening(.5,2,.5,2);o.transform=t.slice();o.transform[12]+=c*.5;o.transform[13]+=2;o.transform[14]+=s*.5;
 check(()=>assert(Math.abs(run(ring,[o],t).netArea.value-(wall===L?6:9))<1e-9));
}
const big=L.map(p=>[p[0]*20,p[1]]);check(()=>assert.strictEqual(run(big,[opening(20,.5-5e-7,30,1)]).netArea.value,null));
const adjacent=run(L,[opening(.5,1,.5,1),opening(.5,2,.5,1,'b')]);check(()=>assert(Math.abs(adjacent.netArea.value-6)<1e-10));
check(()=>assert.throws(()=>intersect([[0,0],[3,3],[0,3],[3,0]],[[0,0],[1,0],[1,1],[0,1]],inPolygon)));
if(process.env.CONCAVE_FIXTURES)fs.writeFileSync(process.env.CONCAVE_FIXTURES,JSON.stringify(fixtures,null,2));
console.log('concave walls:',checks,'checks passed;',fixtures.length,'independent-intersection fixtures');
