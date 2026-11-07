'use strict';
/** Independent conservative BOQ engine. Not a port of ArchiDrawing web/report-model.
 * API: buildReport(decodedCapture, sourceRoot={}); quantitiesCSV(report).
 * All geometry is source-space; alignment and DXF sheet offsets are never used.
 */
const ceilingReconstruct = require('./ceiling-reconstruct');
const planStatistics = require('./plan-statistics');
const handoffLib = require('./handoff');
const EPS = 1e-7;
const finite = v => typeof v === 'number' && Number.isFinite(v);
const pos = v => finite(v) && v > 0;
const sub = (a,b) => a.map((v,i)=>v-b[i]);
const dot = (a,b) => a.reduce((s,v,i)=>s+v*b[i],0);
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm = a => Math.hypot(...a);
const xyz = p => [p.x,p.y,p.z];
/**
 * SPEC section 4 measure, one shape for the whole report:
 *   { value, status, coverage, included, expected, reason }
 * `status` is PROVENANCE only (supplied|computed|reconstructed|estimated|
 * unavailable). `coverage` is COMPLETENESS only (complete|partial) and carries
 * the counts behind it. The two were a single field until 2026-11-07 (defect
 * C-6: `coverage` held 'computed', `status` held 'partial'), which made a
 * partial subtotal look like a provenance class.
 */
const PROVENANCE = ['supplied', 'computed', 'reconstructed', 'estimated', 'unavailable'];
const STATUS_ALIASES = { 'source-derived': 'supplied', 'complete': 'computed', 'partial': 'computed', 'explicit': 'supplied' };
function measure(value, status, reason = null, counts = null) {
  const ok = finite(value);
  let st = STATUS_ALIASES[status] || status;
  if (!PROVENANCE.includes(st)) st = ok ? 'computed' : 'unavailable';
  if (!ok) st = 'unavailable';
  const included = counts && finite(counts.included) ? counts.included : (ok ? 1 : 0);
  const expected = counts && finite(counts.expected) ? counts.expected : (ok ? 1 : 1);
  return {
    value: ok ? value : null,
    status: st,
    coverage: ok && expected > 0 && included >= expected ? 'complete' : 'partial',
    included, expected,
    reason: ok ? (reason || null) : (reason || 'value unavailable'),
  };
}
const missing = reason => measure(null, 'unavailable', reason);
function world(p,t) { return [0,1,2].map(i=>t[i]*p[0]+t[4+i]*p[1]+t[8+i]*p[2]+t[12+i]); }
function orient(a,b,c) { return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]); }
function onSegment(p,a,b,tol=EPS) {
 const d=[b[0]-a[0],b[1]-a[1]], l=Math.hypot(...d);
 return l>EPS && Math.abs(orient(a,b,p))/l<=tol && dot([p[0]-a[0],p[1]-a[1]],d)>=-tol*l && dot([p[0]-b[0],p[1]-b[1]],d)<=tol*l;
}
function intersects(a,b,c,d) {
 const x=orient(a,b,c),y=orient(a,b,d),z=orient(c,d,a),w=orient(c,d,b);
 return (x*y < -EPS*EPS && z*w < -EPS*EPS) || onSegment(c,a,b)||onSegment(d,a,b)||onSegment(a,c,d)||onSegment(b,c,d);
}
function inPolygon(p,poly,tol=EPS) {
 let yes=false;
 for(let i=0,j=poly.length-1;i<poly.length;j=i++) {
  const a=poly[j],b=poly[i]; if(onSegment(p,a,b,tol)) return true;
  if((a[1]>p[1])!==(b[1]>p[1]) && p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]) yes=!yes;
 }
 return yes;
}
/** Newell area with planarity and simple-polygon checks. Returns a plane basis. */
function polygon3D(points) {
 let p=points.map(q=>Array.isArray(q)?q:xyz(q));
 if(p.length>3 && norm(sub(p[0],p[p.length-1]))<EPS) p=p.slice(0,-1);
 if(p.length<3 || p.some(q=>q.length!==3||!q.every(finite))) return {error:'invalid or missing polygon'};
 let n=[0,0,0];
 for(let i=0;i<p.length;i++) {const a=p[i],b=p[(i+1)%p.length];n[0]+=(a[1]-b[1])*(a[2]+b[2]);n[1]+=(a[2]-b[2])*(a[0]+b[0]);n[2]+=(a[0]-b[0])*(a[1]+b[1]);}
 const len=norm(n); if(len<EPS) return {error:'degenerate polygon'};
 n=n.map(v=>v/len); const origin=p[0];
 if(p.some(q=>Math.abs(dot(sub(q,origin),n))>1e-5)) return {error:'nonplanar polygon'};
 const e=sub(p[1],origin),el=norm(e);if(el<EPS) return {error:'duplicate polygon vertex'};
 const u=e.map(v=>v/el),v=cross(n,u),project=q=>[dot(sub(q,origin),u),dot(sub(q,origin),v)];
 const poly=p.map(project);
 for(let i=0;i<p.length;i++) {
  if(norm(sub(p[i],p[(i+1)%p.length]))<EPS) return {error:'duplicate polygon vertex'};
  for(let j=i+1;j<p.length;j++) {if(j===i+1 || (i===0&&j===p.length-1))continue;if(intersects(poly[i],poly[(i+1)%p.length],poly[j],poly[(j+1)%p.length])) return {error:'self-intersecting polygon'};}
 }
 return {area:len/2,origin,u,v,n,poly,project};
}

