"""Patch-owned native FX are portable and never replace user insert processors."""
import copy,json,unittest
from app.plugin_profiles import _cache,rotate,validate_bank
from app.web_synth import apply
from app.synth_patch_fx import effects,MARK
from app.model import Application,validate_project
from app.bank_sounds import project,FORMAT
from tests import test_synth_bank_waves as fixtures

class SynthPatchFxTests(unittest.TestCase):
    setUp=fixtures.SynthBankWavesTests.setUp
    def publish(self):
        self.bank['patches'][0]['effects']=[dict(uri='urn:machinista:effect:chorus',controls={'mix':.2}),dict(uri='urn:machinista:effect:reverb',controls={'mix':.15})]
        (self.root/'presets/plugin-banks/machinista-synth/factory.json').write_text(json.dumps(self.bank));_cache.clear()
    def load(self,index=0):apply(self.a,dict(slot=0,uri=self.p['uri'],preset=dict(bank='factory',patch=index)))
    def test_web_and_controller_load_fx_and_legacy_patch_removes_only_owned(self):
        for web in (False,True):
            self.publish();a=self.a;a.track()['plugins']=a.track()['plugins'][:1]
            custom=dict(uri='urn:my:eq',kind='EFFECT',controls={'gain':.7});a.track()['plugins'].append(custom)
            if web:self.load()
            else:rotate(a,a.plugin_selected(),dict(profile_action='bank'),-1)
            chain=a.track()['plugins'];self.assertEqual([p['uri'] for p in chain],[self.p['uri'],'urn:machinista:effect:chorus','urn:machinista:effect:reverb','urn:my:eq'])
            self.assertIs(chain[-1],custom);self.assertTrue(chain[1][MARK]);self.assertEqual(chain[1]['controls']['mix'],.2)
            self.assertIn('rate',chain[1]['controls']);validate_project(a.project)
            if web:self.load(1)
            else:rotate(a,a.plugin_selected(),dict(profile_action='patch'),1)
            self.assertEqual(a.track()['plugins'],[a.plugin_selected(),custom])
    def test_web_uses_sound_even_if_controller_is_at_master(self):
        self.publish();self.a.control_level=0;master=copy.deepcopy(self.a.project.get('plugins',[]));self.load()
        self.assertEqual(len(self.a.track()['plugins']),3);self.assertEqual(self.a.project.get('plugins',[]),master)
    def test_sound_browser_builds_identical_chain_and_roundtrips(self):
        self.publish();p=project(self.root,dict(format=FORMAT,version=1,uri=self.p['uri'],bank='factory',bank_name='Factory',program=0,preset=self.bank['patches'][0]))
        self.load();self.assertEqual(p['groups'][0]['pads'][0]['plugins'][1:],self.a.track()['plugins'][1:])
        self.a.save();restored=Application(self.root);self.assertEqual(restored.track()['plugins'][1:][0]['controls']['mix'],.2)
    def test_slot_overflow_and_invalid_recipes_are_atomic(self):
        self.publish();self.a.track()['plugins'] += [dict(uri=f'urn:user:{i}',kind='EFFECT',controls={}) for i in range(15)]
        old=copy.deepcopy(self.a.project);undo=len(self.a.undo)
        with self.assertRaisesRegex(ValueError,'slots'):self.load()
        self.assertEqual(self.a.project,old);self.assertEqual(len(self.a.undo),undo)
        rotate(self.a,self.a.plugin_selected(),dict(profile_action='bank'),-1)
        self.assertEqual(self.a.project,old);self.assertIn('slots',self.a.message)
        for recipe in ([{'uri':'https://bad/plugin'}],[{'uri':'urn:machinista:effect:reverb','state':'/tmp/file'}],[{'uri':'urn:machinista:effect:reverb','controls':{'mix':float('nan')}}],[{'uri':'urn:machinista:effect:reverb','controls':{'mix':2}}],[{'uri':'urn:machinista:effect:chorus','controls':{'missing':.2}}],[{'uri':'urn:machinista:effect:chorus'}]*2):
            b=copy.deepcopy(self.bank);b['patches'][0]['effects']=recipe
            with self.assertRaises(ValueError):validate_bank(b,self.p)
    def test_undo_and_automation_reindex_follow_user_effect(self):
        self.publish();a=self.a;custom=dict(uri='urn:my:eq',kind='EFFECT',controls={});a.track()['plugins'].append(custom)
        a.project['groups'][0].setdefault('automation',{})['0:0:plugin:1:gain']={'points':{'0':.5}}
        before=copy.deepcopy(a.project);self.load()
        self.assertIn('0:0:plugin:3:gain',a.project['groups'][0]['automation'])
        self.assertEqual(a.undo[-1],before)
        self.load(1);self.assertIn('0:0:plugin:1:gain',a.project['groups'][0]['automation'])
    def test_patch_effect_controls_validated_when_project_reloads(self):
        self.publish();self.load();self.a.track()['plugins'][1][MARK]='yes'
        with self.assertRaises(ValueError):validate_project(self.a.project)
