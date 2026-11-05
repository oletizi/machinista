import json,unittest
from pathlib import Path
from app.controller_survey import summarize,review,validate
from app.controller_survey_catalog import PROFILES,checklist

class ControllerSurveyTests(unittest.TestCase):
 def sample(self):
  s=checklist('maschine_studio')[0]
  return dict(format='Machinista-controller-survey',version=2,demo=False,profile_id='maschine_studio',layout_audited=False,device=dict(vendor_id=0x17cc,product_id=0x1300,interfaces=[dict(id='hid0')]),controls=[dict(**s,status='captured',tester_confirmed=True,frames=[dict(ms=0,interface='hid0',hex='0100'),dict(ms=1500,interface='hid0',hex='0104'),dict(ms=3000,interface='hid0',hex='0100')])])
 def test_catalog_matches_browser(self):
  self.assertEqual(PROFILES,json.loads(Path('web/controller-survey/catalog.json').read_text()))
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
