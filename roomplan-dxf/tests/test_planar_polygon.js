'use strict';
const assert=require('assert');
const {triangulate}=require('../scripts/lib/planar-polygon');
const {meshArrays}=require('../scripts/lib/usda-export');
const shapes={L:[[0,0],[3,0],[3,3],[1,3],[1,1],[0,1]],U:[[0,0],[4,0],[4,4],[3,4],[3,1],[1,1],[1,4],[0,4]],collinear:[[0,0],[2,0],[4,0],[4,3],[0,3]]};
const records=[];
for(const [name,ring] of Object.entries(shapes)) for(const reverse of [false,true])for(let start=0;start<ring.length;start++)for(const closed of [false,true])for(const plane of ['horizontal','tilted','vertical']){
 let q=ring.slice(start).concat(ring.slice(0,start));if(reverse)q.reverse();if(closed)q.push(q[0]);
 const p=q.map(([x,y])=>plane==='horizontal'?[x,0,y]:plane==='vertical'?[x,y,0]:[x,y*.6,y*.8]);
 const r=triangulate(p),m=meshArrays({points:p,faces:[p.map((_,i)=>i)]});
 const area=Math.abs(ring.reduce((s,a,i)=>{const b=ring[(i+1)%ring.length];return s+a[0]*b[1]-a[1]*b[0];},0))/2;
 assert(Math.abs(r.surfaceArea3D-area)<1e-9);assert(Math.abs(m.renderMeshArea-area)<1e-9);
 records.push({name,reverse,start,closed,plane,polygon:p,triangles:r.triangles,area});
}
for(const p of [[[0,0,0],[2,0,2],[0,0,2],[2,0,0]],[[0,0,0],[1,0,0],[1,1,1],[0,0,1]]])assert.throws(()=>triangulate(p),/planar-polygon/);
assert.throws(()=>meshArrays({points:[[0,0,0],[1,0,0],[0,1,0]],faces:[[0,1,2]],holes:[[0,1,2]]}),/unsupported hole/);
if(process.argv.includes('--json'))console.log(JSON.stringify(records));else console.log(`planar-polygon: ${records.length} synthetic variants passed; invalid/self-intersection/non-planar/hole refusal passed`);
