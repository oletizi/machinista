"""Confirmed catalog deletion, active-project reset and retained shared assets."""
import copy,json,queue,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock
from app.model import Application
from app.project_delete import delete
from tests import test_web_projects as project_fixtures
from tests import test_sound_library as sound_fixtures
from tests import test_bank_sounds as bank_fixtures

class SoundDeletionTests(unittest.TestCase):
 setUp=sound_fixtures.SoundLibraryTests.setUp
 draft=sound_fixtures.SoundLibraryTests.draft
 opener=sound_fixtures.SoundLibraryTests.opener
 def test_confirmation_stale_name_and_retained_samples(self):
  draft=self.lib.save(self.draft(),self.opener);before=self.lib.read(draft['id']);value=dict(id=draft['id'],name=draft['name'],confirmed=True)
  for change in ({'confirmed':False},{'name':'Renamed'}):
   with self.assertRaises(ValueError):self.lib.delete(dict(value,**change))
   self.assertIsNotNone(self.lib.row(draft['id']))
  self.lib.delete(value);self.assertIsNone(self.lib.row(draft['id']))
  self.assertTrue(all(Path(z['sample']).is_file() for z in before['zones']))
  self.assertEqual(len(list((self.lib.folder/'.trash').glob('*/Sound.sound'))),1)

class BankDeletionTests(unittest.TestCase):
 setUp=bank_fixtures.BankSoundTests.setUp
 build=bank_fixtures.BankSoundTests.build
 def test_bank_patch_deletion_survives_catalog_rebuild_without_removing_bank(self):
  self.build();rows=self.library.scan()['sounds'];row=next(r for r in rows if r['kind']=='SYNTH');path=self.library.folder/row['link']
  self.library.delete(dict(id=row['id'],name=row['name'],confirmed=True));self.build()
  self.assertFalse(path.exists());self.assertIsNone(self.library.row(row['id']))
  self.assertEqual(len(self.library.scan()['sounds']),len(rows)-1)
  self.assertTrue((self.root/'presets/plugin-banks/machinista-synth/warm.json').is_file())

class ProjectDeletionTests(unittest.TestCase):
 setUp=project_fixtures.ProjectTransferTests.setUp
 def value(self,identity):
  row=next(r for r in self.library.projects.list() if r['id']==identity)
  return dict(id=row['id'],name=row['name'],version=row['version'],confirmed=True)
 def test_confirmation_staleness_and_inactive_project_preserve_working_copy(self):
  other=copy.deepcopy(self.project);other.update(name='OTHER',file_id='PROJECT-0002');p=self.root/'projects/PROJECT-0002.json';p.write_text(json.dumps(other));value=self.value(p.name)
  for change in ({'confirmed':False},{'name':'wrong'},{'version':'old'},{'id':'../current.json'}):
   with self.assertRaises(ValueError):self.library.projects.delete(dict(value,**change))
   self.assertTrue(p.is_file())
  result=self.library.projects.delete(value);self.assertFalse(result['cleared']);self.assertFalse(p.exists());self.assertEqual((self.root/'projects/current.json').read_bytes(),self.saved)
 def test_active_project_removal_clears_saved_slot_but_keeps_samples_and_recovery(self):
  result=self.library.projects.delete(self.value('PROJECT-0001.json'))
  self.assertTrue(result['cleared']);self.assertFalse((self.root/'projects/PROJECT-0001.json').exists());self.assertEqual(json.loads((self.root/'projects/current.json').read_text())['name'],'UNTITLED')
  self.assertEqual((self.root/'samples/kick.wav').read_bytes(),b'sample bytes')
  self.assertEqual(len(list((self.root/'projects/.trash').glob('*/PROJECT-0001.json'))),1)
 def test_current_project_can_be_deleted_via_runtime_with_busy_guards(self):
  from app.sound_runtime import SoundRuntime
  app=Application(self.root);app.put_note(2,0,dict(note=50,velocity=100,length=24,probability=100));audio=Mock();audio.native_capture=None;runtime=SoundRuntime(self.root,app,audio,Mock())
  try:
   for busy in (True,False):
    app.playing=busy;done=queue.Queue(1)
    value=dict(self.value('current.json'),operation='project_delete',generation=app.project_generation,group=app.group,pad=app.pad,revision=app.revision)
    runtime.requests.put((value,done,time.monotonic()+4));runtime.poll(time.monotonic());result=done.get_nowait()
    if busy:self.assertIn('error',result);self.assertEqual(app.project['name'],'MY BEAT')
    else:self.assertTrue(result['ok']);self.assertEqual(app.project['name'],'UNTITLED');self.assertFalse(app.notes());self.assertIn(('reload',None),app.actions)
   backup=next((self.root/'projects/.trash').glob('*/Working.json'));self.assertEqual(json.loads(backup.read_text())['name'],'MY BEAT')
  finally:runtime.close()

from tests import test_web_server as http_fixtures
class DeleteHTTPTests(unittest.TestCase):
 setUp=http_fixtures.WebHttpTests.setUp
 stop=http_fixtures.WebHttpTests.stop
 request=http_fixtures.WebHttpTests.request
 def test_delete_routes_require_csrf_and_explicit_confirmation(self):
  from app.model import new_project
  folder=self.root/'projects';folder.mkdir(exist_ok=True);(folder/'PROJECT-0001.json').write_text(json.dumps(new_project()))
  row=json.loads(self.request('GET','/api/projects')[2])[0];value=dict(id=row['id'],name=row['name'],version=row['version'],confirmed=True)
  headers={'X-Machinista-Token':self.library.token,'Content-Type':'application/json'}
  self.assertEqual(self.request('POST','/api/projects/delete')[0],403)
  self.assertEqual(self.request('POST','/api/sounds/delete')[0],403)
  self.assertEqual(self.request('GET','/api/projects/delete')[0],404)
  self.assertEqual(self.request('POST','/api/projects/delete',json.dumps(dict(value,confirmed=False)),headers)[0],400)
  self.assertEqual(self.request('POST','/api/sounds/delete',json.dumps(dict(id='a'*32,confirmed=False)),headers)[0],400)
  status,_,body=self.request('POST','/api/projects/delete',json.dumps(value),headers);self.assertEqual(status,200,body)
  self.assertFalse((folder/row['id']).exists())
