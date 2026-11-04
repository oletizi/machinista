import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app.model import Application,validate_project
from app.clip_arranger import new_clip,data,validate,spans
from app.native_sequence import sequence_commands,NativeSequence
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Mk2Surface
from app.mk3_surface import Mk3Surface
from app.mk1_session import Mk1Surface
from app.mk2_display import snapshot as mono_snapshot,Mk2Renderer
from app.mk3_state import snapshot
from app.mk3_display import Mk3Renderer
from app.ni_display import frame

class ClipTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=Application(self.tmp.name)
 def clip(self,g=0,p=0,start=0,length=384,offset=0):
  c=new_clip(g,p,start,length,offset);self.a.project.setdefault('arrangement',dict(mode='CLIPS',clips=[]))['clips'].append(c);self.a.arranger_id=c['id'];return c
 def test_new_empty_and_legacy_projects_untouched_until_edit(self):
  a=self.a;before=copy.deepcopy(a.project);a.arranger_open();self.assertEqual(a.project,before);self.assertNotIn('arrangement',a.project)
  a.arranger_add();self.assertEqual(len(data(a.project)['clips']),1);a.undo_action();self.assertNotIn('arrangement',a.project)
  a.arranger_add();a.save();b=Application(self.tmp.name);self.assertEqual(data(b.project),data(a.project));validate_project(copy.deepcopy(b.project))
 def test_move_trim_offset_pattern_collision_and_independent_groups(self):
  a=self.a;c=self.clip(start=384,length=768);other=self.clip(start=1536);a.arranger_id=c['id']
  a.arranger_rotate(2,1);self.assertEqual(a.arranger_selected()['start'],768)
  before=copy.deepcopy(a.project);a.arranger_rotate(3,1);self.assertEqual(a.project,before);self.assertIn('OVERLAP',a.message)
  a.arranger_rotate(3,-1);a.arranger_rotate(5,1);self.assertEqual(a.arranger_selected()['offset'],383)
  a.arranger_rotate(4,1);self.assertEqual(a.arranger_selected()['pattern'],1)
  self.clip(g=1,start=768);validate(a.project)
 def test_validation_rejects_bool_nan_overlap_bad_references_duplicate_identity(self):
  self.clip()
  for field,value in [('group',True),('pattern',9999),('start',-1),('length',0),('offset',float('nan')),('id','bad')]:
   p=copy.deepcopy(self.a.project);p['arrangement']['clips'][0][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):validate(p)
  p=copy.deepcopy(self.a.project);p['arrangement']['clips']*=2
  with self.assertRaises(ValueError):validate(p)
  self.clip(start=100)
  with self.assertRaises(ValueError):validate(self.a.project)
 def test_duplicate_delete_unique_undo_and_original_pattern_unchanged(self):
  a=self.a;a.put_note(0,0,dict(note=60,velocity=100,probability=100,length=24));c=self.clip();a.arranger_duplicate();n=a.arranger_selected()
  self.assertEqual((n['start'],n['pattern']),(384,0));a.arranger_unique();p=a.arranger_selected()['pattern'];self.assertNotEqual(p,0)
  self.assertEqual(a.notes(0,p),a.notes(0,0));a.put_note(0,24,dict(note=62,velocity=100,probability=100),pattern=p)
  self.assertNotIn((0,24),a.notes(0,0));a.arranger_delete();self.assertEqual(len(data(a.project)['clips']),1);a.undo_action();self.assertEqual(len(data(a.project)['clips']),2)
 def test_from_song_preserves_legacy_and_copies_master_automation(self):
  a=self.a;a.project['song']=[0,1];a.project['scenes'][0]=[0]+[None]*7;a.project['scenes'][1]=[None,1]+[None]*6
  a.project['scene_lengths']={'0':16,'1':32};old=copy.deepcopy(a.project['song']);a.arranger_from_song()
  clips=data(a.project)['clips'];self.assertEqual([(c['group'],c['pattern'],c['start'],c['length']) for c in clips],[(0,0,0,384),(1,1,384,768)])
  self.assertEqual(a.project['song'],old);self.assertEqual(sum(n for _,n in spans(a)),1152)
 def test_native_compiler_finite_windows_audio_midi_poly_and_metronome(self):
  a=self.a;a.track().update(sample='fixture.wav',end=1000);a.put_note(0,0,dict(note=60,velocity=100,probability=100,length=500));self.clip(start=192,length=384,offset=48)
  a.clip_transport=True;a.active_clips=[False]*8
  commands=sequence_commands(a);self.assertTrue(any(c.startswith('sequence_window 192 576 48 ') for c in commands));self.assertTrue(any(c.startswith('hit ') for c in commands))
  a.track()['playback_mode']='AUDIO';commands=sequence_commands(a);self.assertTrue(any(c.startswith('sequence_audio 0 ') for c in commands));self.assertFalse(any(c.startswith('hit ') for c in commands))
  a.timing()['metro']=True;self.assertNotIn('click ', '\n'.join(sequence_commands(a,metronome=False)))
 def test_transport_gap_stop_seek_restart_and_native_plan_not_rebuilt_at_clip_changes(self):
  a=self.a;self.clip(start=48,length=48);a.arranger_cursor=0;a.arranger_play();a.native_sequence=True
  self.assertTrue(a.playing);a.clock_tick(0);self.assertEqual(a.clock_phase,0);self.assertFalse(a.active_clips[0])
  for t in range(1,49):a.clock_tick(t*a.clock_interval())
  self.assertEqual(a.clock_phase,48);self.assertTrue(a.active_clips[0])
  for t in range(49,97):a.clock_tick(t*a.clock_interval())
  self.assertFalse(a.playing);self.assertEqual(a.clock_phase,96)
  a.arranger_play();self.assertTrue(a.playing);self.assertEqual(a.native_arranger_seek,0);a.button('RESTART',True);self.assertEqual(a.clock_phase,-1)
 def test_automation_uses_clip_offset_and_restores_base_in_gaps(self):
  from app.automation import lane_key
  a=self.a;self.clip(start=96,length=96,offset=48);a.clip_transport=True
  d=(0,'value',-1,'gain');key=lane_key(0,d)
  a.project['groups'][0]['automation']={key:dict(base=80,points={'0':20,'48':60})}
  a.clock_phase=96;a.arranger_update(96);a.automation_tick();self.assertEqual(a.track()['gain'],60)
  a.clock_phase=192;a.arranger_update(192);a.automation_tick();self.assertEqual(a.track()['gain'],80)
 def test_render_and_bindings_all_controllers_keep_model_read_only(self):
  a=self.a;self.clip();a.arranger_open();inputs=ControllerInputs(a);r=Mk3Renderer();m=Mk2Renderer();self.addCleanup(r.close);self.addCleanup(m.close)
  before=copy.deepcopy(a.project)
  for surface in (Mk2Surface(a,inputs),Mk1Surface(a,inputs),Mk3Surface(a,inputs)):
   st=snapshot(surface) if surface.source=='mk3' else mono_snapshot(surface)
   self.assertIn('clip_arranger',st);self.assertEqual(len(surface.fields()),8)
   images=r.images(st) if surface.source=='mk3' else m(st);self.assertEqual(len(images),2)
   self.assertEqual(a.project,before)
  self.assertEqual(len(frame(a)),8192)
  a.page='CLIP MENU';self.assertEqual(len(frame(a)),8192);r.images(snapshot(Mk3Surface(a,inputs)));m(mono_snapshot(Mk2Surface(a,inputs)))
 def test_song_entry_shortcuts_and_mk3_four_direction_navigation(self):
  a=self.a;a.page='SONG';a.button('SHIFT',True);a.button('F2',True);self.assertEqual(a.page,'CLIP ARRANGER');a.button('F2',False);a.button('SHIFT',False)
  s=Mk3Surface(a,ControllerInputs(a));a.page='SONG';s.softkey(7);self.assertEqual(a.page,'CLIP ARRANGER')
  s.softkey(1);self.assertEqual(len(data(a.project)['clips']),1);s.button('MASTER RIGHT',True);s.button('MASTER RIGHT',False);self.assertEqual(a.arranger_cursor,384)
  s.button('MASTER DOWN',True);s.button('MASTER DOWN',False);self.assertEqual(a.arranger_group,1)

