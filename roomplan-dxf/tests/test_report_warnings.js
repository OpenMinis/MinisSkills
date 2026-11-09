'use strict';
// Regression: ceiling warnings use `reason`; CLI report-v1 must retain it as
// message, retain room attribution, and not deduplicate different rooms.
const assert = require('assert');
const fs = require('fs'), os = require('os'), path = require('path');
const {spawnSync} = require('child_process');
const {validate} = require('./lib/mini-schema');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'report-warnings-'));
const T = (x,y,z) => [1,0,0,0,0,1,0,0,0,0,1,0,x,y,z,1];
const face = {transform:T(0,2.5,0),polygonCorners:[[0,0,0],[2,0,0],[2,0,2],[0,0,2]]};
const raw = {format_version:1,walls:[{identifier:'w1',category:'wall',dimensions:[2,2.5,0.1],transform:T(1,1.25,0),story:0}],floors:[],doors:[],windows:[],objects:[],
 rooms:['r1','r2'].map(id=>({id,category:'other',center_xz:[1,1],story:0,area:4,floor_height:0,vertices_x:[0,2,2,0],vertices_z:[0,0,2,2],ceiling:[face,face]}))};
try {
 const input=path.join(tmp,'scan.json'),out=path.join(tmp,'out');fs.writeFileSync(input,JSON.stringify(raw));
 const res=spawnSync('node',[path.join(__dirname,'../scripts/roomplan-to-dxf.js'),input,out,'--report','--no-place-lookup'],{encoding:'utf8'});
 assert.strictEqual(res.status,0,res.stderr);
 const report=JSON.parse(fs.readFileSync(path.join(out,'scan.report.json')));
 const manifest=JSON.parse(fs.readFileSync(path.join(out,'scan.roomplan.json')));
 const schema=JSON.parse(fs.readFileSync(path.join(__dirname,'../scripts/lib/schema/report-v1.json')));
 assert.deepStrictEqual(validate(schema,report),[],'CLI report must conform to report-v1 including ceiling warnings');
 const originals=manifest.warnings.filter(w=>w.code==='roomplan.ceiling-source-alternatives');
 assert.strictEqual(originals.length,2,'two rooms produce distinct diagnostics');
 for (const original of originals) assert(report.warnings.some(w=>w.code===original.code&&w.message===original.reason&&w.roomIdentifier===original.roomIdentifier),'retain original reason and room attribution');
 assert(report.warnings.every(w=>typeof w.message==='string'&&w.message.length>0));
 console.log('report warning regression: schema, messages and room attribution PASS');
} finally {fs.rmSync(tmp,{recursive:true,force:true});}
