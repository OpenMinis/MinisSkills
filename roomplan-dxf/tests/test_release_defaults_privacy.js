'use strict';
const assert=require('assert'),fs=require('fs'),os=require('os'),path=require('path'),crypto=require('crypto'),{spawnSync}=require('child_process');
const {displayPath}=require('../scripts/lib/group-sidecar');
const {buildUsda}=require('../scripts/lib/usda-export');
const {decode}=require('../scripts/lib/decode-optimized');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'release-synthetic-'));
const T=(x,y,z)=>[1,0,0,0,0,1,0,0,0,0,1,0,x,y,z,1];
const raw={format_version:1,walls:[0,4].map((z,i)=>({identifier:'W'+i,category:{wall:{}},confidence:{high:{}},dimensions:[6,2.5,.16],transform:T(3,1.25,z),story:0})),rooms:[{id:'R',category:'room',story:0,area:24,center_xz:[3,2],floor_height:0,vertices_x:[0,6,6,0],vertices_z:[0,0,4,4]}],floors:[],doors:[],windows:[],objects:[],alignment_transform:T(0,0,0)};
try {
 const project=path.join(tmp,'project');fs.mkdirSync(project);const scan=path.join(project,'roomplan.json');const text=JSON.stringify(raw);fs.writeFileSync(scan,text);
 const marker='SYNTHETIC_PRIVATE_MARKER';const external=path.join(tmp,marker);fs.mkdirSync(external);const sidecar=path.join(external,'groups.json');fs.writeFileSync(sidecar,JSON.stringify({sourceSHA256:crypto.createHash('sha256').update(text).digest('hex'),groups:[]}));
 assert.equal(displayPath(sidecar,project,{inputWasDirectory:true,scanPath:scan}),'groups.json');
 assert.equal(displayPath(path.join(project,'sub','groups.json'),project,{inputWasDirectory:true,scanPath:scan}),path.join('sub','groups.json'));
 const cases=[['default',[],false,true],['on',['--usdz-ceilings'],true,true],['off',['--usdz-ceilings','--no-usdz-ceilings'],false,true],['dxf-off',['--no-ceilings','--usdz-ceilings'],true,false]];
 for(const [name,flags,ceilings,dxf] of cases){
  const out=path.join(tmp,'out-'+name);const r=spawnSync(process.execPath,[path.join(__dirname,'../scripts/roomplan-to-dxf.js'),project,out,'--no-place-lookup','--model','--report','--md','--usdz','--surface-region-groups',sidecar,...flags],{encoding:'utf8'});
  assert.equal(r.status,0,r.stderr+'\n'+r.stdout);
  for(const f of fs.readdirSync(out))assert(!fs.readFileSync(path.join(out,f)).includes(Buffer.from(marker)),name+' leak in '+f);
  const zip=fs.readFileSync(path.join(out,'project.usdz')).toString();assert.equal(zip.includes('Category = "Ceiling"'),ceilings,name+' USDZ ceiling setting');
  const manifest=JSON.parse(fs.readFileSync(path.join(out,'project.roomplan.json')));
  assert.equal(manifest.ceilingDiagnostics.surfaceRegions.groupsSource.path,'groups.json');
  // CLI options must be independent, not inferred from whether a scene has meshes.
  assert.equal(manifest.ceilingDiagnostics.enabled,dxf,name+' DXF ceiling default/independence');
 }
 const m=decode(text,'synthetic.json');m.surfaceRegions={groupsSource:{path:'/SYNTHETIC_PRIVATE_MARKER/groups.json',relative:'/SYNTHETIC_PRIVATE_MARKER/groups.json'}};
 assert(!Object.values(buildUsda(m,{ceilings:false}).files).join('\n').includes(marker),'standalone USDZ path leak');
 console.log('PASS release privacy marker absence (all output files), relative/external paths, USDZ default OFF/opt-in/last toggle/DXF independence');
} finally {fs.rmSync(tmp,{recursive:true,force:true});}
