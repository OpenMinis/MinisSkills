'use strict';
/** Ceiling annotations: explicit source ceilings first, wall-top reconstruction
 * only as a fallback (never over an explicit polygon).
 * Source transform once -> source world -> alignment once -> DXF projection.
 * Drawing offsets never feed back into wall/floor quantities.
 */
const {polygon3D,inPolygon}=require('./quantities');
const {apply,project}=require('./transform');
const recon=require('./ceiling-reconstruct');
const {splitCeilingPlan}=require('./ceiling-3d');
const I=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const finite=Number.isFinite;
const OFFSET_M=0.03, TRIM_M=0.03;
function world(p,t){return apply(t,p);}
function sourcePolygon(c){
 if(!c||!Array.isArray(c.transform)||c.transform.length!==16||!c.transform.every(finite))return {error:'missing finite 4x4 source transform'};
 const t=c.transform,cols=[0,4,8].map(i=>t.slice(i,i+3)),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
 if(cols.some(a=>Math.abs(Math.hypot(...a)-1)>1e-5)||Math.abs(dot(cols[0],cols[1]))>1e-5||Math.abs(dot(cols[0],cols[2]))>1e-5||Math.abs(dot(cols[1],cols[2]))>1e-5||[3,7,11].some(i=>Math.abs(t[i])>1e-8)||Math.abs(t[15]-1)>1e-8)return {error:'non-rigid source transform'};
 let p;
 if(Array.isArray(c.polygon))p=c.polygon.map(q=>Array.isArray(q)&&q.length===2?{x:q[0],y:q[1],z:0}:null);
 else if(Array.isArray(c.polygonCorners))p=c.polygonCorners.map(q=>Array.isArray(q)&&q.length===3?{x:q[0],y:q[1],z:q[2]}:q);
 if(!p||p.length<3||p.some(q=>!q||![q.x,q.y,q.z].every(finite)))return {error:'missing supported local XY polygon or local XYZ polygonCorners'};
 const points=p.map(p=>world(p,t)),g=polygon3D(points);
 return g.error?{error:g.error}:{points,geometry:g};
}
function bbox(points){return [Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))];}
function segments(entities,story){return entities.filter(e=>e.story===story).flatMap(e=>e.type==='line'?[[e.a,e.b]]:e.type==='polyline'?e.points.slice(0,e.closed?e.points.length:e.points.length-1).map((p,i)=>[p,e.points[(i+1)%e.points.length]]):[]);}
function overlaps(a,b){return a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1];}
const fmt=h=>h.toFixed(2);
/** Absolute plan area of a drawing-space polygon (shoelace). */
function shoelace(poly){let a=0;for(let i=0;i<poly.length;i+=1){const [x1,y1]=poly[i],[x2,y2]=poly[(i+1)%poly.length];a+=x1*y2-x2*y1;}return Math.abs(a)/2;}
/** "h 2.50" for a flat ceiling, "h 1.65-2.48" for a sloped one: the exact same
 *  string the room label and the USDZ customData carry. */
function heightLabel(h){return h.max-h.min<0.005?`h ${fmt(h.min)}`:`h ${fmt(h.min)}-${fmt(h.max)}`;}

/** 3 cm inward-offset, 3 cm trimmed dashed outline on the CEILING layer.
 * Never fabricates an offset outside a concave footprint. */
function outlineEdges(poly,story,layer,seen,annotations,record){
 for(let j=0;j<poly.length;j++){
  const a=poly[j],b=poly[(j+1)%poly.length];
  const key=JSON.stringify([story,...[a,b].map(p=>p.map(v=>Math.round(v*1e6))).sort((a,b)=>a[0]-b[0]||a[1]-b[1])]);
  if(seen.has(key))continue;seen.add(key);annotations.push({type:'line',story,layer,a,b,role:'source-region-boundary'});
 }
}

/** Conservative collision-free text placement inside the footprint.
 * Ladders down to a smaller text height and finally to a forced centroid
 * placement, because a ceiling height range that cannot be drawn is not
 * reported at all — silent omission was worse than a warned overlap. */
const {place:placeLabel,arrow:drawArrow}=require('./ceiling-layout');

