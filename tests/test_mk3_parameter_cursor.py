import copy,tempfile,unittest
from unittest.mock import patch
from app.mk2_surface import Field
from app.mk3_surface import Mk3Surface
from app.model import Application
from app.controller_inputs import ControllerInputs

FULL=tuple(Field(f'P{i}',str(i),()) for i in range(8))

class ParameterCursorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
    def press(self,name):self.s.button(name,True);self.s.button(name,False)
    def state(self):
        out={}
        for k,v in vars(self.a).items():
            if k=='selection_project':continue                                # lazily refreshed cache, not state
            if isinstance(v,(int,float,str,bool,list,dict,tuple,set,type(None))):
                try:out[k]=copy.deepcopy(v)
                except Exception:pass
        return out,copy.deepcopy(self.s.cursors)
    def restore(self,snap):
        for k,v in snap[0].items():setattr(self.a,k,copy.deepcopy(v))
        self.s.cursors=copy.deepcopy(snap[1])
    def same_as_knob(self,index,delta,action):
        """Park the cursor on knob `index`, run `action`, then the equivalent knob turn from the same start; True when the app state matches."""
        self.s.cursors[self.s.cursor_key()]=index-1                    # cursor parked on that knob's cell
        start=self.state();action();via_action=self.state()
        self.restore(start);self.s.rotate(index,delta);via_knob=self.state()
        self.assertNotEqual(start[0]['project'],via_knob[0]['project'])
        return via_action[0]==via_knob[0]

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
