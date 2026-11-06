import json,unittest
from pathlib import Path
from app.controller_survey import summarize,review,validate
from app.controller_survey_catalog import PROFILES,checklist

class ControllerSurveyTests(unittest.TestCase):
 def sample(self):
  s=checklist('maschine_studio')[0]
  return dict(format='Machinista-controller-survey',version=2,checklist_version=2,demo=False,profile_id='maschine_studio',layout_audited=False,device=dict(vendor_id=0x17cc,product_id=0x1300,interfaces=[dict(id='hid0')]),controls=[dict(**s,status='captured',tester_confirmed=True,frames=[dict(ms=0,interface='hid0',hex='0100'),dict(ms=1500,interface='hid0',hex='0104'),dict(ms=3000,interface='hid0',hex='0100')])])
 def test_catalog_matches_browser(self):
  self.assertEqual({k:v for k,v in PROFILES.items() if v['survey_required']},json.loads(Path('web/controller-survey/catalog.json').read_text()))
 def test_valid_export_is_evidence_only(self):
  r=review(self.sample());self.assertFalse(r['activation_allowed']);self.assertFalse(r['coverage']['driver_ready']);self.assertFalse(r['coverage']['input_check_complete'])
 def test_wrong_device_rejected(self):
  r=self.sample();r['device']['product_id']=0x1700
  with self.assertRaises(ValueError):validate(r)
 def test_midi_release_must_be_same_channel(self):
  frames=[dict(ms=1500,interface='midi0',hex='903c60'),dict(ms=2500,interface='midi0',hex='813c00')]
  self.assertFalse(summarize('key',frames)[0]['returned_to_idle'])
  frames.append(dict(ms=3000,interface='midi0',hex='803c00'))
  self.assertTrue(summarize('key',frames)[0]['returned_to_idle'])
 def test_midi_notes_do_not_conflict(self):
  r=self.sample();r['device']['interfaces']=[dict(id='midi0')];r['controls']=[]
  for s,n in zip(checklist('maschine_studio')[:2],(60,61)):
   frames=[dict(ms=1500,interface='midi0',hex=bytes([0x90,n,100]).hex()),dict(ms=2500,interface='midi0',hex=bytes([0x80,n,0]).hex())]
   r['controls'].append(dict(**s,status='confirmed',selected=0,frames=frames))
  self.assertEqual(review(r)['conflicts'],[])
 def test_raw_browser_evidence_has_review_candidates(self):
  r=review(self.sample());self.assertTrue(r['candidates'][self.sample()['controls'][0]['id']]);self.assertEqual(r['mappings'],[])
 def test_each_profile_ids_unique(self):
  for p in PROFILES:
   steps=checklist(p);self.assertEqual(len(steps),len({s['id'] for s in steps}))
 def test_display_observations_preserved_in_review(self):
  r=self.sample();r['display_checks']=[dict(display_id='display_1',pattern='border',status='confirmed',note='Edges readable',transport='webusb',transfer_count=1,bytes_sent=261152,sha256='a'*64)]
  result=review(r);self.assertEqual(result['display_checks'],r['display_checks']);self.assertEqual(len(result['display_inventory']),2)
 def test_unknown_display_and_odr_fake_pass_rejected(self):
  r=self.sample();r['display_checks']=[dict(display_id='display_99',pattern='border',status='blocked',note='')]
  with self.assertRaises(ValueError):validate(r)
  r=self.sample();r['profile_id']='kk_s49_mk3';r['device']['product_id']=0x2100;r['controls']=[];r['display_checks']=[dict(display_id='display_1',pattern='border',status='confirmed',note='',transport='webusb',transfer_count=1,bytes_sent=200,sha256='a'*64)]
  with self.assertRaises(ValueError):validate(r)
 def test_legacy_and_single_encoder_checklists_are_both_importable(self):
  for version in (1,2):
   r=self.sample();r['checklist_version']=version;s=next(s for s in checklist('maschine_studio',version=version) if s['kind']=='encoder');r['controls']=[dict(**s,status='captured',frames=[])];validate(r)
  self.assertEqual(len([s for s in checklist('maschine_studio',version=2) if s['kind']=='encoder']),10)
 def test_keyboard_quick_full_and_legacy_counts(self):
  self.assertEqual([s['name'] for s in checklist('kk_s49_mk2') if s['kind']=='key'],['KEY 1 FROM LEFT','KEY 49 FROM LEFT','KEY 2 FROM LEFT'])
  self.assertEqual(len([s for s in checklist('kk_s49_mk2',version=3,keyboard_test='full') if s['kind']=='key']),49)
  self.assertEqual(len([s for s in checklist('kk_s49_mk2',version=2) if s['kind']=='key']),49)
