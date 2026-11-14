'use strict';
// Simple planar rings only. Grid-decomposed wall openings remain separate faces.
function triangulate(poly) {
  const fail = s => { throw new Error('planar-polygon: ' + s); };
  if (!Array.isArray(poly) || poly.some(p => !Array.isArray(p) || p.length !== 3 || !p.every(Number.isFinite))) fail('invalid vertices / unsupported hole rings');
  const sub=(a,b)=>a.map((x,i)=>x-b[i]);
  const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const len=a=>Math.hypot(...a);
  if(poly.length<3) fail('fewer than three vertices');
  const origin=poly[0], scale=Math.max(...poly.map(p=>len(sub(p,origin))));
  const eps=Math.max(scale*1e-10,1e-12), ae=Math.max(scale*scale*1e-12,1e-24);
  let p=poly.filter((v,i)=>!i || len(sub(v,poly[i-1]))>eps);
  if(p.length>1 && len(sub(p[0],p[p.length-1]))<=eps)p.pop();
  let n=[0,0,0];
  for(let i=0;i<p.length;i++) {const c=cross(sub(p[i],origin),sub(p[(i+1)%p.length],origin));n=n.map((v,k)=>v+c[k]);}
  const nl=len(n); if(nl<=ae)fail('degenerate or self-intersecting ring'); n=n.map(v=>v/nl);
  if(p.some(v=>Math.abs(dot(sub(v,origin),n))>Math.max(scale*1e-8,1e-9)))fail('non-planar ring');
  let u=sub(p[1],p[0]); u=u.map(v=>v/len(sub(p[1],p[0]))); const v=cross(n,u);
  let q=p.map(a=>[dot(sub(a,origin),u),dot(sub(a,origin),v)]);
  const orient=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const on=(a,b,c)=>Math.abs(orient(a,b,c))<=ae && c[0]>=Math.min(a[0],b[0])-eps && c[0]<=Math.max(a[0],b[0])+eps && c[1]>=Math.min(a[1],b[1])-eps && c[1]<=Math.max(a[1],b[1])+eps;
  for(let i=0;i<q.length;i++)for(let j=i+1;j<q.length;j++){
    if(j===i+1 || (i===0&&j===q.length-1))continue;
    const a=q[i],b=q[(i+1)%q.length],c=q[j],d=q[(j+1)%q.length];
    if((orient(a,b,c)*orient(a,b,d)<0 && orient(c,d,a)*orient(c,d,b)<0)||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b))fail('self-intersection / touching nonadjacent edges');
  }
  // Remove only points lying between their neighbours; never reorder the contour.
  let changed=true;
  while(changed&&q.length>3){changed=false;for(let i=0;i<q.length;i++){const a=(i+q.length-1)%q.length,b=(i+1)%q.length;if(on(q[a],q[b],q[i])){q.splice(i,1);p.splice(i,1);changed=true;break;}}}
  const area=q.reduce((s,a,i)=>{const b=q[(i+1)%q.length];return s+a[0]*b[1]-a[1]*b[0];},0)/2;
  if(area<=ae)fail('invalid winding or zero area');
  const ids=q.map((_,i)=>i), triangles=[];
  const inside=(x,a,b,c)=>orient(a,b,x)>=-ae&&orient(b,c,x)>=-ae&&orient(c,a,x)>=-ae;
  while(ids.length>3){let found=false;for(let k=0;k<ids.length;k++){
    const a=ids[(k+ids.length-1)%ids.length],b=ids[k],c=ids[(k+1)%ids.length];
    if(orient(q[a],q[b],q[c])<=ae || ids.some(i=>i!==a&&i!==b&&i!==c&&inside(q[i],q[a],q[b],q[c])))continue;
    triangles.push([p[a],p[b],p[c]]);ids.splice(k,1);found=true;break;
  }if(!found)fail('ear clipping stalled');}
  triangles.push(ids.map(i=>p[i]));
  let meshArea=0;
  for(const t of triangles){const c=cross(sub(t[1],t[0]),sub(t[2],t[0]));if(dot(c,n)<=ae)fail('triangle winding/degeneracy postcondition');meshArea+=len(c)/2;}
  if(Math.abs(meshArea-area)>Math.max(area*1e-9,ae*10))fail('area postcondition');
  return {triangles, normal:n, surfaceArea3D:area, renderMeshArea:meshArea, projectedArea:area*Math.abs(n[1])};
}
module.exports={triangulate};