/**
 * Local wall profile read from RAW polygonCorners (local x/y, before any
 * transform or projection): upper envelope by x, wall span W and full height H.
 * Slope evidence always comes from this polygon, never from dimensions.y.
 */
function wallProfile(surface) {
 const corners=Array.isArray(surface.polygonCorners)?surface.polygonCorners:null;
 if(!corners||corners.length<3)return null;
 const raw=corners.map(p=>[p.x,p.y]);
 if(raw.some(q=>!q.every(finite)))return null;
 const minY=Math.min(...raw.map(q=>q[1])),maxY=Math.max(...raw.map(q=>q[1]));
 const byX=new Map();
 for(const [x,y] of raw){const k=Math.round(x*100);if(!byX.has(k)||y>byX.get(k)[1])byX.set(k,[x,y]);}
 const pts=[...byX.values()].sort((a,b)=>a[0]-b[0]);
 if(pts.length<2)return null;
 return {pts,minY,maxY,W:pts[pts.length-1][0]-pts[0][0],H:maxY-minY};
}
function convexProfile(pts) {
 const signs=[];
 for(let i=0;i<pts.length;i++){
  const a=pts[i],b=pts[(i+1)%pts.length],c=pts[(i+2)%pts.length];
  const o=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  if(Math.abs(o)>1e-9)signs.push(o>0?1:-1);
 }
 return signs.every(v=>v===signs[0]);
}
/**
 * Slope cut of a wall: the roof takes one triangle out of the wall rectangle
 * per sloping segment, so gross = W*H - SUM(dW*dH/2). `computed` only when the
 * profile is convex with one or two slopes; otherwise `estimated`, always with
 * the triangles and the note that explains the arithmetic.
 */
function slopeCutOf(surface) {
 const d=surface.dimensions||{};
 const rectGross=pos(d.x)&&pos(d.y)?d.x*d.y:null;
 const pr=wallProfile(surface);
 if(!pr)return {status:'unavailable',cutArea:null,triangles:[],ridgeHeight:null,kneeHeight:null,slopeCount:0,
  flatGrossArea:rectGross,correctedGrossArea:rectGross,
  note:'no local polygonCorners profile: gross falls back to the W*H rectangle, no slope cut available'};
 const triangles=[];
 for(let i=0;i<pr.pts.length-1;i++){
  const dW=Math.abs(pr.pts[i+1][0]-pr.pts[i][0]),dH=Math.abs(pr.pts[i+1][1]-pr.pts[i][1]);
  if(dH>0.02)triangles.push({dW,dH,area:dW*dH/2});
 }
 const cutArea=triangles.reduce((a,t)=>a+t.area,0);
 const flatGrossArea=pr.W*pr.H;
 const correctedGrossArea=flatGrossArea-cutArea;
 const slopeCount=triangles.length;
 const convex=convexProfile(pr.pts);
 const status=(pr.W>0&&pr.H>0&&convex&&slopeCount<=2)?'computed':'estimated';
 const eq=triangles.map(t=>`(${t.dW.toFixed(3)}x${t.dH.toFixed(3)})/2`).join(' + ');
 return {status,cutArea,triangles,ridgeHeight:pr.H,kneeHeight:Math.min(...pr.pts.map(p=>p[1]))-pr.minY,
  slopeCount,convex,flatGrossArea,correctedGrossArea,
  note:slopeCount?`gross = W*H (${pr.W.toFixed(3)}x${pr.H.toFixed(3)} = ${flatGrossArea.toFixed(3)} m2) - ${eq} = ${correctedGrossArea.toFixed(3)} m2; slope read from the local polygonCorners top edge, not dimensions.y`
   :`no sloping top segment (W*H = ${flatGrossArea.toFixed(3)} m2)`};
}

