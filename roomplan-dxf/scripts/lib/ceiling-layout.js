'use strict';
// Polygon-aware annotation layout. Baseline TEXT envelope: 1.2h per codepoint, descent .35h,
// ascent 1.2h. Not a guarantee for arbitrary substituted CAD fonts.
const EPS=1e-9;
const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const edges=p=>p.map((a,i)=>[a,p[(i+1)%p.length]]);
function on(p,a,b){return Math.abs(cross(a,b,p))<EPS&&p[0]>=Math.min(a[0],b[0])-EPS&&p[0]<=Math.max(a[0],b[0])+EPS&&p[1]>=Math.min(a[1],b[1])-EPS&&p[1]<=Math.max(a[1],b[1])+EPS;}
function inside(p,poly){if(edges(poly).some(([a,b])=>on(p,a,b)))return true;let ok=false;for(const [a,b] of edges(poly))if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])ok=!ok;return ok;}
function proper(a,b,c,d){return cross(a,b,c)*cross(a,b,d)<-EPS&&cross(c,d,a)*cross(c,d,b)<-EPS;}
function segmentInside(a,b,poly){
 if(!inside(a,poly)||!inside(b,poly))return false;
 // Split at every boundary contact, including reflex vertices; test every interval.
 const dx=b[0]-a[0],dy=b[1]-a[1],ts=[0,1];
 for(const [c,d] of edges(poly)){
  const ex=d[0]-c[0],ey=d[1]-c[1],den=dx*ey-dy*ex;
  if(Math.abs(den)>EPS){const t=((c[0]-a[0])*ey-(c[1]-a[1])*ex)/den,u=((c[0]-a[0])*dy-(c[1]-a[1])*dx)/den;if(t>0&&t<1&&u>=-EPS&&u<=1+EPS)ts.push(t);}
  else for(const p of [c,d])if(on(p,a,b))ts.push(Math.abs(dx)>Math.abs(dy)?(p[0]-a[0])/dx:(p[1]-a[1])/dy);
 }
 ts.sort((a,b)=>a-b);return ts.slice(1).every((t,i)=>{const m=(t+ts[i])/2;return inside([a[0]+dx*m,a[1]+dy*m],poly);});
}
const bounds=p=>[Math.min(...p.map(q=>q[0])),Math.min(...p.map(q=>q[1])),Math.max(...p.map(q=>q[0])),Math.max(...p.map(q=>q[1]))];
const rect=b=>[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]];
const overlap=(a,b)=>a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];
function textBox(e){const w=Array.from(e.value).length*e.height*1.2;return[e.pos[0]-.03,e.pos[1]-.35*e.height-.03,e.pos[0]+w+.03,e.pos[1]+1.2*e.height+.03];}
function containsBox(poly,b){return edges(rect(b)).every(([a,c])=>segmentInside(a,c,poly));}
function obstacleHit(box,es,story){return es.some(e=>{
 if(e.story!==story)return false;
 if(e.type==='text')return overlap(box,e.layoutBox||textBox(e));
 if(!/_WALL$/.test(e.layer)&&e.role!=='downhill-arrow')return false;
 const p=e.type==='line'?[e.a,e.b]:e.points;
 if(!p)return false;
 if(p.some(q=>inside(q,rect(box))))return true;
 if(e.closed&&rect(box).some(q=>inside(q,p)))return true;
 return (e.type==='line'?[[e.a,e.b]]:edges(p)).some(([a,b])=>edges(rect(box)).some(([c,d])=>proper(a,b,c,d)));
 });}
