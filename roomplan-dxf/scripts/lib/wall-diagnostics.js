'use strict';
// Source-space diagnostics. Returns exact convex intersection; caller decides
// whether the intersection is safe to subtract and must record that decision.
const sub=(a,b)=>a.map((x,i)=>x-b[i]);
const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
function world(p,t){return [0,1,2].map(i=>t[i]*p[0]+t[4+i]*p[1]+t[8+i]*p[2]+t[12+i]);}
function local(p,t){const q=sub(p,t.slice(12,15));return [0,4,8].map(i=>dot(q,t.slice(i,i+3)));}
function points(s){const p=s.polygonCorners?.length?s.polygonCorners.map(p=>[p.x,p.y,p.z]):[[-s.dimensions.x/2,-s.dimensions.y/2,0],[s.dimensions.x/2,-s.dimensions.y/2,0],[s.dimensions.x/2,s.dimensions.y/2,0],[-s.dimensions.x/2,s.dimensions.y/2,0]];return p.map(p=>world(p,s.transform));}
function diagnose(w,o,g,og,inPolygon){
 const p=points(o),projected=p.map(g.project),parentLocal=p.map(p=>local(p,w.transform));
 const wp=points(w).map(p=>local(p,w.transform));
 const bounds=pts=>[0,1,2].map(i=>({min:Math.min(...pts.map(p=>p[i])),max:Math.max(...pts.map(p=>p[i]))}));
 const wb=bounds(wp),ob=bounds(parentLocal);
 const violations=wb.map((b,i)=>({axis:['x','y','z'][i],belowMm:Math.max(0,b.min-ob[i].min)*1000,aboveMm:Math.max(0,ob[i].max-b.max)*1000}));
 const planes=p.map(p=>dot(sub(p,g.origin),g.n)*1000);
 const area=poly=>Math.abs(poly.reduce((s,p,i)=>{const q=poly[(i+1)%poly.length];return s+p[0]*q[1]-q[0]*p[1];},0))/2;
 // Exact convex intersection; no concave clipping or polygon union.
 const orient=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 const turns=g.poly.map((p,i)=>orient(p,g.poly[(i+1)%g.poly.length],g.poly[(i+2)%g.poly.length])).filter(x=>Math.abs(x)>1e-7);
 const convex=turns.every(x=>x>0)||turns.every(x=>x<0);
 let clipped=projected;
 if(convex){const sign=turns[0]>0?1:-1;for(let i=0;i<g.poly.length&&clipped.length;i++){
  const a=g.poly[i],b=g.poly[(i+1)%g.poly.length],input=clipped;clipped=[];
  for(let j=0;j<input.length;j++){const p=input[j],q=input[(j+1)%input.length],dp=sign*orient(a,b,p),dq=sign*orient(a,b,q);if(dp>=0)clipped.push(p);if((dp>=0)!==(dq>=0)){const t=dp/(dp-dq);clipped.push(p.map((v,k)=>v+t*(q[k]-v)));}}
 }}
 const intersection=convex?area(clipped):null;
 const distance=(p,a,b)=>{const d=sub(b,a),t=Math.max(0,Math.min(1,dot(sub(p,a),d)/dot(d,d)));return Math.hypot(...sub(p,a.map((v,i)=>v+t*d[i])));};
 const maxOutsideDistanceM=Math.max(0,...projected.filter(p=>!inPolygon(p,g.poly,1e-7)).map(p=>Math.min(...g.poly.map((a,i)=>distance(p,a,g.poly[(i+1)%g.poly.length])))));
 return {intersectionPolygonM:convex?clipped:null,maxOutsideDistanceM,openingKey:`${o.kind}:${o.identifier}`,coordinateSpace:'source world projected to parent plane and parent local; rigid column-major inverse',parentLocalCornersM:parentLocal,parentPolygonLocalM:wp,parentLocalBoundsM:wb,openingLocalBoundsM:ob,bboxViolationsMm:violations,signedPlaneDistancesMm:planes,maxAbsPlaneDistanceMm:Math.max(...planes.map(Math.abs)),containedVertices:projected.map(p=>inPolygon(p,g.poly,1e-7)),wallAreaM2:g.area,openingAreaM2:og.area,intersectionAreaM2:intersection,outsideAreaM2:intersection==null?null:Math.max(0,og.area-intersection),convexWall:convex,netPolicy:'strict containment retained; intersection is diagnostic only, not measured clipped quantity'};
}
module.exports={diagnose};
