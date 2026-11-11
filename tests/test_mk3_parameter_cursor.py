import copy,tempfile,unittest
from unittest.mock import patch,Mock
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Field
from app.mk3_surface import Mk3Surface

FULL=[Field('P%d'%i,'0',()) for i in range(8)]

class CursorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.control_level=2
        self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
    def press(self,name,surface=None):
        s=surface or self.s;s.button(name,True);s.button(name,False)
    def same_as_knob(self,knob,delta,action):
        # Same application, same selectors: replay from an identical project.
        start=copy.deepcopy(self.a.project);self.s.rotate(knob,delta)
        expected=copy.deepcopy(self.a.project);self.a.project=copy.deepcopy(start)
        action();self.assertEqual(self.a.project,expected)
        return expected!=start
    def blank(self,*views):
        # views: (page, channel_page) pairs whose fields() report no parameters.
        real=self.s.fields
        def fake():
            a=self.a;key=(a.page,a.channel_page if a.page in ('CHANNEL','PAD') else 0)
            return [None]*8 if key in views else real()
        return patch.object(self.s,'fields',side_effect=fake)
    def test_cursor_defaults_to_first_populated_cell(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.assertEqual(self.s.cursor_cell(),0)
    def test_cursor_snaps_to_nearest_populated_cell(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.s.cursors[self.s.cursor_key()]=1;self.assertEqual(self.s.cursor_cell(),0)   # tie 0/2 -> lower
        self.s.cursors[self.s.cursor_key()]=6;self.assertEqual(self.s.cursor_cell(),3)
    def test_no_cursor_outside_cursor_pages_or_on_plus(self):
        self.a.page='BROWSE';self.assertIsNone(self.s.cursor_cell())
        from app.plus_session import PlusSurface
        p=PlusSurface(self.a,self.inputs);self.a.page='CHANNEL';self.assertIsNone(p.cursor_cell())
    def test_turn_edits_cursor_parameter_like_a_knob(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.assertTrue(self.same_as_knob(3,1,lambda:self.s.master_turn(1)))      # LEVEL
        self.assertTrue(self.same_as_knob(1,1,lambda:self.s.master_turn(1)))      # DEST.
    def test_knob_turn_moves_cursor_but_empty_knob_does_not(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.s.rotate(4,1);self.assertEqual(self.s.cursor_cell(),3)
        self.s.rotate(2,1);self.assertEqual(self.s.cursor_cell(),3)
    def test_cursor_memory_per_layout(self):
        self.a.page='CHANNEL';self.a.channel_page=0;self.s.rotate(4,1)
        self.a.pad=5;self.assertEqual(self.s.cursor_cell(),3)
        with patch.object(self.s,'fields',return_value=FULL), patch.object(self.s,'page_state',return_value=(0,1)):
            self.a.page='PLUGIN'
            with patch.object(self.a,'plugin_selected',return_value={'uri':'urn:a'}):
                self.s.cursors[self.s.cursor_key()]=5;self.assertEqual(self.s.cursor_cell(),5)
            with patch.object(self.a,'plugin_selected',return_value={'uri':'urn:b'}):
                self.assertEqual(self.s.cursor_cell(),0)
    def test_shift_turn_moves_transport_and_leaves_parameters(self):
        self.a.page='CHANNEL';before=copy.deepcopy(self.a.project)
        self.a.shift=True;self.s.master_turn(1);self.a.shift=False
        self.assertGreater(self.a.clock_phase,0);self.assertEqual(before,self.a.project)
    def test_master_modes_take_precedence(self):
        self.a.page='CHANNEL';self.s.cursors[self.s.cursor_key()]=2
        for mode in ('TEMPO','SWING','VOLUME'):
            with self.subTest(mode=mode):
                self.press(mode);start=copy.deepcopy(self.a.project)
                self.s.rotate(0,2);expected=copy.deepcopy(self.a.project)
                self.a.project=copy.deepcopy(start);self.s.master_turn(2)
                self.assertEqual(self.a.project,expected);self.assertNotEqual(expected,start)
                self.press(mode)                                                 # unlatch
    def test_audio_loop_cursor_reaches_later_setting(self):
        self.a.track()['sample']='x.wav';self.a.audio_loop_setup()               # MODE, BARS, STRETCH, TUNE
        self.assertTrue(self.same_as_knob(2,1,lambda:self.s.master_turn(1)))      # BARS
        self.assertEqual(self.s.cursor_cell(),1)
    def view(self):return (self.a.page,self.a.channel_page,self.s.cursor_cell())
    def test_right_moves_within_page_skipping_empty_cells(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.press('MASTER RIGHT');self.assertEqual(self.s.cursor_cell(),2)
        self.press('MASTER RIGHT');self.assertEqual(self.s.cursor_cell(),3)
    def test_right_past_last_cell_changes_page_and_lands_first(self):
        self.a.page='CHANNEL';self.a.channel_page=0;self.s.rotate(4,1)
        self.press('MASTER RIGHT');self.assertEqual(self.view(),('CHANNEL',1,0))
    def test_left_before_first_cell_lands_on_last_of_previous_page(self):
        self.a.page='CHANNEL';self.a.channel_page=1
        self.press('MASTER LEFT');self.assertEqual(self.view(),('CHANNEL',0,3))
    def test_path_is_traversed_both_ways_and_stops_at_ends(self):
        self.a.page='INPUT';self.press('MASTER LEFT');self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',0))
        for _ in range(40):self.press('MASTER RIGHT')
        self.assertEqual((self.a.page,self.s.cursor_cell()),('MACRO',7))
        for _ in range(40):self.press('MASTER LEFT')
        self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',0))
    def test_consecutive_empty_views_are_skipped_from_input_and_groove(self):
        with self.blank(('CHANNEL',0),('CHANNEL',1),('CHANNEL',2),('CHANNEL',3)):
            self.a.page='INPUT';self.s.rotate(2,1)                                # GAIN, last cell
            self.press('MASTER RIGHT');self.assertEqual((self.a.page,self.s.cursor_cell()),('GROOVE',0))
            self.press('MASTER LEFT');self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',1))
    def test_empty_endpoint_matches_page_buttons_and_can_be_left(self):
        with self.blank(('GROOVE',0),('MACRO',0)):
            self.a.page='CHANNEL';self.a.channel_page=3;self.s.cursors[self.s.cursor_key()]=3
            self.press('MASTER RIGHT')
            b=Application(self.tmp.name);b.control_level=2;b.page='CHANNEL';b.channel_page=3
            t=Mk3Surface(b,ControllerInputs(b));t.change_page(1);t.change_page(1)
            keys=('page','channel_page','parameter_kind','parameter_choice','channel_field','groove_field','macro_index','control_views')
            self.assertEqual({k:getattr(self.a,k) for k in keys},{k:getattr(b,k) for k in keys})
            self.assertIsNone(self.s.cursor_cell())
            self.press('MASTER LEFT');self.assertEqual(self.view(),('CHANNEL',3,3))
    def test_shift_left_right_keeps_old_behaviour(self):
        from app.plus_session import PlusSurface
        for page,channel_page,knob in (('CHANNEL',0,1),('CHANNEL',0,4),('CHANNEL',3,4)):
            with self.subTest(page=page,cell=knob-1):
                b=Application(self.tmp.name);b.control_level=2;b.page=page;b.channel_page=channel_page
                old=PlusSurface(b,ControllerInputs(b))
                self.a.page=page;self.a.channel_page=channel_page;self.s.cursors[self.s.cursor_key()]=knob-1
                self.a.shift=b.shift=True;self.press('MASTER RIGHT');self.press('MASTER RIGHT',old);self.a.shift=b.shift=False
                self.assertEqual((self.a.page,self.a.channel_page,self.a.project),(b.page,b.channel_page,b.project))
                self.assertEqual(self.s.cursor_cell(),knob-1)
        self.a.track()['sample']='x.wav';self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.a.page='SAMPLER';self.a.shift=True;self.press('MASTER RIGHT');self.a.shift=False
        self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN',0))
    def test_up_down_still_switch_slots_and_move_transport(self):
        self.a.track()['sample']='x.wav';self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.a.page='SAMPLER';self.press('MASTER DOWN');self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN',0))
        self.press('MASTER UP');self.assertEqual(self.a.page,'SAMPLER')
        self.a.page='CHANNEL';before=copy.deepcopy(self.a.project)
        self.a.settings['arrange_grid']='1/4';cell=self.s.cursor_cell();self.press('MASTER DOWN');self.assertGreater(self.a.clock_phase,0);self.assertEqual(before,self.a.project);self.assertEqual(self.s.cursor_cell(),cell)
    def test_empty_plugin_view_keeps_slot_switching(self):
        self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={}),dict(uri='urn:delay',kind='EFFECT',controls={})]
        self.press('PLUG-IN');self.assertEqual(self.a.page,'PLUGIN');self.assertIsNone(self.s.cursor_cell())
        self.press('MASTER RIGHT');self.assertEqual(self.a.plugin_slot,1)
    def test_held_right_moves_once(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.s.button('MASTER RIGHT',True);self.s.button('MASTER RIGHT',True)
        self.assertEqual(self.s.cursor_cell(),2);self.s.button('MASTER RIGHT',False)
    def session(self,cls=None):
        from app.mk3_session import Mk3Session
        s=(cls or Mk3Session)(self.tmp.name,self.a,self.inputs,{});self.addCleanup(s.close)
        self.s=s.surface;return s
    def test_session_routes_4d_turn_to_cursor(self):
        s=self.session();self.a.page='GROOVE'
        self.assertTrue(self.same_as_knob(2,1,lambda:s.rotate_raw(0,1)))         # cycle
    def test_batched_turn_moves_n_steps_and_clamps(self):
        s=self.session();self.a.page='CHANNEL';self.a.channel_page=0
        for knob,delta in ((1,3),(1,-500),(3,5),(3,-5),(3,10**4)):
            with self.subTest(knob=knob,delta=delta):
                self.same_as_knob(knob,delta,lambda:s.rotate_raw(0,delta))
    def test_session_knobs_still_use_accumulator(self):
        s=self.session();self.a.page='CHANNEL';s.surface.rotate=Mock();s.rotate_raw(3,1)
        s.surface.rotate.assert_not_called()
    def test_plus_session_4d_turn_keeps_transport(self):
        from app.plus_session import PlusSession
        s=self.session(PlusSession);self.a.page='CHANNEL';self.a.settings['arrange_grid']='1/4';before=copy.deepcopy(self.a.project)
        s.rotate_raw(0,1);self.assertGreater(self.a.clock_phase,0);self.assertEqual(before,self.a.project)
    def test_snapshot_and_render_marks(self):
        from app.mk3_state import snapshot
        from app.mk3_display import Mk3Renderer
        r=Mk3Renderer();self.addCleanup(r.close)
        self.a.settings['controllers']['mk3']['color_scheme']='current';self.a.page='MACRO'
        base=snapshot(self.s);base['touches']=();base['cursor']=None
        def render(**changes):return r.images(dict(base,**changes))[0]
        plain=render();cursor=render(cursor=0);touch=render(touches=('KNOB 2 TOUCH',));both=render(cursor=2,touches=('KNOB 3 TOUCH',))
        px=lambda img,x,y:img.getpixel((x,y))
        self.assertNotEqual(px(cursor,60,269),px(plain,60,269));self.assertEqual(px(cursor,60,219),px(plain,60,219))
        self.assertNotEqual(px(touch,180,219),px(plain,180,219));self.assertEqual(px(touch,180,269),px(plain,180,269))
        self.assertNotEqual(px(both,300,219),px(plain,300,219));self.assertNotEqual(px(both,300,269),px(plain,300,269))
        session=self.session();self.a.page='MACRO';session.surface.cursors[session.surface.cursor_key()]=4
        captured={}
        session.output=Mock(submit=lambda state:captured.update(state),submit_leds=lambda *_:None)
        session.palette=[(0,0,0)]+[(127,64,0)]*16
        session.next_led=session.next_frame=0;session.update(1)
        self.assertEqual(captured['cursor'],4)
