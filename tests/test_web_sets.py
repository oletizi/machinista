import io,json,tempfile,unittest,wave,zipfile
from pathlib import Path
from app.web_server import Library
from app.model import Application
from app.presets import read_preset

class SampleSetTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.lib=Library(self.root,source_scan=lambda:[])
 def tearDown(self):
  for item in (self.lib.sounds,self.lib.stems,self.lib.soundfonts):
   if hasattr(item,'pool'):item.pool.shutdown(wait=True)
  self.tmp.cleanup()
 def wav(self):
  out=io.BytesIO()
  with wave.open(out,'wb') as w:w.setparams((1,2,44100,0,'NONE','NONE'));w.writeframes(b'\0\0'*100)
  return out.getvalue()
 def archive(self,files):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:
   for name,body in files:z.writestr(name,body)
  return out.getvalue()
 def upload(self,files,name='My Kit.zip'):
  raw=self.archive(files);return self.lib.sets.upload(name,io.BytesIO(raw),len(raw))
 def test_pack_splits_without_losing_samples_and_loads_as_group(self):
  result=self.upload([(f'{i:02}.wav',self.wav()) for i in range(17)])
  self.assertEqual(result['sets'],['My Kit 001','My Kit 002']);self.assertEqual([r['pads'] for r in self.lib.sets.listing()],[16,1])
  a=Application(self.root);a.page='BROWSE';a.browser.refresh([]);a.browser.directory=self.root/'presets/Groups';self.assertEqual([a.browser.label(p) for p in a.browser.entries()],['My Kit 001','My Kit 002']);a.enter()
  action=next(v for k,v in a.actions if k=='preset_load');self.assertEqual(action['kind'],'GROUP')
  group=read_preset(action['path'],'GROUP',self.root);self.assertEqual(group['pads'][0]['name'],'00');self.assertTrue(Path(group['pads'][0]['sample']).is_file())
 def test_native_export_import_preserves_pad_order_and_audio(self):
  self.upload([('Kick.wav',self.wav()),('Snare.wav',self.wav())])
  with self.lib.sets.download('My Kit') as (f,mime,name):raw=f.read()
  other=Library(self.root/'other',source_scan=lambda:[])
  try:
   result=other.sets.upload(name,io.BytesIO(raw),len(raw));self.assertEqual(result['sets'],['My Kit'])
   group=read_preset(other.sets.folder/'My Kit/Preset.json','GROUP',other.root);self.assertEqual(group['pads'][1]['name'],'Snare')
  finally:
   for item in (other.sounds,other.stems,other.soundfonts):
    if hasattr(item,'pool'):item.pool.shutdown(wait=True)
 def test_traversal_duplicates_and_non_audio_fail_without_publication(self):
  for files in [[('../escape.wav',self.wav())],[('x.wav',self.wav()),('X.wav',self.wav())],[('instrument.nki',b'x')],[('bad.wav',b'broken')]]:
   with self.subTest(files=[p for p,_ in files]):
    with self.assertRaises((ValueError,wave.Error)):self.upload(files)
    self.assertEqual(self.lib.sets.listing(),[])
 def test_duplicate_set_does_not_overwrite_and_truncated_upload_rolls_back(self):
  self.upload([('x.wav',self.wav())]);before=(self.lib.sets.folder/'My Kit/Preset.json').read_bytes()
  with self.assertRaises(ValueError):self.upload([('new.wav',self.wav())])
  self.assertEqual(before,(self.lib.sets.folder/'My Kit/Preset.json').read_bytes())
  with self.assertRaises(ValueError):self.lib.sets.upload('Incomplete.zip',io.BytesIO(b'x'),100)
  self.assertFalse(any(p.name.startswith('.set-') for p in self.lib.sets.folder.iterdir()))
 def test_external_reference_rejected(self):
  self.upload([('x.wav',self.wav())]);p=self.lib.sets.folder/'My Kit/Preset.json';d=json.loads(p.read_text());d['project']['groups'][0]['pads'][0]['sample']='/etc/passwd';p.write_text(json.dumps(d))
  with self.assertRaises(ValueError):self.lib.sets.document(p.parent)
 def test_http_upload_requires_token_and_download_roundtrip(self):
  import http.client,threading
  from app.web_server import Server
  server=Server(('127.0.0.1',0),self.lib);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   raw=self.archive([('Kick.wav',self.wav())]);client=http.client.HTTPConnection('127.0.0.1',server.server_port)
   client.request('POST','/api/sets/upload?name=HTTP.zip',raw);response=client.getresponse();self.assertEqual(response.status,403);response.read();client.close()
   client=http.client.HTTPConnection('127.0.0.1',server.server_port);client.request('POST','/api/sets/upload?name=HTTP.zip',raw,{'X-Machinista-Token':self.lib.token});response=client.getresponse();self.assertEqual(response.status,200);self.assertEqual(json.loads(response.read())['sets'],['HTTP'])
   client.request('GET','/api/sets');response=client.getresponse();self.assertEqual(json.loads(response.read())[0]['name'],'HTTP')
   client.request('GET','/api/sets/file?id=HTTP');response=client.getresponse();self.assertEqual(response.status,200)
   with zipfile.ZipFile(io.BytesIO(response.read())) as z:self.assertIn('Preset.json',z.namelist())
   client.close()
  finally:server.shutdown();server.server_close();thread.join()
