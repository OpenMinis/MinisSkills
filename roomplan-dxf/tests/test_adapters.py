"""Offline dialect/model regressions. Synthetic inputs only; no external calls.
Run: python3 tests/test_adapters.py
Override package under test with ROOMPLAN_PACKAGE=/path/to/roomplan-dxf.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import ezdxf

ROOT=Path(os.environ.get('ROOMPLAN_PACKAGE',Path(__file__).resolve().parents[1]))
CLI=ROOT/'scripts/roomplan-to-dxf.js'
I=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
def optimized():
    transform=I.copy();transform[12]=12
    alignment=I.copy();alignment[12]=3
    return {'format_version':1,'walls':[{'identifier':'wall-id','parentIdentifier':'parent-id','category':{'wall':{}},'confidence':{'high':{}},'story':0,'dimensions':[4,2.6,0],'transform':transform,'polygonCorners':[]}],
      'floors':[],'windows':[],'doors':[],'openings':[],'objects':[],
      'alignment_transform':alignment,
      'rooms':[{'id':'room-id','category':'Other','area':12,'vertices_x':[0,4,4,0],'vertices_z':[0,0,3,3],'center_xz':[2,1.5],'edges':[['Existing wall','wall-id']],'curved_edges':[],'floor_height':None,'story':0}],
      'orientation':{'orientation_degrees':42,'uncertainty_degrees':4,'confidence':{'high':{},'location':'SECRET-ORIENTATION'}},
      'latLonAlt':{'latitude':12.3456,'longitude':23.4567,'altitude':100},
      'future':{'geolocation':{'note':'SECRET-ROOT'}}}
def raw():
    w=copy.deepcopy(optimized()['walls'][0]);w['sections']=[{'story':0,'location':{'name':'SECRET-SECTION'},'unknown':'SECRET-UNKNOWN'}]
    w['attributes']={'StorageType':'cabinet','future':{'location':'SECRET-ATTRIBUTE'}}
    return {'captureSessions':[{'roomplanSessions':[{'identifier':'raw-room','story':0,'walls':[w],'coreModel':'SECRET-OPAQUE'}]}]}

class Adapters(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.n=0
        stub=self.base/'bin';stub.mkdir();self.marker=self.base/'network-called'
        p=stub/'apple-location';p.write_text('#!/bin/sh\ntouch "'+str(self.marker)+'"\nexit 99\n');p.chmod(0o755)
        self.env=dict(os.environ,PATH=str(stub)+':'+os.environ['PATH'])
    def tearDown(self):
        self.assertFalse(self.marker.exists(),'geocoder unexpectedly executed');self.temp.cleanup()
    def run_capture(self,data,name='scan.json',args=('--model',),out=None):
        self.n+=1;src=self.base/f'in-{self.n}'/name;src.parent.mkdir();src.write_text(json.dumps(data));before=src.read_bytes()
        out=out or self.base/f'out-{self.n}'
        result=subprocess.run(['node',str(CLI),str(src),str(out),'--no-place-lookup',*args],capture_output=True,text=True,env=self.env,timeout=90)
        self.assertEqual(src.read_bytes(),before)
        return result,src,out
    def capture(self,out):return json.loads(next(out.glob('*.capture.json')).read_text())
    def geometry_signature(self,out):
        doc=ezdxf.readfile(next(out.glob('*.dxf')))
        return [(e.dxftype(),{k:str(v) for k,v in e.dxfattribs().items() if k not in ['handle','owner']},list(e.get_points()) if e.dxftype()=='LWPOLYLINE' else []) for e in doc.modelspace()]
    def test_legacy_missing_version_and_label(self):
        d=optimized();d.pop('format_version')
        r,s,o=self.run_capture(d,name='not-a-roomplan.txt');self.assertEqual(r.returncode,0,r.stderr)
        c=self.capture(o);self.assertEqual(c['source']['dialect'],'optimized-legacy-unversioned');self.assertIsNone(c['rooms'][0]['label']);self.assertIsNone(c['rooms'][0]['floorHeight']);self.assertEqual(c['rooms'][0]['category'],'Other');self.assertIn('absent',c['rooms'][0]['labelProvenance'])
        self.assertEqual(c['source']['sha256'],hashlib.sha256(s.read_bytes()).hexdigest())
        doc=ezdxf.readfile(next(o.glob('*.dxf')));audit=doc.audit();self.assertEqual((len(audit.errors),len(audit.fixes)),(0,0))
        texts=[e.dxf.text for e in doc.modelspace().query('TEXT')];self.assertTrue(any('[Other; id=room-id]' in t for t in texts));self.assertFalse(any('null  ' in t for t in texts))
    def test_explicit_v1_missing_label_and_version99_rejected(self):
        d=optimized();r,s,o=self.run_capture(d);self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(self.capture(o)['source']['dialect'],'optimized-v1')
        d['format_version']=99;r,s,o=self.run_capture(d);self.assertEqual(r.returncode,1);self.assertIn('version 99',r.stderr);self.assertFalse(o.exists())
        d['format_version']=None;r,s,o=self.run_capture(d);self.assertEqual(r.returncode,1)
    def test_fake_filename_shape_and_ambiguity(self):
        for bad in [{},{'rooms':[{'category':'Other'}]},{'walls':[]},{'objects':[]}]:
            r,s,o=self.run_capture(bad,name='optimized_roomplan.json');self.assertEqual(r.returncode,1);self.assertFalse(o.exists())
        d=raw();r,s,o=self.run_capture(d,name='optimized_roomplan.json');self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(self.capture(o)['source']['dialectKind'],'raw')
        d['alignment_transform']=I;r,s,o=self.run_capture(d);self.assertEqual(r.returncode,1);self.assertIn('Ambiguous',r.stderr)
        d=optimized();d.pop('format_version');d.pop('openings');r,s,o=self.run_capture(d);self.assertEqual(r.returncode,1);self.assertIn('no raw fallback',r.stderr)
    def test_malformed_numeric_geometry_and_matrices(self):
        cases=[]
        for field,value in [('vertices_z',[0,1]),('vertices_x',[0,'bad',4,0]),('center_xz',[0]),('area',-1),('story',0.5)]:
            d=optimized();d['rooms'][0][field]=value;cases.append(d)
        for matrix in [None,I[:15],[0]*16,[*I[:15],0],I[:12]+['bad',0,0,1]]:
            d=optimized();d['alignment_transform']=matrix;cases.append(d)
        for field,value in [('dimensions',[-1,2,0]),('dimensions',[1e12,2,0]),('polygonCorners',[[0,0,0],[1,0,0]]),('transform',I[:12]+[None,0,0,1])]:
            d=optimized();d['walls'][0][field]=value;cases.append(d)
        d=optimized();d['rooms'][0]['ceiling']=[{'transform':[0]*16,'polygon':[[0,0],[1,0],[1,1]]}];cases.append(d)
        d=optimized();d['rooms'][0]['vertices_x']=[0,1,2,3];d['rooms'][0]['vertices_z']=[0,0,0,0];cases.append(d)
        d=optimized();d['floors']=[{'story':0,'transform':I}];cases.append(d)
        for d in cases:
            r,s,o=self.run_capture(d);self.assertEqual(r.returncode,1,r.stdout);self.assertIn('Malformed',r.stderr);self.assertFalse(o.exists())
        script="const v=require(process.argv[1]);for(const n of [Infinity,NaN,-Infinity]) {try {v.number(n,'test');process.exit(2)}catch(e){}}"
        r=subprocess.run(['node','-e',script,str(ROOT/'scripts/lib/validate.js')]);self.assertEqual(r.returncode,0)
    def test_privacy_and_optional_source_tree(self):
        for data in [raw(),optimized()]:
            r,s,o=self.run_capture(data);self.assertEqual(r.returncode,0,r.stderr);c=self.capture(o);text=json.dumps(c)
            self.assertNotIn('SECRET-',text);self.assertNotIn('12.3456',text);self.assertNotIn('23.4567',text);self.assertNotIn('sourceTree',c);self.assertNotIn('originalFilename',c['source']);self.assertGreater(c['completeness']['lossInventory']['omittedFieldCount'],0)
            self.assertEqual(c['surfaces'][0]['parentIdentifier'],'parent-id');self.assertEqual(c['surfaces'][0]['confidence'],'high');self.assertEqual(c['surfaces'][0]['sourceStory'],0)
            if c['source']['dialectKind']=='raw':
                self.assertTrue(c['completeness']['coreModel']['present']);self.assertEqual(c['rooms'][0]['identifier'],'raw-room');self.assertEqual(c['surfaces'][0]['sourceRoomIdentifier'],'raw-room')
                self.assertEqual(c['sourceRecords']['rooms'][0]['walls'][0]['attributes']['StorageType'],'cabinet')
            else:self.assertEqual(c['meta']['orientation']['degrees'],42)
            r,s,o=self.run_capture(data,args=('--model','--geo'));self.assertEqual(r.returncode,0,r.stderr);c=self.capture(o);self.assertEqual(c['sourceTree'],data)
    def test_paths_overwrite_source_and_no_duplicate_alignment(self):
        d=optimized();r,s,o=self.run_capture(d);self.assertEqual(r.returncode,0,r.stderr);c=self.capture(o)
        self.assertFalse(c['alignment']['applied']);self.assertEqual(c['surfaces'][0]['transform'],d['walls'][0]['transform']);self.assertEqual(c['alignment']['matrix'],d['alignment_transform']);self.assertEqual(c['rooms'][0]['polygonXZ'][0],{'x':0,'z':0})
        with_model_geometry=self.geometry_signature(o)
        cap=next(o.glob('*.capture.json'));before=cap.read_bytes()
        for p in list(o.glob('*.dxf'))+list(o.glob('*.roomplan.json')):p.unlink()
        r=subprocess.run(['node',str(CLI),str(s),str(o),'--model','--no-place-lookup'],capture_output=True,text=True,env=self.env);self.assertEqual(r.returncode,2);self.assertEqual(cap.read_bytes(),before);self.assertFalse(list(o.glob('*.dxf')))
        r=subprocess.run(['node',str(CLI),str(s),str(o),'--model','--force','--no-place-lookup'],capture_output=True,text=True,env=self.env);self.assertEqual(r.returncode,0,r.stderr)
        cap.unlink();cap.symlink_to(s);source=s.read_bytes()
        r=subprocess.run(['node',str(CLI),str(s),str(o),'--model','--force','--no-place-lookup'],capture_output=True,text=True,env=self.env);self.assertEqual(r.returncode,1);self.assertEqual(s.read_bytes(),source);self.assertIn('alias',r.stderr)
        cap.unlink();os.link(s,cap)
        r=subprocess.run(['node',str(CLI),str(s),str(o),'--model','--force','--no-place-lookup'],capture_output=True,text=True,env=self.env);self.assertEqual(r.returncode,1);self.assertEqual(s.read_bytes(),source);self.assertIn('alias',r.stderr)
        r,s,o=self.run_capture(d,args=());self.assertEqual(r.returncode,0,r.stderr);self.assertFalse(list(o.glob('*.capture.json')));self.assertEqual(self.geometry_signature(o),with_model_geometry)
    def test_wrapper_meta_fallback_and_scan_priority(self):
        for scan in [raw(),optimized()]:
            self.n+=1;src=self.base/f'project-{self.n}';src.mkdir();(src/'scan.json').write_text(json.dumps(scan));(src/'meta.json').write_text(json.dumps({'name':'SECRET-PROJECT','latitude':11,'longitude':22,'headingDegrees':99,'future':{'address':'SECRET-META'}}));out=self.base/f'project-out-{self.n}'
            r=subprocess.run(['node',str(CLI),str(src),str(out),'--model','--no-place-lookup'],capture_output=True,text=True,env=self.env);self.assertEqual(r.returncode,0,r.stderr);c=self.capture(out);self.assertNotIn('SECRET-',json.dumps(c));self.assertIn('metadata',c['source'])
            self.assertEqual(c['meta']['orientation']['degrees'],99 if 'captureSessions' in scan else 42)
            self.assertEqual('orientationDegrees' in c['meta']['metadataFallbackFields'],'captureSessions' in scan)

if __name__=='__main__':unittest.main()
