"""Native inserts share project/automation controls, but never patch-bank files."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app.model import Application,validate_project
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot,chain_state
from app.mk3_display import Mk3Renderer
from app.plugin_profiles import profile,controls,names
from app.instrument_art import effect_art,image
from app.ni_display import plugin_value
ROOT=Path(__file__).resolve().parents[1]
ROWS=json.loads((ROOT/'app/native_effects_data.json').read_text())

class NativeEffectsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=Application(self.tmp.name);self.a.page='PLUGIN';self.a.control_level=2
  self.a.plugin_catalog=[dict(uri=r['uri'],name=r['name'],kind='EFFECT',supported=True,builtin=True,ports=[dict(p,index=i) for i,p in enumerate(r['parameters'])]) for r in ROWS]
 def load(self,row):
  self.a.plugin_target()['plugins']=[dict(uri=row['uri'],kind='EFFECT',controls={p['symbol']:p['default'] for p in row['parameters']})];self.a.plugin_slot=0;self.a.plugin_param=0
 def test_complete_inventory_at_sound_group_and_master(self):
  for level in (0,1,2):
   self.a.control_level=level;self.a.plugin_filter='EFFECT';self.assertEqual({r['uri'] for r in ROWS},{p['uri'] for p in self.a.plugin_items()})
 def test_layout_units_no_disk_bank_lookup_and_no_render_mutation(self):
  for row in ROWS:
   with self.subTest(effect=row['id']):
    self.load(row);before=copy.deepcopy(self.a.project)
    with patch('app.plugin_profiles.selection',side_effect=AssertionError('Native FX must not scan patch banks')):ports=self.a.plugin_controls()
    self.assertEqual({p['symbol'] for p in ports},{p['symbol'] for p in row['parameters']})
    self.assertTrue(all(not p['symbol'].startswith('@') for p in ports));self.assertIsNone(names(self.a.root,self.a.plugin_selected()))
    for p in ports:
     if p.get('unit')=='percent':self.assertRegex(plugin_value(p,.65),r'^65%$')
    self.assertEqual(before,self.a.project)
 def test_parameter_edit_automation_and_project_reload(self):
  for row in ROWS:
   self.load(row);port=self.a.plugin_controls()[0];old=self.a.plugin_selected()['controls'][port['symbol']]
   self.a.plugins_rotate(1);self.assertNotEqual(self.a.plugin_selected()['controls'][port['symbol']],old,row['id'])
   self.assertIsNotNone(self.a.automation_descriptor());validate_project(self.a.project);self.a.save()
   restored=Application(self.tmp.name);saved=restored.track()['plugins'][0];current=self.a.plugin_selected()
   self.assertEqual(saved['uri'],current['uri']);self.assertEqual(saved['controls'],current['controls']);self.assertEqual(Path(saved['state']).resolve(),Path(current['state']).resolve())
 def test_own_art_for_every_effect_and_ducktor_at_all_levels(self):
  surface=Mk3Surface(self.a,ControllerInputs(self.a));renderer=Mk3Renderer();self.addCleanup(renderer.close);seen=set()
  for uri in [r['uri'] for r in ROWS]+['urn:machinista:effect:ducktor']:
   art=effect_art(uri);self.assertNotEqual(art,'generic-filter');self.assertNotIn(image(art).tobytes(),seen);seen.add(image(art).tobytes())
   for level in (0,1,2):
    self.a.control_level=level;self.a.plugin_target()['plugins']=[dict(uri=uri,kind='EFFECT',controls={})]
    self.a.page='CHANNEL';self.assertEqual(snapshot(surface)['output_art'],art)
    self.a.page='PLUGIN';self.assertEqual(chain_state(surface)['items'][0]['art'],art);renderer.images(snapshot(surface))
  self.assertEqual(effect_art('urn:unknown:effect'),'generic-filter')
 def test_generated_profiles_and_cpp_metadata_reproducible(self):
  from tools.generate_native_effects import generate
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'app/plugin_profiles_data').mkdir(parents=True);(root/'src/audio').mkdir(parents=True)
   (root/'app/native_effects_data.json').write_bytes((ROOT/'app/native_effects_data.json').read_bytes());generate(root)
   for path in root.rglob('*'):
    if path.is_file():self.assertEqual(path.read_bytes(),(ROOT/path.relative_to(root)).read_bytes(),str(path))
  for row in ROWS:self.assertEqual(profile(row['uri'])['provider'],'native-core')