/** Plan bounding box of the zone's wall transforms: [x0,z0,x1,z1] or null. */
function wallBounds(walls){
 const xs=[],zs=[];
 for(const w of walls){const t=w&&w.transform;if(!Array.isArray(t)||t.length!==16)continue;if(finite(t[12])&&finite(t[14])){xs.push(t[12]);zs.push(t[14]);}}
 if(!xs.length)return null;
 return [Math.min(...xs),Math.min(...zs),Math.max(...xs),Math.max(...zs)];
}

function addCeilings(model,entities){
 const annotations=[],records=[],warnings=[],alignment=model.architecturalAlignment?.matrix||I,seen=new Set();
 const slopeIndicator=(p,d,down,st,l,out,r)=>drawArrow(p,d,down,st,l,out,r,entities);
 const floors=(model.surfaces||[]).filter(s=>s.kind==='floor').map(s=>({s,...sourcePolygon(s)})).filter(f=>!f.error&&Math.max(...f.points.map(p=>p.y))-Math.min(...f.points.map(p=>p.y))<1e-5);
 const toPlan=p=>{const q=project(apply(alignment,p));return [q.x,q.y];};
 const warn=(code,roomIdentifier,reason)=>warnings.push({code,roomIdentifier,reason});

 // ---- 1. explicit source ceilings (unchanged behaviour) -------------------
 for(const room of model.rooms||[]){
  const base=room.ceiling,current=room.ceilingCurrent;
  if(base&&current&&JSON.stringify(base)!==JSON.stringify(current)){warn('roomplan.ceiling-conflicting-variants',room.identifier,'ceiling and ceiling_curr differ; no selection guessed; wall-top reconstruction not run over conflicting explicit geometry');continue;}
  const list=current||base;
  if(!Array.isArray(list)||!list.length)continue;
  if(list.length>1)warn('roomplan.ceiling-source-alternatives',room.identifier,'Multiple supplied source regions may overlap or conflict; all retained and labelled SR; no min/max physical envelope selected'); // fallback layer handles this room
  for(let i=0;i<list.length;i++){
   const src=sourcePolygon(list[i]),r={roomIdentifier:room.identifier,story:room.story,source:`rooms[].${current?'ceiling_curr':'ceiling'}[${i}]`,coverage:'source-derived',status:'supplied',method:'explicit',heightM:null,annotationOffsetM:OFFSET_M,annotationTrimM:TRIM_M};records.push(r);
   if(src.error){r.reason=src.error;warn('roomplan.ceiling-unsupported',room.identifier,src.error);continue;}
   const points=src.points,poly=points.map(toPlan),story=room.story,layer=`S${story}_CEILING`;
   r.sourceRegionId=`SR ${room.identifier}.${i+1}`;r.interpretation="supplied alternative source surface; not a selected physical envelope";r.regionPlanM=poly;r.worldCornersM=points;r.sourceAreaM2=src.geometry.area;r.ceilingAreaM2=src.geometry.area;r.worldElevationRangeM=[Math.min(...points.map(p=>p.y)),Math.max(...points.map(p=>p.y))];
   if(finite(room.area)&&room.area>0&&Math.abs(src.geometry.area-room.area)/room.area>0.2)warn('roomplan.ceiling-area-discrepancy',room.identifier,`ceiling polygon area ${src.geometry.area.toFixed(2)} m2 differs >20% from room.area ${room.area.toFixed(2)} m2`);
   if(Math.abs(src.geometry.n[1])<1e-5){r.reason='ceiling plane vertical; no supported height function';warn('roomplan.ceiling-vertical',room.identifier,r.reason);continue;}
   // Only an actual same-story horizontal floor polygon covering every vertex
   // establishes the floor datum. floorHeight is a supplied scalar cross-check,
   // never a replacement for missing source geometry.
   const candidates=floors.filter(f=>f.s.story===story&&points.every(p=>inPolygon([p.x,p.z],f.points.map(q=>[q.x,q.z]),0.02)));
   const elevations=candidates.map(f=>f.points.reduce((s,p)=>s+p.y,0)/f.points.length);
   const suppliedFloor=finite(room.floorHeight)?room.floorHeight:null;
   let floor=elevations.length?elevations[0]:null;
   r.floorCandidatesM=elevations;r.suppliedRoomFloorHeightM=suppliedFloor;
   if(elevations.some(v=>Math.abs(v-floor)>0.02)){floor=null;r.heightReason='ambiguous same-story floor elevations';}
   if(floor!=null&&suppliedFloor!=null&&Math.abs(suppliedFloor-floor)>0.02){
    r.floorScalarMinusPolygonM=suppliedFloor-floor;
    floor=null;r.heightReason='room.floor_height contradicts a covering transformed floor polygon by more than 0.02m';
   }
   if(floor==null&&!r.heightReason&&suppliedFloor!=null){
    const values=points.map(p=>p.y-suppliedFloor),min=Math.min(...values),max=Math.max(...values);
    if(min>0&&max<=6){
     r.heightM={min,max,coverage:'supplied-floor-level',basis:'source-world ceiling Y minus source-supplied room.floor_height; no covering measured floor polygon; positive separation, maximum 6.0 m',floorElevationM:suppliedFloor};
     warn('roomplan.ceiling-height-from-supplied-floor-level',room.identifier,'height uses supplied room.floor_height because no measured floor polygon covers the ceiling; not a measured floor plane');
    } else r.heightReason=`ceiling minus supplied floor_height ${min.toFixed(3)}-${max.toFixed(3)} m outside positive-to-6.0 m supported separation`;
   }
   if(floor!=null){
    const values=points.map(p=>p.y-floor),min=Math.min(...values),max=Math.max(...values);
    if(min<=0){r.heightReason='nonpositive ceiling-floor vertical separation';}
    else if(max>6){r.heightReason='separation above 6.0 m storey plausibility bound';}
    else r.heightM={min,max,coverage:'computed',basis:'source-world ceiling Y minus covering horizontal same-story floor polygon Y',floorElevationM:floor};
   } else if(!r.heightM) r.heightReason=r.heightReason||'no covering horizontal same-story floor polygon and no usable supplied floor level';
   // A tilted source ceiling plane is a slope: show its fall direction and its
   // real height range, not just a flat outline.
   const ny=src.geometry.n[1];
   r.planeTiltDeg=Math.abs(Math.acos(Math.min(1,Math.abs(ny))))*180/Math.PI;
   if(r.planeTiltDeg<=2.5){
    // FLAT source ceiling: nothing is drawn on the ceiling layer. A flat plane
    // needs no dashed strips and no callout; the room label already states the
    // height ("Room 40.49 m2  h 3.07").
    r.flatCeiling=true;r.ceilingDrawn=false;
    r.note='supplied flat source region: height only, no perimeter';
    {const value=`${r.sourceRegionId}  ${r.heightM?heightLabel(r.heightM):'h unknown'}`;r.layout=placeLabel(poly,story,`S${story}_CEILING_FLAT`,entities,annotations,value);r.label=value;}
    if(!r.heightM)warn('roomplan.ceiling-height-unavailable',room.identifier,r.heightReason);
    continue;
   }
   outlineEdges(poly,story,layer,seen,annotations,r);
   {
    // downhill in plan = (n_x/n_y, -n_z/n_y) because plan y = -source z
    const dir=[src.geometry.n[0]/ny,-src.geometry.n[2]/ny];
    if(!slopeIndicator(poly,dir,'plus',story,layer,annotations,r))r.slopeIndicatorReason='no interior straight run along the plane gradient';
   }
   if(r.heightM){
    const value=`${r.sourceRegionId}  ${heightLabel(r.heightM)}`,placed=placeLabel(poly,story,layer,entities,annotations,value);
    if(placed){r.label=value;r.labelPosition=placed.pos;r.layout=placed;}
    else {r.layoutReason='no collision-free conservative label bbox candidate';warn('roomplan.ceiling-label-layout',room.identifier,r.layoutReason);}
   }else {warn('roomplan.ceiling-height-unavailable',room.identifier,r.heightReason);r.layout=placeLabel(poly,story,layer,entities,annotations,`${r.sourceRegionId}  h unknown`);}
  }
 }

 // ---- 2. wall-top reconstruction, only where no explicit ceiling exists --
 for(const zone of recon.zoneCeilings(model)){
  if(zone.source==='explicit')continue; // never reconstruct over supplied geometry
  const story=finite(zone.story)?zone.story:0, layer=`S${story}_CEILING`;
  const r={roomIdentifier:zone.roomIdentifier,zoneKey:zone.key,story,source:'wall-top reconstruction',
   sourceRefs:(zone.walls||[]).map(w=>({kind:'wall',identifier:w.identifier??null,sourceRoomIndex:w.sourceRoomIndex??null})),
   status:zone.status,coverage:zone.coverage,method:zone.method||null,
   ceilingAreaM2:finite(zone.ceilingArea)?zone.ceilingArea:null,
   floorAreaM2:finite(zone.floorArea)?zone.floorArea:null,
   heightM:finite(zone.heightMin)&&finite(zone.heightMax)?{min:zone.heightMin,max:zone.heightMax,basis:zone.method==='flat'?'flat wall top heights from wall polygons/dimensions.y':'roof section read from wall top profiles (knee/ridge), not dimensions.y'}:null,
   slopeSurplusM2:finite(zone.slopeSurplus)?zone.slopeSurplus:null,
   slopeExtentM:finite(zone.slopeExtent)?zone.slopeExtent:null,
   kneeWallIds:zone.kneeWallIds||[],notParallel:zone.notParallel===true,fallDirection:zone.fallDirection||null,
   wallCount:zone.wallCount||0,profileWallCount:zone.profileWallCount||0,
   reason:zone.reason||null,annotationOffsetM:OFFSET_M,annotationTrimM:TRIM_M};
  records.push(r);
  for(const w of zone.warnings||[])warn(w.code,zone.roomIdentifier??null,w.reason);
  if(r.method==='flat')warn('roomplan.ceiling-reconstructed-flat',zone.roomIdentifier??null,'no wall top edge is sloped; flat ceiling reconstructed equal to the measured floor footprint');
  if(!finite(zone.ceilingArea)){warn('roomplan.ceiling-unavailable',zone.roomIdentifier??null,zone.reason||'no explicit ceiling and no reconstructable wall-top geometry');continue;}
  // Drawing needs a footprint. Raw captures (no room polygons) have none, so
  // the dashed ceiling plane is drawn over the walls' own plan bounding box —
  // clearly an approximation, still visible, still labelled with its method.
  let footprint=zone.polygon, synthesized=null;
  if(!footprint){
   const b=wallBounds(zone.walls||[]);
   if(b){
    footprint=[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]];
    synthesized='walls bounding box (no room/floor polygon in this capture)';
    r.layoutReason=synthesized;
    warn('roomplan.ceiling-reconstruction-no-outline',zone.roomIdentifier??null,'no room/floor footprint polygon; the ceiling plane is drawn over the walls bounding box');
   }
  }
  if(!footprint){r.layoutReason='no footprint at all: no polygon and no walls';warn('roomplan.ceiling-reconstruction-no-outline',zone.roomIdentifier??null,r.layoutReason);continue;}
  // zone polygons are plan [x,z] pairs; lift to source world [x,0,z]
  const poly=footprint.map(p=>toPlan({x:p[0],y:0,z:p[1]}));
  // If a footprint had to be synthesized (no room polygon), the band split
  // would be drawn over a guessed outline: say so instead of pretending.
  if(synthesized)warn('roomplan.ceiling-side-assumed',zone.roomIdentifier??null,'the sloped band is split over the walls bounding box, not a measured room polygon');
  // fall direction in PLAN space, rotated by the same alignment as the polygon
  // (fallDirection is a source-plan vector; the drawing may be rotated).
  const planDir=zone.fallDirection&&Array.isArray(zone.fallDirection.u)?(()=>{const v=apply(alignment,{x:zone.fallDirection.u[0],y:0,z:-zone.fallDirection.u[1]});return [v.x,-v.z];})():null;
  const segs=zone.section&&Array.isArray(zone.section.segments)?zone.section.segments:[];
  const slopeSegs=segs.filter(s=>s.isSlope&&finite(s.run)&&s.run>0);
  const flatSegs=segs.filter(s=>!s.isSlope&&finite(s.run));
  const widest=list=>list.reduce((a,s)=>(a==null||s.run>a.run?s:a),null);
  const slopeSeg=widest(slopeSegs),flatSeg=widest(flatSegs);
  const kneeH=finite(zone.kneeHeightM)?zone.kneeHeightM:null;
  const ridgeH=finite(zone.ridgeHeightM)?zone.ridgeHeightM:null;
  const split=(zone.method!=='flat'&&planDir&&slopeSeg&&finite(kneeH)&&finite(ridgeH)&&ridgeH-kneeH>0.005)
    ?splitCeilingPlan(poly,planDir,zone.fallDirection.downhill,{run:slopeSeg.run,knee:kneeH,ridge:ridgeH,flatRun:flatSeg?flatSeg.run:0})
    :null;
  if(!split){
   // A FLAT ceiling is not drawn at all: strips and a height callout across a
   // plane that has no slope were pure noise, and the room label already
   // states "h 2.48". Nothing but the room label belongs on S0_CEILING.
   r.flatCeiling=true;r.ceilingDrawn=false;
   r.note='flat reconstructed ceiling: one regional height label, no perimeter';
   if(r.heightM){const value=heightLabel(r.heightM);r.label=value;r.layout=placeLabel(poly,story,`S${story}_CEILING_FLAT`,entities,annotations,value);}
   continue;
  }
  const slopeParts=split.parts.filter(p=>p.kind==='slope');
  const flatParts=split.parts.filter(p=>p.kind==='flat');
  // 1. the SLOPED band: dashed orange outline, fall arrow, knee label.
  r.ceilingDrawn=true;
  r.bandAreaM2=slopeParts.reduce((a,p)=>a+shoelace(p.poly),0);
  r.flatAreaM2=flatParts.reduce((a,p)=>a+shoelace(p.poly),0);
  for(const part of slopeParts)outlineEdges(part.poly,story,layer,seen,annotations,r);
  // 2. the RIDGE: where the band ends and the flat remainder begins.
  for(const line of split.ridgeLines||[]){
   annotations.push({type:'line',layer,story,a:line[0],b:line[1]});
  }
  if(split.ridgeLines&&split.ridgeLines.length){
   const line=split.ridgeLines[0];
   // Ridge is geometric only; no uncontained label.
   r.ridgeLine=line;
  }
  if(slopeParts.length&&planDir){
   if(!slopeIndicator(slopeParts[0].poly,planDir,zone.fallDirection.downhill,story,layer,annotations,r))
    r.slopeIndicatorReason='no interior straight run along the fall direction';
  }
  if(slopeParts.length){
   const ht=heightLabel({min:kneeH,max:ridgeH});
   const value=ht;
   r.slopeLayouts=slopeParts.map(part=>placeLabel(part.poly,story,layer,entities,annotations,value));
   const placed=r.slopeLayouts[0];
   if(placed){r.label=value;r.labelPosition=placed.pos;r.layout=placed;if(placed.forced)warn('roomplan.ceiling-label-layout',zone.roomIdentifier??null,'label placed at the band centroid without a collision-free candidate');}
   else {r.layoutReason='no collision-free conservative label bbox candidate';warn('roomplan.ceiling-label-layout',zone.roomIdentifier??null,r.layoutReason);}
  }
  // 3. the FLAT remainder: a thin continuous boundary and "h 2.48 (flat)" on
  // its own layer — no orange strips, ever.
  if(flatParts.length){
   const flatLayer=`S${story}_CEILING_FLAT`;
   // No duplicated flat perimeter.
   const value=`h ${ridgeH.toFixed(2)}`;
   const placed=placeLabel(flatParts[0].poly,story,flatLayer,entities,annotations,value);
   if(placed){r.flatLabel=value;r.flatLabelPosition=placed.pos;}
   else warn('roomplan.ceiling-label-layout',zone.roomIdentifier??null,'flat-part label had no collision-free candidate');
  }
 }
 for(const r of records)if(r.layout?.status==='unresolved-visible-no-leader')warn('roomplan.ceiling-label-unresolved',r.roomIdentifier,'Annotation preserved visibly in external rail without unsafe leader');
 if(!(model.rooms||[]).length&&!records.length)warn('roomplan.ceiling-missing',null,'no explicit room ceilings and no decodable wall-top geometry; ceiling left unavailable');
 warnings.push({code:'roomplan.ceiling-annotation-layout',reason:'3cm offset/trim dashed annotations only; text collision search is conservative and not a CAD layout guarantee; wall geometry and quantities unchanged'});
 return {annotations,diagnostics:{enabled:true,engine:'explicit source ceilings first, wall-top reconstruction (ported ArchiDrawing G1 knee/section/extrusion core) as fallback; drawing only',records,warnings}};
}
module.exports={addCeilings,sourcePolygon};