function rigid(t) {
 if(!Array.isArray(t)||t.length!==16||!t.every(finite))return false;
 const a=t.slice(0,3),b=t.slice(4,7),c=t.slice(8,11);
 return [a,b,c].every(q=>Math.abs(norm(q)-1)<1e-5)&&Math.abs(dot(a,b))<1e-5&&Math.abs(dot(a,c))<1e-5&&Math.abs(dot(b,c))<1e-5;
}
function geometry(s) {
 if(s.curve) return {error:'curved surface unsupported'};
 if(!rigid(s.transform))return {error:'non-rigid or missing transform unsupported'};
 if(s.polygonCorners?.length) {
  const g=polygon3D(s.polygonCorners.map(p=>world(xyz(p),s.transform)));
  return g.error?g:{...g,coverage:'computed',method:'verified planar polygon; Newell 3D area'};
 }
 const d=s.dimensions||{};
 if(s.kind==='floor') {
  // RoomPlan floor dimensions are a bounding box, never ceiling height.
  if(/placeholder/.test(s.dimensionsProvenance||'')) return {error:'missing floor polygon; generated DXF dimensions are not quantities'};
  const dims=[d.x,d.y,d.z].filter(pos).sort((a,b)=>b-a);
  return dims.length>=2?{area:dims[0]*dims[1],coverage:'estimated',method:'floor dimensional bounding box; not measured polygon',estimateOnly:true}:{error:'missing floor polygon and usable bounding box'};
 }
 if(!pos(d.x)||!pos(d.y))return {error:'missing positive width/height'};
 const pts=[[-d.x/2,-d.y/2,0],[d.x/2,-d.y/2,0],[d.x/2,d.y/2,0],[-d.x/2,d.y/2,0]].map(p=>world(p,s.transform));
 const g=polygon3D(pts);
 return {...g,coverage:'estimated',method:'source dimensions x*y; rectangular planar model assumption',rectangle:true};
}
function rawRooms(root) {
 if(Array.isArray(root.walls))return [root];
 if(Array.isArray(root.rooms))return root.rooms;
 if(Array.isArray(root.captureSessions))return root.captureSessions.flatMap(c=>c.roomplanSessions||[]);
 return [];
}
/** Trade convention, NOT geometry: when a wall is painted, an opening up to this
 * size is not deducted at all — the time saved on the hole is spent right back
 * on its reveals, corners and masking. Above it only the excess comes off (a
 * 4 m2 opening deducts 1 m2). Paint area is a SEPARATE field: `netArea` stays
 * the geometrically honest number and is what cross-checks against a survey;
 * this one is what goes into a quote. Ported from geometry.js
 * `PAINT_FREE_OPENING_M2` / `wallPaintArea` (SPEC section 5, G-11). */
const PAINT_FREE_OPENING_M2=3;
/** Paint measure for one wall: gross minus the excess above the threshold, per
 * opening, clamped at zero. Unknown opening area => null, never a free pass. */
function paintMeasure(grossMeasure,openings) {
 const areas=openings.map(o=>o&&o.area);
 if(!grossMeasure||!finite(grossMeasure.value))return missing('gross wall area unavailable; paint area cannot be derived');
 if(areas.some(a=>!finite(a)))return missing('parent-linked opening without a finite area; paint deduction unknown');
 const excess=areas.reduce((s,a)=>s+Math.max(0,a-PAINT_FREE_OPENING_M2),0);
 const value=Math.max(0,grossMeasure.value-Math.min(excess,grossMeasure.value));
 const estimated=grossMeasure.coverage==='estimated'||openings.some(o=>o&&o.coverage==='estimated');
 return measure(value,estimated?'estimated':'computed',`gross minus ${excess>0?'the excess above':'nothing (all openings at or below)'} PAINT_FREE_OPENING_M2=${PAINT_FREE_OPENING_M2} m2 per linked parent-linked opening; trade rule, not net area`);
}
/**
 * Subtotal measure. A subtotal is `complete` only when every expected row
 * produced a value; otherwise `partial` with included/expected. `status` stays a
 * provenance class (SPEC section 4) — partiality lives in `coverage`, never in
 * `status`, so a consumer can never mistake an incomplete sum for a class of
 * measurement.
 */