function wrap(value){const parts=value.split(/\s{2,}/);if(parts.length>1)return parts;const m=value.match(/^(h\s+[^ ]+)\s+(.*)$/);return m?[m[1],m[2]]:[value];}
function place(poly,story,layer,entities,out,value){
 const b=bounds(poly),all=[...entities,...out];
 const cx=(b[0]+b[2])/2,cy=(b[1]+b[3])/2;
 const candidates=[];for(let iy=0;iy<=20;iy++)for(let ix=0;ix<=20;ix++)candidates.push([b[0]+(ix+.5)/21*(b[2]-b[0]),b[1]+(iy+.5)/21*(b[3]-b[1])]);
 candidates.sort((a,b)=>Math.hypot(a[0]-cx,a[1]-cy)-Math.hypot(b[0]-cx,b[1]-cy));
 for(const h of [.18,.15,.12,.10,.08,.06])for(const lines of [[value],wrap(value)]){
  const w=Math.max(...lines.map(s=>Array.from(s).length))*h*1.2,dy=h*1.8;
  for(const c of candidates){const pos=[c[0]-w/2,c[1]+(lines.length-1)*dy/2];const texts=lines.map((s,i)=>({type:'text',story,layer,value:s,height:h,pos:[pos[0],pos[1]-i*dy]}));
   const boxes=texts.map(textBox);if(!boxes.every(q=>containsBox(poly,q)&&!obstacleHit(q,all,story)))continue;
   texts.forEach((t,i)=>{t.layoutBox=boxes[i];t.regionPolygon=poly;t.layoutStatus='inside-conservative-envelope';out.push(t);});
   return {pos,forced:false,height:h,lines,boxes,status:'inside-conservative-envelope'};
  }
 }
 // External callout is a documented exception. Search local sides, NEVER draw
 // an unchecked diagonal to a global gutter through unrelated rooms.
 const h=.10,w=Array.from(value).length*h*1.2,external=[];
 for(let k=0;k<=20;k++){
  const x=b[0]+k/20*(b[2]-b[0]),y=b[1]+k/20*(b[3]-b[1]);
  external.push({pos:[b[0]-.14-w,y],end:[b[0]-.08,y]},
    {pos:[b[2]+.14,y],end:[b[2]+.08,y]},
    {pos:[x-w/2,b[3]+.18],end:[x,b[3]+.08]},
    {pos:[x-w/2,b[1]-.25],end:[x,b[1]-.08]});
 }
 const lineClear=(a,c)=>!all.some(e=>{
  if(e.story!==story)return false;
  if(e.type==='text'){
   const r=rect(e.layoutBox||textBox(e));return inside(a,r)||inside(c,r)||edges(r).some(([p,q])=>proper(a,c,p,q));
  }
  if(!/_WALL$/.test(e.layer))return false;
  const p=e.type==='line'?[e.a,e.b]:e.points;if(!p)return false;
  if(e.closed&&(inside(a,p)||inside(c,p)))return true;
  return (e.type==='line'?[[e.a,e.b]]:edges(p)).some(([p,q])=>proper(a,c,p,q)||on(p,a,c)||on(q,a,c));
 });
 for(const choice of external){
  const t={type:'text',story,layer,value,height:h,pos:choice.pos,layoutStatus:'external-callout-local-leader'};
  const box=textBox(t);if(obstacleHit(box,all,story))continue;
  const anchors=candidates.filter(p=>inside(p,poly)).sort((a,b)=>Math.hypot(a[0]-choice.end[0],a[1]-choice.end[1])-Math.hypot(b[0]-choice.end[0],b[1]-choice.end[1]));
  const anchor=anchors.find(a=>lineClear(a,choice.end));if(!anchor)continue;
  t.layoutBox=box;out.push(t,{type:'line',story,layer,a:anchor,b:choice.end,role:'region-callout-leader'});
  return {pos:t.pos,forced:false,status:t.layoutStatus,boxes:[box]};
 }
 // Always preserve the annotation visibly, but never fabricate an unsafe leader.
 const xs=all.filter(e=>e.story===story).flatMap(e=>e.points?e.points.map(p=>p[0]):e.a?[e.a[0],e.b[0]]:e.pos?[textBox(e)[2]]:[]);
 const t={type:'text',story,layer,value:'UNRESOLVED '+value,height:.10,pos:[Math.max(b[2],...xs)+.5,b[3]],layoutStatus:'unresolved-visible-no-leader'};
 while(obstacleHit(textBox(t),all,story))t.pos[1]-=.4;
 t.layoutBox=textBox(t);out.push(t);
 return {pos:t.pos,forced:false,status:t.layoutStatus,value,boxes:[t.layoutBox]};

}
// Short downhill arrow; exact segment containment, no unicode, no room-wide diagonal.
function arrow(poly,dir,downhill,story,layer,out,record,obstacles=[]){
 if(!dir||downhill==='both')return false;
 const l=Math.hypot(...dir);if(l<1e-8)return false;
 const u=dir.map(v=>v/l*(downhill==='minus'?-1:1)),v=[-u[1],u[0]],b=bounds(poly);
 for(let iy=1;iy<10;iy++)for(let ix=1;ix<10;ix++){
  const c=[b[0]+ix/10*(b[2]-b[0]),b[1]+iy/10*(b[3]-b[1])];
  const tip=c.map((n,k)=>n+.14*u[k]),tail=c.map((n,k)=>n-.14*u[k]);
  const wings=[-1,1].map(s=>tip.map((n,k)=>n-.09*u[k]+s*.045*v[k]));
  const lines=[[tail,tip],...wings.map(p=>[tip,p])];
  if(!lines.every(([a,b])=>segmentInside(a,b,poly)))continue;
  if(lines.some(([a,b])=>obstacleHit(bounds([a,b]).map((n,i)=>n+(i<2?-.015:.015)),[...obstacles,...out],story)))continue;
  lines.forEach(([a,b])=>out.push({type:'line',story,layer,a,b,role:'downhill-arrow'}));record.slopeIndicatorLine=[tail,tip];record.slopeDownhillEnd=tip;return true;
 }
 return false;
}
module.exports={place,arrow,inside,segmentInside,containsBox,textBox,bounds};

