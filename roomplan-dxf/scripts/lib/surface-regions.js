'use strict';
// Surface Region: supplied face or an explicitly identified reconstruction zone.
// A group is a semantic reference, never an additional quantity or merged plane.
function normal(points){
 if(!points||points.length<3)return null;
 const p=points.map(q=>Array.isArray(q)?q:[q.x,q.y,q.z]),n=[0,0,0];
 for(let i=0;i<p.length;i++){const a=p[i],b=p[(i+1)%p.length];n[0]+=(a[1]-b[1])*(a[2]+b[2]);n[1]+=(a[2]-b[2])*(a[0]+b[0]);n[2]+=(a[0]-b[0])*(a[1]+b[1]);}
 const len=Math.hypot(...n);return len>0?n.map(x=>x/len):null;
}
function bend(faces){if(faces.length!==2)return null;const n=faces.map(r=>normal(r.worldCornersM));return n.every(Boolean)?Math.acos(Math.min(1,Math.abs(n[0].reduce((s,v,i)=>s+v*n[1][i],0))))*180/Math.PI:null;}
function buildRegistry(records, sha256, override=null) {
 const regions=records.map((r,i)=>({
  id:r.sourceRegionId || `SR reconstructed:${r.zoneKey || `story:${r.story}:zone:${i}`}`,
  origin:r.status==='supplied'?'supplied':'reconstructed',
  sourceRefs:r.sourceRefs||(r.status==='supplied'?[r.source]:[{zoneKey:r.zoneKey||null,method:r.method,wallTopReconstruction:true}]),
  roomIdentifier:r.roomIdentifier,story:r.story,areaM2:r.ceilingAreaM2??null,
  worldCornersM:r.worldCornersM||null,heightM:r.heightM||null,
 }));
 const byId=new Map(regions.map(r=>[r.id,r]));
 if(byId.size!==regions.length)throw new Error('Duplicate Surface Region ID');
 const groups=[];
 if(override){
  if(override.sourceSHA256!==sha256)throw new Error('Surface Region override source SHA256 mismatch');
  const used=new Set();
  for(const g of override.groups||[]){
   if(g.confirmation!=='user-confirmed')throw new Error('Only user-confirmed groups accepted as confirmed');
   if(!g.id||!Array.isArray(g.members)||g.members.length<2)throw new Error('Invalid Surface Region group');
   const faces=g.members.map(id=>{if(!byId.has(id)||used.has(id))throw new Error('Unknown or multiply grouped Surface Region');used.add(id);return byId.get(id);});
   if(faces.some(r=>r.story!==faces[0].story||r.roomIdentifier!==faces[0].roomIdentifier))throw new Error('Group must belong to one room and story');
   groups.push({id:g.id,confirmation:'user-confirmed',members:g.members.slice(),faceCount:faces.length,
    areaM2:faces.every(r=>Number.isFinite(r.areaM2))?faces.reduce((s,r)=>s+r.areaM2,0):null,
    bendAngleDegrees:bend(faces),
    interpretation:'piecewise source faces; no flattening, no additional quantity; physical envelope unresolved'});
  }
 }
 return {definition:'SR = Surface Region',sourceSHA256:sha256,regions,groups,
  quantityBasis:'source surface sum with multiplicity; NOT verified physical total; groups are non-additive references'};
}
module.exports={buildRegistry};
