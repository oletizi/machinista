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
