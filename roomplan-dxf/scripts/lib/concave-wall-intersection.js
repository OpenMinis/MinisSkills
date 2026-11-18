'use strict';
// Simple planar wall rings; convex apertures only. Triangles have disjoint
// interiors, so their intersections add without union or seam double counting.
const {triangulate}=require('./planar-polygon');
const orient=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const area=p=>Math.abs(p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-a[1]*b[0];},0))/2;
function clip(poly,ring){
 const sign=ring.reduce((s,a,i)=>{const b=ring[(i+1)%ring.length];return s+a[0]*b[1]-a[1]*b[0];},0)>0?1:-1;
 for(let i=0;i<ring.length&&poly.length;i++){
  const a=ring[i],b=ring[(i+1)%ring.length],input=poly;poly=[];
  for(let j=0;j<input.length;j++){
   const p=input[j],q=input[(j+1)%input.length],dp=sign*orient(a,b,p),dq=sign*orient(a,b,q);
   if(dp>=0)poly.push(p);
   if((dp>=0)!==(dq>=0)){const t=dp/(dp-dq);poly.push(p.map((v,k)=>v+t*(q[k]-v)));}
  }
 }
 return poly;
}
function distance(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],l=dx*dx+dy*dy;const t=l?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l)):0;return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);}
// Split EVERY aperture edge at boundary crossings, not just its vertices.
// Between crossings the midpoint determines inside/outside. For each outside
// interval, distance to any fixed wall segment is convex, so the larger endpoint
// distance bounds the ENTIRE interval. Min over wall segments is conservative.
function edgeOutsideBound(poly,wall,inPolygon){
 let bound=0;
 for(let i=0;i<poly.length;i++){
  const a=poly[i],b=poly[(i+1)%poly.length],r=[b[0]-a[0],b[1]-a[1]],ts=[0,1];
  for(let j=0;j<wall.length;j++){
   const c=wall[j],d=wall[(j+1)%wall.length],s=[d[0]-c[0],d[1]-c[1]],den=r[0]*s[1]-r[1]*s[0];
   if(den!==0){const t=((c[0]-a[0])*s[1]-(c[1]-a[1])*s[0])/den,u=((c[0]-a[0])*r[1]-(c[1]-a[1])*r[0])/den;if(t>0&&t<1&&u>=0&&u<=1)ts.push(t);}
  }
  ts.sort((x,y)=>x-y);const at=t=>[a[0]+t*r[0],a[1]+t*r[1]];
  for(let j=1;j<ts.length;j++){
   const p=at(ts[j-1]),q=at(ts[j]);
   if(inPolygon(at((ts[j-1]+ts[j])/2),wall,0))continue;
   bound=Math.max(bound,Math.min(...wall.map((c,k)=>Math.max(distance(p,c,wall[(k+1)%wall.length]),distance(q,c,wall[(k+1)%wall.length])))));
  }
 }
 return bound;
}
function intersect(wall,opening,inPolygon){
 const turns=opening.map((p,i)=>orient(p,opening[(i+1)%opening.length],opening[(i+2)%opening.length])).filter(x=>Math.abs(x)>1e-12);
 if(!turns.length||!(turns.every(x=>x>0)||turns.every(x=>x<0)))throw new Error('convex opening required');
 const mesh=triangulate(wall.map(p=>[p[0],p[1],0]));
 const triangles=mesh.triangles.map(t=>t.map(p=>p.slice(0,2)));
 const pieces=triangles.map(t=>clip(opening,t)).filter(p=>p.length>=3&&area(p)>0);
 const intersectionAreaM2=pieces.reduce((s,p)=>s+area(p),0),openingAreaM2=area(opening);
 if(intersectionAreaM2>openingAreaM2+1e-10)throw new Error('intersection area postcondition');
 return {intersectionAreaM2,outsideAreaM2:Math.max(0,openingAreaM2-intersectionAreaM2),intersectionPiecesM:pieces,wallTrianglesM:triangles,maxEdgeOutsideDistanceBoundM:edgeOutsideBound(opening,wall,inPolygon),method:'disjoint planar-polygon wall triangles intersected with convex opening; full-edge outside-distance bound'};
}
module.exports={intersect};