// Candidate: reserve an own-sheet annotation rail before emitter packs sheets.
// Unresolved association stays unresolved; do not invent a leader.
function finalizeSheetAnnotations(entities){
 const stories=[...new Set(entities.map(e=>e.story))],result=[];
 for(const story of stories){
  const own=entities.filter(e=>e.story===story);
  const pending=own.filter(e=>e.type==='text'&&e.layoutStatus==='unresolved-visible-no-leader');
  const stable=own.filter(e=>!pending.includes(e));
  const boxOf=e=>e.type==='text'?(e.layoutBox||textBox(e)):e.type==='line'?bounds([e.a,e.b]):e.points?bounds(e.points):null;
  const boxes=stable.map(boxOf).filter(Boolean);
  if(!boxes.length)continue;
  let b=[Math.min(...boxes.map(q=>q[0])),Math.min(...boxes.map(q=>q[1])),Math.max(...boxes.map(q=>q[2])),Math.max(...boxes.map(q=>q[3]))];
  let strip=null;
  if(pending.length){
   const x=b[2]+.30,y=b[3]-.20;
   pending.forEach((e,i)=>{e.pos[0]=x;e.pos[1]=y-i*.40;const box=textBox(e);if(e.layoutBox)e.layoutBox.splice(0,4,...box);else e.layoutBox=box;e.annotationRole='unresolved-review';e.annotationStrip=true;});
   const p=pending.map(textBox);strip=[x-.03,Math.min(...p.map(q=>q[1]))-.15,Math.max(...p.map(q=>q[2]))+.15,b[3]];
   b=[Math.min(b[0],strip[0]),Math.min(b[1],strip[1]),Math.max(b[2],strip[2]),Math.max(b[3],strip[3])];
  }
  result.push({story,bounds:{minX:b[0],minY:b[1],maxX:b[2],maxY:b[3]},annotationStrip:strip});
 }
 return result;
}
module.exports.finalizeSheetAnnotations=finalizeSheetAnnotations;