class ClipExportTests(unittest.TestCase):
 setUp=ClipTests.setUp
 clip=ClipTests.clip
 def request(self,**values):
  r=dict(mode='SONG',source='MIX',rate=48000,tail=0,group=0,pad=0,pattern=0,scene=0,metadata=[],scene_retrigger='ON',project=self.a.project_for_save());r.update(values);return r
 def test_export_uses_windows_preserves_gaps_and_does_not_export_metronome(self):
  from app.export_audio import compile_export,export_spans
  a=self.a;a.timing()['metro']=True;a.track().update(sample='fixture.wav',end=1000)
  a.put_note(0,0,dict(velocity=100,probability=100,length=100));self.clip(start=96,length=192,offset=48)
  before=copy.deepcopy(a.project);controls,plan,frames=compile_export(a,self.request())
  self.assertEqual(frames,72000);self.assertTrue(any(c.startswith('sequence_window 96 288 48 ') for c in plan))
  self.assertFalse(any(c.startswith('click ') for c in plan));self.assertEqual(a.project,before)
  self.assertEqual(sum(n for _,n in export_spans(a,self.request())),288)
 def test_midi_polyphony_offset_and_gates_cross_other_group_boundaries(self):
  from app.export_midi import compile_midi
  from tests.test_export_midi import read_midi
  a=self.a;a.put_event((0,0,'a'),dict(_id='a',note=60,velocity=100,probability=100,length=384))
  a.put_event((0,0,'b'),dict(_id='b',note=64,velocity=80,probability=100,length=384))
  self.clip(start=0,length=192);self.clip(g=1,start=96,length=96)
  midi,end,count=compile_midi(a,self.request(source='SOUND'))
  self.assertEqual((end,count),(192,2));tracks=read_midi(midi)
  events=tracks[1];self.assertEqual([e[0] for e in events if e[1]&240==144],[0,0]);self.assertEqual([e[0] for e in events if e[1]&240==128],[192,192])
 def test_master_timeline_recording_validation_and_replay(self):
  from app.automation import lane_key
  from app.layout import MASTER
  a=self.a;self.clip(start=0,length=768);a.clip_transport=True;a.playing=a.recording=True;a.shift=True;a.clock_phase=450
  d=(MASTER,'value',-1,'gain');a.remember_modulation();a.capture_automation(d,100,50)
  lane=a.project['arrangement_automation'][lane_key(0,d)];self.assertEqual(lane['points'],{'450':50})
  a.shift=False;a.clock_phase=500;a.automation_cache=None;a.automation_tick();self.assertEqual(a.project['gain'],50)
  validate_project(copy.deepcopy(a.project))
  a.project['arrangement_automation'][lane_key(0,d)]['points']['393215']=25;validate_project(copy.deepcopy(a.project))
  a.page='SONG AUTO';self.assertEqual(a.remote_selected()[0],lane_key(0,d));a.button('F2',True);self.assertFalse(lane.get('enabled',True))

