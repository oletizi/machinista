import copy,json,tempfile,time,unittest,wave
from pathlib import Path
from unittest.mock import Mock,patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk1_session import Mk1Surface
from app.mk2_surface import Mk2Surface
from app.mk3_surface import Mk3Surface
from app.controller_stems import open_page,start,cancel,open_folder,Control,PAGE
from app.surface import PROCESSING

class ControllerStemTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.a=Application(self.root)
  self.path=self.root/'samples/Example.wav'
  with wave.open(str(self.path),'wb') as w:w.setparams((2,2,44100,0,'NONE','NONE'));w.writeframes(bytes(400))
  self.a.browser.directory=self.path.parent;self.a.page='BROWSE'
 def ready(self):self.a.stem_status=dict(known=True,ready=True,state='IDLE',busy=False,can_separate=True,progress=0,message='Ready')
 def test_browse_action_only_for_audio_and_shift_f3_opens_without_loading_pad(self):
  a=self.a;before=copy.deepcopy(a.project);a.shift=True
  self.assertEqual(a.softkeys()[2],'STEMS');a.button('F3',True);a.button('F3',False)
  self.assertEqual(a.page,PAGE);self.assertEqual(a.stem_asset,{'browser':str(self.path)})
  self.assertEqual(a.project,before);a.button('SHIFT',False);a.button('F1',True);self.assertEqual(a.page,'BROWSE')
  a.browser.directory=None;a.shift=True;self.assertEqual(a.softkeys()[2],'')
 def test_sampling_processing_op_opens_current_sample_and_keeps_original(self):
  a=self.a;a.page='SAMPLE EDIT';a.track().update(sample=str(self.path),start=0,end=100)
  before=copy.deepcopy(a.project);a.process_index=PROCESSING.index(PAGE);a.button('F2',True)
  self.assertEqual(a.page,PAGE);self.assertEqual(a.stem_asset,{'current':str(self.path)});self.assertEqual(a.project,before)
  self.ready();start(a);self.assertEqual(a.page,'CONFIRM');a.confirmation[1]()
  self.assertEqual(a.actions[-1],('stems',('start',{'asset':{'current':str(self.path)}})))
 def test_stopped_install_cancel_and_output_folder_flow(self):
  a=self.a;open_page(a,True);self.ready();a.playing=True;start(a);self.assertNotEqual(a.page,'CONFIRM')
  a.playing=False;a.stem_status['ready']=False;start(a);self.assertEqual(a.page,'CONFIRM');a.confirmation[1]()
  self.assertEqual(a.actions[-1],('stems',('install',{})))
  a.page=PAGE;a.stem_command_pending=False;a.stem_status.update(busy=True);cancel(a);self.assertEqual(a.actions[-1],('stems',('cancel',{})))
  folder=self.root/'samples/Library/Stems/Test';folder.mkdir(parents=True)
  a.stem_status=dict(state='DONE',folder='Library/Stems/Test',busy=False);open_folder(a)
  self.assertEqual((a.page,a.browser.directory),('BROWSE',folder))
  a.page=PAGE;a.stem_status['folder']='../config';open_folder(a);self.assertEqual(a.page,PAGE)
 def test_all_fullsize_controllers_expose_browse_and_stem_actions(self):
  a=self.a;inputs=ControllerInputs(a)
  for cls in (Mk1Surface,Mk2Surface,Mk3Surface):
   a.page='BROWSE';a.shift=False;s=cls(a,inputs)
   self.assertEqual(s.softkeys()[6],'STEMS');s.softkey(6);self.assertEqual(a.page,PAGE)
   self.ready();self.assertEqual(s.softkeys()[4],'START');s.softkey(0);self.assertEqual(a.page,'BROWSE')
 def test_background_adapter_polls_without_blocking_and_keeps_cancel_available(self):
  a=self.a;a.page=PAGE;calls=[]
  def call(v):calls.append(v);return dict(known=True,ready=True,state='SEPARATING',busy=True,progress=42,message='Separating drums')
  c=Control(call=call);self.addCleanup(c.close);c.submit(('start',{'asset':{'browser':str(self.path)}}));c.poll(a,1)
  c.future.result(timeout=2);c.poll(a,1.1);self.assertEqual(a.stem_status['progress'],42);self.assertEqual(a.softkeys()[1],'CANCEL')
  self.assertEqual(calls[0][0],'start');self.assertFalse(a.stem_command_pending)
 def test_renderers_show_progress_on_all_controller_sizes(self):
  from app.ni_display import frame
  from app.mk2_display import Mk2Renderer,snapshot
  from app.mk3_state import snapshot as color_snapshot
  from app.mk3_display import Mk3Renderer
  a=self.a;open_page(a,True);self.ready();a.stem_status.update(state='SEPARATING',busy=True,progress=46,message='Separating vocals')
  self.assertEqual(len(frame(a)),128*64);inputs=ControllerInputs(a)
  mono=Mk2Renderer();color=Mk3Renderer();self.addCleanup(mono.close);self.addCleanup(color.close)
  for cls in (Mk1Surface,Mk2Surface):
   s=cls(a,inputs);st=snapshot(s);self.assertEqual(st['stem_separation']['progress'],46);self.assertEqual(len(mono(st)[0]),256*64)
  images=color.images(color_snapshot(Mk3Surface(a,inputs)));self.assertEqual([im.size for im in images],[(480,272),(480,272)])
 def test_assets_hidden_at_root_but_find_and_saved_project_paths_survive(self):
  a=self.a;sample=self.root/'projects/Collected/Samples/keep.wav';sample.parent.mkdir(parents=True);sample.write_bytes(self.path.read_bytes())
  a.browser.refresh([]);a.browser.directory=None
  names=[a.browser.label(p) for p in a.browser.entries()]
  self.assertIn('SOUNDS',names);
  a.browser.directory=a.samples;folder=self.root/'samples/Drums';folder.mkdir();self.assertEqual(a.browser.label(folder),'Drums');self.assertNotIn('PROJECT ASSETS',names);self.assertNotIn('PRESET ASSETS',names)
  self.assertEqual(a.browser.locate(sample),'');self.assertEqual(a.browser.selected(),sample.resolve());self.assertTrue(sample.exists())
