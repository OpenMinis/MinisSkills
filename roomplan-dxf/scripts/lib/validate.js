'use strict';
const fail = (p,why) => { throw new Error(`Malformed RoomPlan at ${p}: ${why}`); };
function number(v,p,min=-1e6,max=1e6) { if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max) fail(p,`expected finite number in [${min}, ${max}]`); return v; }
function vector(a,n,p) { if(!Array.isArray(a)||a.length!==n) fail(p,`expected ${n} numbers`); a.forEach((v,i)=>number(v,`${p}[${i}]`)); return a; }
function matrix(a,p) {
 vector(a,16,p);
 if([3,7,11].some(i=>Math.abs(a[i])>1e-5)||Math.abs(a[15]-1)>1e-5) fail(p,'expected affine column-major 4x4 transform');
 const det=a[0]*(a[5]*a[10]-a[9]*a[6])-a[4]*(a[1]*a[10]-a[9]*a[2])+a[8]*(a[1]*a[6]-a[5]*a[2]);
 if(Math.abs(det)<1e-10) fail(p,'singular transform');
 return a;
}
function polygon(points,p,minimum=3) {
 if(!Array.isArray(points)||points.length<minimum) fail(p,`expected at least ${minimum} vertices`);
 const dimensions=Array.isArray(points[0])?points[0].length:0;
 if(![2,3].includes(dimensions)) fail(p,'expected 2D or 3D numeric vertices');
 points.forEach((v,i)=>vector(v,dimensions,`${p}[${i}]`));
 if(minimum>=3) {
  const a=points[0]; let noncollinear=false;
  for(let i=1;i+1<points.length;i++) {
   const b=points[i],c=points[i+1]; const u=b.map((v,j)=>v-a[j]),v=c.map((x,j)=>x-a[j]);
   const mag=a.length===2?Math.abs(u[0]*v[1]-u[1]*v[0]):Math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);
   if(mag>1e-10) noncollinear=true;
  }
  if(!noncollinear) fail(p,'degenerate polygon');
 }
}
function element(r,p,floor=false) {
 if(!r||typeof r!=='object'||Array.isArray(r)) fail(p,'expected element object');
 matrix(r.transform,`${p}.transform`);
 if(!floor||r.dimensions!=null) { vector(r.dimensions,3,`${p}.dimensions`);r.dimensions.forEach((v,i)=>number(v,`${p}.dimensions[${i}]`,0,1e5)); }
 if(r.story!=null) { number(r.story,`${p}.story`,-10000,10000);if(!Number.isInteger(r.story)) fail(`${p}.story`,'expected integer'); }
 if(r.polygonCorners!=null) {
  if(!Array.isArray(r.polygonCorners)) fail(`${p}.polygonCorners`,'expected array');
  if(r.polygonCorners.length) {r.polygonCorners.forEach((v,i)=>vector(v,3,`${p}.polygonCorners[${i}]`));polygon(r.polygonCorners,`${p}.polygonCorners`);}
 }
 if(floor && (!Array.isArray(r.polygonCorners)||r.polygonCorners.length<3)) fail(`${p}.polygonCorners`,'optimized floor requires a numeric polygon');
 if(r.wall_thickness!=null) number(r.wall_thickness,`${p}.wall_thickness`,0,1000);
 const isOpen=r.isOpen ?? r.category?.door?.isOpen;
 if(isOpen!=null && typeof isOpen!=='boolean') fail(`${p}.isOpen`,'expected boolean');
 if(r.parentIdentifier!=null && typeof r.parentIdentifier!=='string') fail(`${p}.parentIdentifier`,'expected string');
 if(r.curve!=null) {
  if(typeof r.curve!=='object') fail(`${p}.curve`,'expected object');
  for(const [a,b] of [['centerX','center_x'],['centerZ','center_z'],['radius','radius'],['startAngleRadians','start_angle'],['endAngleRadians','end_angle']]) number(r.curve[a]??r.curve[b],`${p}.curve.${a}`,a==='radius'?0:-1e6,1e6);
 }
}
function optimizedRoom(r,p) {
 if(!r||typeof r!=='object') fail(p,'expected room object');
 if(!Array.isArray(r.vertices_x)||!Array.isArray(r.vertices_z)||r.vertices_x.length!==r.vertices_z.length) fail(p,'mismatched room polygon coordinates');
 polygon(r.vertices_x.map((x,i)=>[x,r.vertices_z[i]]),`${p}.vertices`);
 vector(r.center_xz,2,`${p}.center_xz`);number(r.area,`${p}.area`,0,1e10);if(r.floor_height!=null) number(r.floor_height,`${p}.floor_height`);
 if(r.story!=null && (!Number.isInteger(r.story)||Math.abs(r.story)>10000)) fail(`${p}.story`,'expected bounded integer');
 for(const k of ['ceiling_lidar_avg_diff','ceiling_lidar_valid_pct']) if(r[k]!=null) number(r[k],`${p}.${k}`,k.endsWith('pct')?0:-1e6,k.endsWith('pct')?100:1e6);
 if(r.edges!=null&&!Array.isArray(r.edges)) fail(`${p}.edges`,'expected array');
 if(r.curved_edges!=null&&!Array.isArray(r.curved_edges)) fail(`${p}.curved_edges`,'expected array');
}
function geo(root) {
 if(root.latLonAlt!=null) {
  if(typeof root.latLonAlt!=='object'||Array.isArray(root.latLonAlt)) fail('latLonAlt','expected object');
  for(const [k,min,max] of [['latitude',-90,90],['longitude',-180,180],['altitude',-1e6,1e6]]) if(root.latLonAlt[k]!=null) number(root.latLonAlt[k],`latLonAlt.${k}`,min,max);
 }
 if(root.orientation!=null) {
  if(typeof root.orientation!=='object'||Array.isArray(root.orientation)) fail('orientation','expected object');
  if(root.orientation.orientation_degrees!=null) number(root.orientation.orientation_degrees,'orientation.orientation_degrees',-360,360);
  if(root.orientation.uncertainty_degrees!=null) number(root.orientation.uncertainty_degrees,'orientation.uncertainty_degrees',0,360);
 }
}
function sourceGeometry(v,p='source') {
 if(!v||typeof v!=='object') return;
 if(Array.isArray(v)) {v.forEach((x,i)=>sourceGeometry(x,`${p}[${i}]`));return;}
 for(const [k,x] of Object.entries(v)) {
  if(k==='coreModel') continue;
  if(k==='transform'||k==='referenceOriginTransform') matrix(x,`${p}.${k}`);
  else if(k==='polygon') polygon(x,`${p}.${k}`);
  else if(['ceiling','ceiling_curr','sections','curved_edges','attributes'].includes(k)||['rooms','walls','floors','doors','windows','openings','objects'].includes(k)) sourceGeometry(x,`${p}.${k}`);
 }
}
module.exports = {number,vector,matrix,polygon,element,optimizedRoom,geo,fail,sourceGeometry};
