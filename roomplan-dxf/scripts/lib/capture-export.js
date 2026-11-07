'use strict';
/** Normalized capture interchange v1. Source space, NOT a mesh decoder or a
 * lossless CapturedRoom archive. DXF alignment is a separate unapplied transform.
 * Unknown/opaque fields are omitted by default; --geo permits a source tree.
 */
const crypto = require('crypto');
const KEYS = new Set(`identifier parentIdentifier id kind category categoryDetail category_detail confidence story dimensions transform polygonCorners polygon curve centerX centerZ center_x center_z radius startAngleRadians endAngleRadians start_angle end_angle isOpen wallThickness wall_thickness label labelProvenance area floorHeight floor_height center_xz centerX centerZ vertices vertices_x vertices_z x y z edges curvedEdges curved_edges outerHull outer_hull ceiling ceilingCurrent ceiling_curr ceilingLidarAverageDifference ceilingLidarValidFraction ceiling_lidar_avg_diff ceiling_lidar_valid_pct doorIdentifiers openingIdentifiers windowIdentifiers doors openings windows walls floors objects rooms joints sections attributes completedEdges color position wall_endpoints room_vertices StorageType ChairType SofaType TableType BedType BathtubType ToiletType SinkType RefrigeratorType StoveType WasherDryerType FireplaceType TelevisionType Shape Style Material type name value width height length angle start end center normal points indices wallId roomId referenceOriginTransform label_automated sourceRoomIndex dimensionsProvenance identifierProvenance sourceRoomIdentifier sourceRecordIndex sourceStory sourceStoryProvenance`.split(/\s+/));
const PRIVATE = /latitude|longitude|latlon|altitude|location|address|geocode|geolocation|gps|placemark|postal|street|locality|country|heading|orientation|filename|filepath|url|path|mesh|coremodel/i;
function sha(v) { return crypto.createHash('sha256').update(v).digest('hex'); }
function select(v,stats,key='') {
  if (typeof v==='number') { if(!Number.isFinite(v)) throw new Error('Nonfinite value in normalized model');return v; }
  if(v==null||typeof v==='string'||typeof v==='boolean') return v;
  if(Array.isArray(v)) return v.map(x=>select(x,stats,key));
  if(typeof v!=='object') return null;
  if(key==='confidence') {
    const out={};
    for(const k of Object.keys(v)) {if(['high','medium','low','unknown'].includes(k)) out[k]={};else stats.omittedFieldCount++;}
    return out;
  }
  const out={};
  for(const [k,x] of Object.entries(v)) {
    if(PRIVATE.test(k)||!KEYS.has(k)) {stats.omittedFieldCount++;continue;}
    out[k]=select(x,stats,k);
  }
  return out;
}
function rawRooms(root) {
 if(Array.isArray(root.walls)) return [root];
 if(Array.isArray(root.rooms)) return root.rooms;
 if(Array.isArray(root.captureSessions)) return root.captureSessions.flatMap(c=>c.roomplanSessions||[]);
 return [root];
}
function buildCapture(model,root,options={}) {
 const stats={omittedFieldCount:0};
 const normalized={
  schemaVersion:'roomplan.capture/1',
  dialect:{name:model.dialect,kind:model.kind,evidence:model.dialectEvidence||[]},
  source:{sha256:model.sourceSHA256,byteCount:model.sourceByteCount,originalBytesPreserved:true,originalBytesEmbedded:false},
  conventions:{units:'metres',areaUnits:'square metres',sourceAxes:{up:'+Y',groundPlane:'XZ',handedness:'right-handed'},matrices:'16 numbers, column-major; column vectors; translation indices 12,13,14',surfaceGeometry:'polygonCorners are surface-local; element.transform maps local to source space',roomGeometry:'optimized room vertices/centers are source XZ coordinates',alignment:'unapplied; alignedPoint = alignmentMatrix * element.transform * localPoint; rooms use alignmentMatrix only',dxfProjection:'aligned XZ -> (x,-z); DXF sheet translations are presentation only',boundsPolicy:'coordinates ±1e6 m, dimensions 0..1e5 m, integer story ±10000; affine nonsingular matrices'},
  coordinateState:'source-space; not aligned; no DXF sheet translations applied',
  alignment:{matrix:model.architecturalAlignment.matrix,method:model.architecturalAlignment.method,applied:false},
  surfaces:select(model.surfaces,stats),objects:select(model.objects,stats),rooms:select(model.rooms,stats),
  meta:{storyAssignmentMethod:model.storyAssignmentMethod,orientation:{degrees:model.meta.orientationDegrees??null,uncertaintyDegrees:model.meta.orientationUncertaintyDegrees??null,confidence:select(model.meta.orientationConfidence??null,stats,'confidence'),source:model.meta.orientationDegrees==null ? null : (model.meta.orientationSource||'scan.orientation'),caveat:'source-provided direction, not surveyed/verified true north'},metadataFallbackFields:options.metaFallbackFields||[]},
  completeness:{lossless:false,meshDecoded:false,coreModel:{status:'opaque; not decoded',present:false},sourceTreeIncluded:!!options.includeGeo,lossInventory:{policy:'Default whitelist omits unknown fields and location-like metadata at every nesting depth; field names/values are not copied into the inventory',omittedFieldCount:0,knownLimitations:['No mesh/coreModel decoding','Raw rooms have no inferred measured polygon or name','DXF is a separate lossy projection; canonical curves/sections/attributes are not proof of DXF fidelity','Omitted unknown fields remain in the unchanged source identified by SHA256']}},
 };
 // Recognized source fields preserve attributes/sections and per-record room identity
 // without copying arbitrary opaque metadata. They retain source-space semantics.
 const sourceRooms=model.kind==='raw'?rawRooms(root):root.rooms;
 if(model.kind==='raw') normalized.rooms=sourceRooms.map((r,i)=>({identifier:r.identifier??r.id??null,sourceRoomIndex:i,label:null,labelProvenance:'no measured room name decoded',story:r.story??null,confidence:select(r.confidence??null,stats),vertices:null,sections:select(r.sections??null,stats),attributes:select(r.attributes??null,stats)}));
 normalized.sourceRecords=select(model.kind==='raw'?{rooms:sourceRooms,sections:root.sections,attributes:root.attributes}:{walls:root.walls,floors:root.floors,doors:root.doors,windows:root.windows,openings:root.openings,objects:root.objects,rooms:root.rooms,joints:root.joints,sections:root.sections,attributes:root.attributes},stats);
 function countOpaque(v) {
  if(!v||typeof v!=='object')return;
  if(!Array.isArray(v)&&Object.prototype.hasOwnProperty.call(v,'coreModel')) normalized.completeness.coreModel.present=true;
  for(const [k,x] of Object.entries(v)) {if(k==='coreModel')continue;countOpaque(x);}
 }
 countOpaque(root);
  normalized.completeness.lossInventory.omittedFieldCount=stats.omittedFieldCount;
  normalized.completeness.lossInventory.countScope='omitted field occurrences while projecting canonical records and sourceRecords; not a recursive count of all original fields';
  normalized.completeness.lossInventory.omittedRootFieldCount=Object.keys(root).filter(k=>!['format_version','walls','floors','doors','windows','openings','objects','rooms','captureSessions','alignment_transform','latLonAlt','orientation','joints','sections','attributes'].includes(k)).length;
  normalized.completeness.lossInventory.wrapperMetadata='Raw wrapper/container fields outside known room/element records are not projected; available only in unchanged input or --geo sourceTree';
 normalized.privacy={includeGeo:!!options.includeGeo,sourceTree:'omitted',note:'Metadata redaction, not anonymization: geometry, IDs and source labels can still be identifying. Source basename/path/project name omitted unless --geo.'};
 if(options.metaBytes) normalized.source.metadata={sha256:sha(options.metaBytes),byteCount:options.metaBytes.length};
 if(options.includeGeo) {
  normalized.source.originalFilename=model.originalFilename;
  normalized.meta.location={latitude:model.meta.latitude??null,longitude:model.meta.longitude??null,altitude:model.meta.altitude??null};
  normalized.sourceTree=root;
  if(options.metaBytes) normalized.sourceMetaTree=JSON.parse(options.metaBytes.toString('utf8'));
  normalized.privacy.sourceTree='included verbatim; may contain private locations, names and opaque encoded data';
 }
 return normalized;
}
module.exports = {buildCapture};
