import json,tempfile,unittest
from pathlib import Path
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk2_display import snapshot,Mk2Renderer
from app.mono_effect_art import KINDS,pixels
from app.instrument_art import EFFECT_ART
ROOT=Path(__file__).resolve().parents[1]
class MonoEffectArtTests(unittest.TestCase):
 def test_native_unique_drawings_are_cached_binary_and_bounded(self):
  seen=set()
  for kind in KINDS:
   drawing=pixels(kind);self.assertEqual(len(drawing),104*20);self.assertEqual(set(drawing),{0,1});self.assertNotIn(drawing,seen);seen.add(drawing);self.assertIs(drawing,pixels(kind))
  self.assertEqual(pixels('../invalid'),())
 def test_all_native_effects_both_controllers_scopes_and_parameter_pages(self):
  rows=json.loads((ROOT/'app/native_effects_data.json').read_text());duck=json.loads((ROOT/'app/plugin_profiles_data/ducktor.json').read_text());rows.append(dict(uri=duck['uri'],name=duck['title'],parameters=duck['parameters']))
  with tempfile.TemporaryDirectory() as root:
   a=Application(root);a.plugin_catalog=[dict(uri=r['uri'],name=r['name'],kind='EFFECT',supported=True,ports=[dict(p,index=i) for i,p in enumerate(r['parameters'])]) for r in rows]
   renderer=Mk2Renderer();self.addCleanup(renderer.close)
   for cls in (Mk1Surface,Mk2Surface):
    s=cls(a,ControllerInputs(a))
    for level in (0,1,2):
     a.control_level=level
     for row in rows:
      with self.subTest(controller=cls.__name__,level=level,effect=row['uri']):
       a.plugin_target().pop('sample',None);a.plugin_target()['plugins']=[dict(uri=row['uri'],kind='EFFECT',controls={p['symbol']:p['default'] for p in row['parameters']})];a.plugin_slot=0;a.plugin_param=0;a.page='PLUGIN'
       state=snapshot(s);art=EFFECT_ART[row['uri']];self.assertEqual(state['mono_plugin']['art'],art)
       left,right=renderer.draw(state)
       actual=b''.join(left[y*256+17:y*256+121] for y in range(25,45));self.assertEqual(actual,pixels(art))
       plain=dict(state);plain.pop('mono_plugin');baseline=renderer.draw(plain);self.assertEqual(right,baseline[1]);self.assertEqual(left[46*256:],baseline[0][46*256:])
       a.page='CHANNEL';a.channel_page=0;self.assertEqual(snapshot(s)['mono_channel_art'],art)
       a.page='PLUGIN';a.plugin_param=8;self.assertNotIn('mono_plugin',snapshot(s))
 def test_ducktor_public_title_and_uri_unchanged(self):
  p=json.loads((ROOT/'app/plugin_profiles_data/ducktor.json').read_text());self.assertEqual(p['title'],'Machinista Ducktor');self.assertEqual(p['uri'],'urn:machinista:effect:ducktor')
 def test_synth_machines_keep_banks_patch_names_and_keyboard_geometry(self):
  from app.mono_effect_art import SYNTH_ART,synth_art
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as root:
   a=Application(root);a.control_level=2;a.page='PLUGIN';r=Mk2Renderer();self.addCleanup(r.close)
   for uri in (*SYNTH_ART,'urn:other-synth'):
    a.plugin_catalog=[dict(uri=uri,name='Machinista Synth' if 'instrument:synth' in uri else 'Other Synth',kind='INSTRUMENT',supported=True,ports=[])]
    a.track()['plugins']=[dict(uri=uri,kind='INSTRUMENT',controls={})]
    art=synth_art(uri)
    for cls in (Mk1Surface,Mk2Surface):
     s=cls(a,ControllerInputs(a));a.page='PLUGIN'
     with patch('app.plugin_profiles.names',return_value=('Factory','Warm Keys')):state=snapshot(s)
     self.assertEqual(state['mono_plugin']['art'],art);self.assertEqual(state['plugin_names'],('Factory','Warm Keys'));left,right=r.draw(state)
     plain=dict(state);plain.pop('mono_plugin');plain.pop('synth_graph',None);self.assertEqual(right,r.draw(plain)[1])
     a.page='CHANNEL';a.channel_page=0;self.assertEqual(snapshot(s)['mono_channel_art'],art)
    # Full keyboard sits below every instrument panel, with 2/3 black groups.
    data=pixels(art)
    self.assertEqual([x for x in range(44,90) if not data[12*104+x]],[46+i*3 for i in (0,1,3,4,5,7,8,10,11,12)])