ROOT=Path(__file__).resolve().parent.parent
@unittest.skipUnless((ROOT/'build/audio_engine').is_file() and Path('/usr/share/alsa/alsa.conf').exists(),'Native Linux audio host required')
class ClipAudioTests(unittest.TestCase):
 def test_native_live_clip_plan_handoff_survives_rapid_replacement(self):
  import subprocess,time
  p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  def send(command):p.stdin.write(command+'\n');p.stdin.flush()
  try:
   send('device "-" 48000');self.assertEqual(json.loads(p.stdout.readline())['status'],'idle')
   send('sequence_seek 0 3\nsequence_transport 120 1')
   for i in range(240):
    prefix='sequence_lane 96\nsequence_window 0 393216 0 456\n' if i%2 else ''
    send('sequence_begin\n'+prefix+'sequence_lane 96\nsequence_window 0 393216 0 123\nsequence_event 0 80 100 0\nclick 0 .1\nsequence_commit')
    self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
   time.sleep(.05);send('sequence_status');status=json.loads(p.stdout.readline());self.assertEqual(status['overflow'],0)
   send('quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)
  finally:
   if p.poll() is None:p.kill();p.communicate()
 def test_actual_pcm_has_exact_finite_note_and_audio_loop_windows(self):
  import array,wave
  from app.export_audio import render_export
  for rate in (44100,48000):
   for audio_loop in (False,True):
    with self.subTest(rate=rate,audio=audio_loop),tempfile.TemporaryDirectory() as tmp:
     a=Application(tmp);root=Path(tmp);(root/'build').mkdir();(root/'build/audio_engine').symlink_to(ROOT/'build/audio_engine');source=root/'constant.wav'
     with wave.open(str(source),'wb') as f:f.setparams((1,2,rate,0,'NONE','not compressed'));f.writeframes(array.array('h',[8192]*(rate*2)).tobytes())
     a.track().update(sample=str(source),start=0,end=rate*2,gain=100,sampler=dict(type='ADSR',attack=0,decay=1,sustain=100,release=1))
     if audio_loop:a.track()['playback_mode']='AUDIO';a.track()['audio_loop']=dict(bars=1,tempo=120,stretch=True,tune=0)
     a.put_note(0,0,dict(note=36,velocity=127,probability=100,length=384))
     a.project['arrangement']=dict(mode='CLIPS',clips=[new_clip(0,0,96,96),new_clip(1,0,288,96)])
     request=dict(project=a.project_for_save(),mode='SONG',source='MIX',rate=rate,tail=0,group=0,pad=0,pattern=0,scene=0,metadata=[],scene_retrigger='ON')
     folder=render_export(request,root)
     with wave.open(str(folder/'Mix.wav')) as f:
      self.assertEqual(f.getnframes(),rate*2);v=array.array('h');v.frombytes(f.readframes(f.getnframes()));left=v[::2]
     hits=[i for i,x in enumerate(left) if abs(x)>100]
     self.assertTrue(hits);self.assertGreaterEqual(hits[0],rate//2);self.assertLessEqual(hits[0],rate//2+3)
     self.assertLessEqual(hits[-1],rate+(0 if audio_loop else rate//1000+1)+3);self.assertFalse(any(left[rate+100:]));self.assertFalse(any(left[:rate//2]))