function sum(rows,key,label) {
 const what=label||key;
 if(!rows.length)return {...missing(`no applicable source elements for ${what}`),included:0,expected:0};
 const values=rows.map(r=>r[key]),ok=values.filter(q=>q&&finite(q.value));
 const reasons=[...new Set(values.filter(q=>!q||!finite(q.value)).map(q=>q?.reason||'missing measure'))];
 if(!ok.length)return {value:null,status:'unavailable',coverage:'partial',included:0,expected:rows.length,
  reason:`${what}: no measurable value (${reasons.join('; ')||'all reasons empty'})`};
 const st=ok.some(q=>q.status==='estimated')?'estimated':ok.some(q=>q.status==='reconstructed')?'reconstructed':ok.every(q=>q.status==='supplied')?'supplied':'computed';
 const complete=ok.length===rows.length;
 return {value:ok.reduce((s,q)=>s+q.value,0),status:st,coverage:complete?'complete':'partial',included:ok.length,expected:rows.length,
  reason:complete?`sum of ${ok.length} ${st} ${what} measure(s)`:`${what}: ${ok.length} of ${rows.length} measured; ${reasons.join('; ')}`};
}
/** Wall run length: source length first, polygonCorners span as the fallback. */
function runLength(surface) {
 const d=surface.dimensions||{};
 if(pos(d.x))return measure(d.x,'supplied','source wall length (dimensions.x)');
 const pr=wallProfile(surface);
 if(pr&&pos(pr.W))return measure(pr.W,'computed','wall span read from the local polygonCorners profile');
 return missing('wall run length unavailable: no dimensions.x and no polygonCorners profile');
}
function buildReport(capture,root={}) {
 const warnings=[],ceilingZones=ceilingReconstruct.zoneCeilings(capture);
 /** Structured warning (SPEC section 3): message and severity are mandatory, a
  * code is stable, extra fields (roomIdentifier, differenceM2) are kept. */
 const warn=(code,message,severity='warning',extra={})=>{warnings.push({code,message,severity,...extra});};
 let livingAreaInput=null;
 /** SPEC section 3 assumptions[]: plain strings, one assumption each. The old
  * conventions.caveat string lives here now (defect C-1). */
 const assumptions=[
  'Room-side quantities are references and not additive: a shared wall appears once in the totals and on both room sides.',
  'No surveyed accuracy is claimed; source geometry is trusted only as far as the producer wrote it.',
  'Ceiling areas are reconstructed from wall-top profiles unless the producer supplies a ceiling polygon; a supplied ceiling always wins.',
  'Paint area follows a trade rule (an opening up to '+PAINT_FREE_OPENING_M2+' m2 is not deducted, above it only the excess); net area keeps the full geometric deduction.',
  'No complete native-app support and no volume inference: volume stays null with a reason instead of a guess.',
 ];
 /**
  * Ceiling measure for one room: explicit source polygon first, then the
  * wall-top reconstruction, then unavailable. `status` uses the ceiling
  * vocabulary (supplied / reconstructed / reconstructed-bound / estimated /
  * unavailable); `coverage` keeps the report-wide vocabulary
  * (source-derived / computed / estimated / unavailable).
  */
 /**
  * Ceiling measure for one room: explicit source polygon first, then the
  * wall-top reconstruction, then unavailable. `status` is provenance
  * (supplied / reconstructed / estimated / unavailable); `coverage` is
  * `complete` unless the reconstruction only covered part of the room.
  * `method` is the SPEC section 3 enum: supplied|knee|section|extrusion|flat|unavailable.
  */
 function ceilingMeasureFor(identifier,sourceRoomIndex){
  const zone=(identifier!=null?ceilingZones.find(z=>z.roomIdentifier===identifier):null)||
   (sourceRoomIndex!=null?ceilingZones.find(z=>z.sourceRoomIndex===sourceRoomIndex):null)||null;
  const toMethod=(z)=>{
   if(!z)return 'unavailable';
   if(z.source==='explicit'||z.method==='explicit')return 'supplied';
   return ['knee','section','extrusion','flat','supplied','unavailable'].includes(z.method)?z.method:'unavailable';
  };
  if(!zone)return {...missing('no room/zone wall geometry to derive a ceiling from'),method:toMethod(null),basis:null,heightM:null};
  const m=measure(finite(zone.ceilingArea)?zone.ceilingArea:null,zone.status||'reconstructed',zone.reason||'ceiling area unavailable');
  return {value:m.value,status:m.status,coverage:m.coverage,included:m.included,expected:m.expected,reason:m.reason,
   method:m.value==null?'unavailable':toMethod(zone),
   basis:zone.source==='explicit'?'explicit source ceiling polygon; wall-top reconstruction not run':'wall-profile ceiling reconstruction',
   heightM:finite(zone.heightMin)&&finite(zone.heightMax)?{min:zone.heightMin,max:zone.heightMax}:null};
 }
 const rooms=(capture.rooms||rawRooms(root)).map((r,i)=>{
  const polygonXZ=r.polygonXZ||r.vertices||null, curved=r.curvedEdges?.length||r.curved_edges?.length;
  const pg=polygonXZ&&!curved?polygon3D(polygonXZ.map(v=>[v.x,0,v.z])):{error:curved?'curved room boundary unsupported':'source room polygon absent'};
  const declaredValue=finite(r.declaredArea)?r.declaredArea:(finite(r.area)?r.area:null);
  const declared=declaredValue!=null?measure(declaredValue,'supplied','source room area (declaredArea); separate from the computed polygon'):missing('source room area absent');
  const derived=pg.error?missing(pg.error):measure(pg.area,'computed','source XZ polygon; Newell area');
  const discrepancy=declared.value!=null&&derived.value!=null?derived.value-declared.value:null;
  const identifier=r.identifier??r.id??`source-room:${i}`;
  return {id:identifier,identifier,sourceRoomIndex:r.sourceRoomIndex??i,story:r.story??null,label:r.label??null,
   declaredArea:declared,polygonArea:derived,polygonMinusDeclared:discrepancy,
   ceilingArea:ceilingMeasureFor(r.identifier??r.id??null,r.sourceRoomIndex??i),
   volume:missing('closed verified volume geometry unavailable'),
   _vertices:pg.error?null:polygonXZ,_source:r};
 });
 const all=[...(capture.surfaces||[]),...(capture.objects||[])],groups=new Map();
 all.forEach((s,i)=>{const key=s.identifier?`${s.kind||'object'}:${s.identifier}`:`anonymous:${i}`;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(s);});
 const elements=[],geometries=new Map();
 for(const [key,records] of groups) {
  const s=records[0],kind=s.kind||'object', stories=[...new Set(records.map(q=>q.story??null))],conflict=records.some(q=>JSON.stringify([q.dimensions,q.transform,q.polygonCorners,q.curve,q.parentIdentifier])!==JSON.stringify([s.dimensions,s.transform,s.polygonCorners,s.curve,s.parentIdentifier]));
  const g=kind==='object'?{error:'furniture has count, no surface quantity'}:geometry(s);
  if(conflict)g.error='conflicting records for same source identifier';
  if(stories.length!==1)g.error='same identifier assigned to conflicting stories';
  const slopeCut=kind==='wall'?slopeCutOf(s):null;
  const grossBase=g.error||!slopeCut?null:slopeCut;
  const e={id:key,identifier:s.identifier??null,kind,category:s.category??null,story:stories.length===1?stories[0]:null,sourceStory:s.sourceStory??null,storyProvenance:s.sourceStoryProvenance||capture.storyAssignmentMethod||'source or decoder assignment',parentIdentifier:s.parentIdentifier??null,sourceRecords:records.map(q=>({sourceRecordIndex:q.sourceRecordIndex??null,sourceRoomIndex:q.sourceRoomIndex??null,sourceRoomIdentifier:q.sourceRoomIdentifier??null})),count:1,roomRefs:[],length:runLength(s),area:(()=>{
   if(g.error)return missing(g.error);
   if(!slopeCut||slopeCut.correctedGrossArea==null)return measure(g.area,g.coverage,g.method);
   if(slopeCut.status==='computed'&&Math.abs(slopeCut.correctedGrossArea-g.area)<=0.02)
    return measure(slopeCut.correctedGrossArea,'computed',slopeCut.note);
   if(Math.abs((slopeCut.correctedGrossArea??g.area)-g.area)>0.02)
    return measure(g.area,'estimated',`slope-cut gross ${slopeCut.correctedGrossArea.toFixed(3)} m2 disagrees with the verified polygon area ${g.area.toFixed(3)} m2; polygon area kept, slope cut reported separately`);
   return measure(g.area,g.coverage,g.method);
  })(),slopeCut,netArea:missing(kind==='wall'?'not evaluated':'not applicable'),thickness:pos(s.wallThickness)?measure(s.wallThickness,'supplied','source.wallThickness'):pos(s.dimensions?.z)&&kind==='wall'?measure(s.dimensions.z,'supplied','source.dimensions.z'):missing('source thickness absent; DXF fallback not used'),notes:[]};
  if(g.error&&kind!=='object')e.notes.push(g.error);
  if(g.coverage==='estimated')e.notes.push(g.method);
  for(const room of rooms) {
   const sourceLink=records.some(q=>q.sourceRoomIndex!=null&&q.sourceRoomIndex===room.sourceRoomIndex || q.sourceRoomIdentifier!=null&&q.sourceRoomIdentifier===room.identifier);
   const rr=room._source;
   const explicit=(rr.edges||[]).flat(Infinity).includes(s.identifier)||['doorIdentifiers','windowIdentifiers','openingIdentifiers','doors','windows','openings'].some(k=>Array.isArray(rr[k])&&rr[k].includes(s.identifier));
   if(sourceLink||explicit) {e.roomRefs.push({roomIdentifier:room.identifier,coverage:'supplied',method:sourceLink?'source-room record linkage':'source room identifier references'});continue;}
   if(capture.kind==='optimized'&&room._vertices&&room.story===e.story&&rigid(s.transform)) {
    const poly=room._vertices.map(v=>[v.x,v.z]), center=[s.transform[12],s.transform[14]];
    // Walls require both endpoints and midpoint, not centroid alone. Boundary
    // tolerance intentionally admits references to both adjacent rooms.
    const points=kind==='wall'&&pos(s.dimensions?.x)?[-0.5,0,0.5].map(t=>world([t*s.dimensions.x,0,0],s.transform)).map(p=>[p[0],p[2]]):[center];
    if(points.every(p=>inPolygon(p,poly,0.02)))e.roomRefs.push({roomIdentifier:room.identifier,coverage:'inferred',method:'source-space point-in-polygon; 0.02m boundary tolerance; not measured membership'});
   }
  }
  elements.push(e);geometries.set(key,{g,s});
 }
 const apertures=elements.filter(e=>['door','window','opening'].includes(e.kind));
 for(const wall of elements.filter(e=>e.kind==='wall')) {
  const {g}=geometries.get(wall.id),linked=apertures.filter(e=>e.parentIdentifier===wall.identifier&&wall.identifier!=null);
  wall.openingIds=linked.map(e=>e.id);
  wall.openingDiagnostics=[];
  if(!g.error&&!g.estimateOnly)for(const opening of linked){const og=geometries.get(opening.id).g;if(!og.error&&og.poly)wall.openingDiagnostics.push(require('./wall-diagnostics').diagnose(geometries.get(wall.id).s,geometries.get(opening.id).s,g,og,inPolygon));}
  if(wall.slopeCut&&wall.slopeCut.status!=='computed'&&wall.slopeCut.status!=='unavailable')wall.notes.push(`slope cut ${wall.slopeCut.status}: ${wall.slopeCut.note}`);
  if(g.error||g.estimateOnly) {wall.netArea=missing(g.error||'wall plane unavailable');continue;}
  let failure=null; const projected=[];
  // Restrict subtraction to convex wall boundaries; concave clipping is not implemented.
  const turns=g.poly.map((p,i)=>orient(p,g.poly[(i+1)%g.poly.length],g.poly[(i+2)%g.poly.length])).filter(v=>Math.abs(v)>EPS);
  const convex=turns.every(v=>v>0)||turns.every(v=>v<0);
  if(linked.length&&!convex)failure='opening subtraction for concave wall unsupported';
  for(const opening of linked) {
   const og=geometries.get(opening.id).g;
   if(opening.story!==wall.story){failure='parent-linked opening on different story';break;}
   if(og.error||!og.poly){failure='parent-linked opening geometry unavailable';break;}
   // Opening local surfaces must be coplanar with wall, not merely have a matching ID.
   const points=og.poly.map(p=>og.origin.map((v,i)=>v+og.u[i]*p[0]+og.v[i]*p[1]));
   if(points.some(p=>Math.abs(dot(sub(p,g.origin),g.n))>0.01)) {failure='parent-linked opening not coplanar within 0.01m';break;}
   let poly=points.map(g.project),subtractionArea=og.area;
   const diagnostic=wall.openingDiagnostics.find(d=>d.openingKey===opening.id);
   if(!poly.every(p=>inPolygon(p,g.poly,EPS))) {
    // Do NOT increase EPS or silently subtract the full opening. For dimensional
    // rectangles only, exact convex intersection may repair sub-micrometre
    // source-rounding overflow. Larger or polygonal mismatches remain unknown.
    if(g.rectangle&&og.rectangle&&convex&&diagnostic?.intersectionAreaM2>0&&diagnostic.maxOutsideDistanceM<=1e-6&&diagnostic.outsideAreaM2<=1e-5){
     poly=diagnostic.intersectionPolygonM;subtractionArea=diagnostic.intersectionAreaM2;
     diagnostic.netPolicy='exact convex intersection of dimensional rectangles; estimated geometry; only <=1e-6m overflow and <=1e-5m2 outside; original opening and outside area retained';
     diagnostic.clippingApplied=true;
     wall.notes.push('sub-micrometre dimensional rounding overflow: exact clipped intersection subtracted; outside area retained in openingDiagnostics');
    }else {failure='parent-linked opening outside wall boundary';break;}
   }
   const box=[Math.min(...poly.map(p=>p[0])),Math.max(...poly.map(p=>p[0])),Math.min(...poly.map(p=>p[1])),Math.max(...poly.map(p=>p[1]))];
   // Deliberately conservative: overlapping bounding boxes refuse a net rather
   // than risk subtracting two openings twice; no approximate polygon union.
   if(projected.some(q=>Math.min(q.box[1],box[1])-Math.max(q.box[0],box[0])>EPS&&Math.min(q.box[3],box[3])-Math.max(q.box[2],box[2])>EPS)) {failure='overlapping opening projections/bounds; union unsupported';break;}
   projected.push({box,area:subtractionArea,coverage:og.coverage});
  }
  // Openings are subtracted from the CORRECTED gross (slope cut applied), not
  // from the full W*H rectangle: otherwise a gable wall's net is overstated by
  // whatever the roof cut away.
  const netBase=finite(wall.area.value)?wall.area.value:g.area;
  const net=netBase-projected.reduce((s,q)=>s+q.area,0);
  if(net < -EPS)failure='negative net wall area refused';
  wall.netArea=failure?missing(failure):measure(Math.max(0,net),g.coverage==='estimated'||projected.some(q=>q.coverage==='estimated')?'estimated':'computed','gross minus verified contained or explicitly diagnostic-clipped dimensional-rounding intersections; coplanar parent-linked nonoverlapping openings');
  if(failure)wall.notes.push(failure);
 }
 for(const a of apertures) {
  const parents=elements.filter(e=>e.kind==='wall'&&e.identifier===a.parentIdentifier&&a.parentIdentifier!=null);
  a.parentLinkStatus=parents.length===1?'linked':parents.length?'ambiguous':'unlinked';
  if(a.parentLinkStatus!=='linked')a.notes.push('opening not subtracted: '+a.parentLinkStatus+' parentIdentifier');
 }
 // Paint area per wall: a SEPARATE field next to netArea, never folded into it.
 // Same parent-linked openings as net (one wall, unambiguous parent); the trade
 // threshold is applied to each opening separately, so two 2 m2 openings deduct
 // nothing while one 4 m2 opening deducts 1 m2.
 for(const wall of elements.filter(e=>e.kind==='wall')) {
  const linked=apertures.filter(e=>e.parentIdentifier===wall.identifier&&wall.identifier!=null);
  wall.paintArea=paintMeasure(wall.area,linked.map(e=>({area:e.area.value,coverage:e.area.coverage})));
  wall.paintRule={thresholdM2:PAINT_FREE_OPENING_M2,freeOpeningM2:PAINT_FREE_OPENING_M2,deductedM2:finite(wall.area.value)&&finite(wall.paintArea.value)?wall.area.value-wall.paintArea.value:null,policy:'an opening up to PAINT_FREE_OPENING_M2 is not deducted; above it only the excess is deducted; net area keeps the full geometric deduction'};
 }
 /** Ceiling subtotal: only rooms/zones with an area contribute; anything
  * missing makes the subtotal 'partial' rather than silently complete. */
 /**
  * Ceiling subtotal: only rooms/zones with an area contribute; anything
  * missing makes the subtotal `partial` rather than silently complete.
  * `status` is the provenance of the contributing zones.
  */
 function ceilingSummary(zones){
  const byStatus={};for(const z of zones)if(z.status)byStatus[z.status]=(byStatus[z.status]||0)+1;
  const known=zones.filter(z=>finite(z.ceilingArea));
  if(!zones.length)return {...missing('no room/zone geometry to derive a ceiling from'),included:0,expected:0,byStatus};
  if(!known.length)return {value:null,status:'unavailable',coverage:'partial',included:0,expected:zones.length,byStatus,reason:[...new Set(zones.map(z=>z.reason||'ceiling area unavailable'))].join('; ')};
  const suppliedOnly=known.every(z=>z.source==='explicit');
  const anyEstimated=known.some(z=>z.status==='estimated');
  const st=suppliedOnly?'supplied':anyEstimated?'estimated':'reconstructed';
  const complete=known.length===zones.length;
  return {value:known.reduce((s,z)=>s+z.ceilingArea,0),status:st,coverage:complete?'complete':'partial',
   included:known.length,expected:zones.length,byStatus,
   reason:complete?`sum of ${known.length} ${st} ceiling area(s)`:known.length+' of '+zones.length+' ceilings measured; '+[...new Set(zones.filter(z=>!finite(z.ceilingArea)).map(z=>z.reason||'ceiling area unavailable'))].join('; ')};
 }
 function totals(list,story) {
  const zones=story===undefined?ceilingZones:ceilingZones.filter(z=>z.story===story);
  const select=k=>list.filter(e=>e.kind===k),walls=select('wall');
  const apertures=list.filter(e=>['door','window','opening'].includes(e.kind));
  const unlinked=apertures.filter(e=>e.parentLinkStatus!=='linked');
  const net=sum(walls,'netArea','wall net area');
  if(unlinked.length){net.coverage='partial';net.reason=`${net.reason}; unlinked/ambiguous openings excluded from subtraction, so net coverage is incomplete`;}
  const paint=sum(walls,'paintArea','paint area');
  if(unlinked.length){paint.coverage='partial';paint.reason=`${paint.reason}; unlinked/ambiguous openings cannot be deducted, so paint coverage is incomplete`;}
  const roomList=story===undefined?rooms:rooms.filter(r=>r.story===story);
  const withoutArea=roomList.filter(r=>!(r.polygonArea&&finite(r.polygonArea.value))&&!(r.declaredArea&&finite(r.declaredArea.value))).length;
  const living=(()=>{
   if(story!==undefined)return missing('living area is reported per level in the statistics block; not re-derived per story here');
   // A room with no measurable area must not make the building living area look
   // complete: zero rooms measured is unavailable, some rooms measured is
   // partial, and only every room measured is complete (SPEC section 4).
   if(livingAreaInput&&finite(livingAreaInput.value)){
    const measured=roomList.length-withoutArea;
    if(roomList.length>0&&measured===0)return missing(`${withoutArea} of ${roomList.length} room(s) have no measurable area (no polygon and no declared area); living area is unknown, not zero`);
    return measure(livingAreaInput.value,'computed','plan-statistics totals.livingArea: interior floor area per room, wall footprints removed (G-9)',{included:roomList.length?measured:undefined,expected:roomList.length||undefined});
   }
   return missing(livingAreaInput&&livingAreaInput.reason?livingAreaInput.reason:'living area requires zone/type classification; see the statistics block');
  })();
  return {
   floorArea:sum(select('floor'),'area','floor area'),
   ceilingArea:ceilingSummary(zones),
   wallAreaGross:sum(walls,'area','wall gross area'),
   wallAreaNet:net,
   openingArea:sum(apertures,'area','opening area'),
   wallLength:sum(walls,'length','wall run length'),
   paintArea:paint,
   livingArea:living,
   roomsWithoutArea:measure(withoutArea,'computed',`${withoutArea} of ${roomList.length} room(s) have neither a computed polygon area nor a declared area`,{included:roomList.length-withoutArea,expected:roomList.length}),
   volume:missing('verified closed volume geometry unavailable'),
   doorArea:sum(select('door'),'area','door area'),
   windowArea:sum(select('window'),'area','window area'),
   uniqueElementCount:list.length,
   counts:{
    roomCount:roomList.length,
    wallCount:walls.length,
    doorCount:select('door').length,
    windowCount:select('window').length,
    objectCount:select('object').length,
    floorCount:select('floor').length,
    openingCount:select('opening').length,
    elementCount:list.length,
   },
   unlinkedOpeningIds:unlinked.map(e=>e.id),
  };
 }
 /** SPEC section 6: one kernel, many outputs. The statistics (G-9) and handoff
  * (G-10) blocks are computed from the same capture and written INSIDE
  * report-v1, so a consumer never has to re-derive them. A failure is a warning,
  * never a silent omission and never a thrown report. */
 let statisticsBlock=null,handoffBlock=null;
 try{
  const ps=planStatistics.planStatistics(capture);
  if(ps&&ps.ok&&ps.statistics){
   statisticsBlock=ps.statistics;
   const la=ps.statistics.totals&&ps.statistics.totals.livingArea;
   livingAreaInput=finite(la)?{value:la}:{reason:'plan-statistics could not measure a living area for this capture'};
  }else livingAreaInput={reason:`plan-statistics refused the capture${ps&&ps.reason?`: ${ps.reason}`:''}`};
 }catch(e){livingAreaInput={reason:`plan-statistics threw: ${e.message}`};warn('statistics-unavailable',`plan-statistics failed: ${e.message}`,'warning');}
 try{
  const ho=handoffLib.handoff(capture);
  if(ho&&ho.ok)handoffBlock=ho.scope;
  else warn('handoff-unavailable',`handoff refused the capture${ho&&ho.reason?`: ${ho.reason}`:''}`,'warning');
 }catch(e){warn('handoff-unavailable',`handoff failed: ${e.message}`,'warning');}

 const storyIds=[...new Set([...elements.map(e=>e.story),...rooms.map(r=>r.story)])];
 const stories=storyIds.map(story=>({story,totals:totals(elements.filter(e=>e.story===story),story),rooms:rooms.filter(r=>r.story===story).map(r=>r.identifier)}));
 for(const room of rooms) {
  const sides=elements.filter(e=>e.roomRefs.some(m=>m.roomIdentifier===room.identifier));
  room.elementIds=sides.map(e=>e.id);room.roomSideCounts=Object.fromEntries(['wall','floor','door','window','opening','object'].map(k=>[k,sides.filter(e=>e.kind===k).length]));
  room.roomSideWallGrossAreaM2=sum(sides.filter(e=>e.kind==='wall'),'area');
  delete room._vertices;delete room._source;
  if(room.polygonMinusDeclared!=null&&Math.abs(room.polygonMinusDeclared)>0.01)warn('room-area-discrepancy',`room ${room.identifier}: computed polygon area differs from the declared area by ${room.polygonMinusDeclared.toFixed(3)} m2`,'warning',{roomIdentifier:room.identifier,differenceM2:room.polygonMinusDeclared});
 }
 /**
  * report-v1 (SPEC section 3). Canonical names, canonical measure shape:
  * totals are the building takeoff, elements are the flat line list, rooms and
  * stories are the per-room view, assumptions[] is what we had to assume and
  * warnings[] is what we could not measure. `statistics` and `handoff` are the
  * two specialist blocks (G-9, G-10) carried inside the same document.
  */
 const report={
  schemaVersion:'roomplan.report/1',
  engine:'independent conservative quantities engine; not ported or compared to unavailable ArchiDrawing web engine',
  source:{
   sha256:capture.sourceSHA256??capture.source?.sha256??null,
   byteCount:capture.sourceByteCount??capture.source?.bytes??capture.source?.byteCount??null,
   dialect:capture.dialect?.name??capture.dialect?.kind??capture.source?.dialect??capture.kind??null,
   captureSchema:'roomplan.capture/1',
  },
  conventions:{
   units:'metres',areaUnits:'m2',
   measureShape:'{value,status,coverage,included,expected,reason}; status=provenance supplied|computed|reconstructed|estimated|unavailable; coverage=completeness complete|partial with included/expected counts',
   coordinateSpace:'source space; local surface transforms applied; alignment and DXF sheet translations not used',
   roomMembership:'source links first; polygon inference explicitly inferred; shared walls have multiple room references but one unique total',
   netOpeningToleranceM:0.01,roomBoundaryToleranceM:0.02,
   paintFreeOpeningM2:PAINT_FREE_OPENING_M2,
   paintPolicy:'trade rule, separate from netArea: an opening up to paintFreeOpeningM2 is not deducted, above it only the excess; never folded into net',
  },
  assumptions,
  sourceReferences:{floorAreaSquareMetres:finite(root&&root.floorAreaSquareMetres)?root.floorAreaSquareMetres:null,floorAreaPolicy:'metadata reference only; never added to geometry totals'},
  rooms,elements,stories,
  totals:totals(elements),
  statistics:statisticsBlock,
  handoff:handoffBlock,
  warnings,
 };
 report.summary={
  sourceSHA256:report.source.sha256,
  roomCount:rooms.length,
  ceilingArea:report.totals.ceilingArea,
  storyCount:stories.length,
  uniqueElementCount:elements.length,
  counts:report.totals.counts,
  floorArea:report.totals.floorArea,
  wallAreaGross:report.totals.wallAreaGross,
  wallAreaNet:report.totals.wallAreaNet,
  paintArea:report.totals.paintArea,
  warningCount:warnings.length+elements.reduce((n,e)=>n+e.notes.length,0),
  caveat:'Room-side quantities are references and not additive. No surveyed accuracy, complete app support, ceiling inference or volume inference claimed.',
 };
 return report;
}
/** Guard strings before RFC4180-style quoting; BOM and semicolon for spreadsheets. */
function csvCell(v) {
 let s=v==null?'':typeof v==='object'?JSON.stringify(v):String(v);
 if(typeof v!=='number'&&/^[\s\uFEFF]*[=+\-@]/u.test(s))s="'"+s;
 return /[;"\r\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s;
}
function quantitiesCSV(report) {
 const header=['Kat','Tip','ID','Izvorni_ID','Kategorija','Broj','Povrsina_bruto_m2','Bruto_pokrivenost','Povrsina_neto_m2','Neto_pokrivenost','Povrsina_bojanje_m2','Bojanje_pokrivenost','Bojanje_odbijeno_m2','Debljina_m','Debljina_pokrivenost','Sobe_reference','Provenance','Napomena'];
 const rows=report.elements.map(e=>[e.story,e.kind,e.id,e.identifier,e.category,e.count,e.id,e.identifier,e.category,e.count,e.area.value,e.area.status,e.netArea.value,e.netArea.status,e.paintArea?e.paintArea.value:null,e.paintArea?e.paintArea.status:null,e.paintRule?e.paintRule.deductedM2:null,e.thickness.value,e.thickness.status,e.roomRefs,e.sourceRecords,e.notes.join(' | ')]);
 return '\uFEFF'+[header,...rows].map(r=>r.map(csvCell).join(';')).join('\r\n')+'\r\n';
}
module.exports={buildReport,quantitiesCSV,csvCell,polygon3D,inPolygon,PAINT_FREE_OPENING_M2,paintMeasure};
