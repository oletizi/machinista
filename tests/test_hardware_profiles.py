import os,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from app.hardware_profiles import current,environment
from app.model import Application
from app.autosampler import configuration

class HardwareProfilesTests(unittest.TestCase):
 def test_marker_defaults_and_unknown_profile(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=True):
   marker=Path(folder)/'profile';self.assertEqual(current(marker)['id'],'standard');marker.write_text('pi3b-sampler\n');self.assertEqual(current(marker)['sampler_voices'],16);marker.write_text('unknown')
   with self.assertRaises(ValueError):current(marker)
 def test_small_profile_defaults_without_rewriting_projects(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'MACHINISTA_HARDWARE_PROFILE':'pi3b-sampler'}):
   app=Application(folder);self.assertEqual(app.settings['audio_buffer'],512);self.assertFalse(app.hardware_profile['lv2']);self.assertEqual(app.hardware_profile['sample_memory_mib'],192);self.assertEqual(environment()['MACHINISTA_HARDWARE_PROFILE'],'pi3b-sampler')
   app.auto_setup();self.assertEqual(app.auto_config['source'],'EXTERNAL')
 def test_standard_retains_current_capabilities(self):
  with patch.dict(os.environ,{'MACHINISTA_HARDWARE_PROFILE':'standard'}):self.assertTrue(current()['synth']);self.assertTrue(current()['lv2']);self.assertTrue(current()['stems']);self.assertEqual(current()['sampler_voices'],64)

 def test_webui_hides_and_blocks_disabled_capabilities(self):
  import http.client,threading
  from app.web_server import Library,Server
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'MACHINISTA_HARDWARE_PROFILE':'pi3b-sampler'}):
   Application(folder);library=Library(folder,lambda:[]);server=Server(('127.0.0.1',0),library);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    for route in ('/api/lv2','/api/synth','/api/plugin-banks','/api/stems'):
     c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request('GET',route);r=c.getresponse();self.assertEqual(r.status,403);r.read();c.close()
    c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request('GET','/api/session');r=c.getresponse();value=json.loads(r.read());self.assertEqual(r.status,200);self.assertEqual(value['hardware_profile']['id'],'pi3b-sampler');c.close()
   finally:server.shutdown();server.server_close();thread.join()
