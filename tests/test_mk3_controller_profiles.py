import copy,io,json,tempfile,time,unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.controller_profiles import ORIGINAL
from app.mk3_surface import Mk3Surface

EVENTS=[('turn',1),('button','MASTER LEFT'),('button','MASTER RIGHT'),('button','MASTER UP'),('button','MASTER DOWN'),('button','MASTER PUSH'),('knob',4),('button','KNOB 3 TOUCH')]

class ProfileDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.fresh()
    def fresh(self):
        self.a=Application(self.tmp.name);self.a.control_level=2
        self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
    def use(self,ident,*bindings):
        if bindings:
            folder=Path(self.tmp.name)/'controller-profiles';folder.mkdir(exist_ok=True)
            (folder/f'{ident}.json').write_text(json.dumps({'format':1,'name':ident,'device':'mk3','bindings':list(bindings)}))
        self.a.controller_profiles.load();self.a.settings['controllers']['mk3']['profile']=ident
    def twin(self):
        b=Application(self.tmp.name);b.control_level=2;b.project=copy.deepcopy(self.a.project)
        b.page=self.a.page;b.channel_page=self.a.channel_page;b.shift=self.a.shift
        return b,Mk3Surface(b,ControllerInputs(b))
    def press(self,name,surface=None):
        s=surface or self.s;s.physical_button(name,True);s.physical_button(name,False)
    def sampler(self):
        self.a.track()['sample']='x.wav';self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.a.page='SAMPLER'
    def state(self,a,s):
        return (a.page,a.channel_page,a.plugin_slot,a.project,a.clock_phase,set(s.held),set(s.touched))

    def test_original_profile_is_transparent(self):
        for page in ('CHANNEL','SAMPLER'):
            for shift in (False,True):
                for kind,value in EVENTS:
                    with self.subTest(page=page,shift=shift,event=value):
                        self.fresh()
                        if page=='SAMPLER':self.sampler()
                        else:self.a.page='CHANNEL';self.a.channel_page=0
                        self.a.shift=shift;b,t=self.twin()
                        if kind=='turn':self.s.physical_turn(value);t.rotate(0,value)
                        elif kind=='knob':self.s.physical_rotate(value,1);t.rotate(value,1)
                        else:self.press(value);t.button(value,True);t.button(value,False)
                        self.assertEqual(self.state(self.a,self.s),self.state(b,t))
    def test_default_setting_is_original(self):
        self.assertEqual(self.a.settings['controllers']['mk3']['profile'],'original')
        self.assertIs(self.s.active_profile(),ORIGINAL)
    def test_turn_edit_knob1_dispatches_once_and_edits_once(self):
        self.use('k1',{'input':'4D TURN','action':'edit.knob1'});self.a.page='CHANNEL';self.a.channel_page=0
        b,t=self.twin()
        with patch.object(self.s,'dispatch',wraps=self.s.dispatch) as dispatch,patch.object(self.s,'rotate',wraps=self.s.rotate) as rotate:
            self.s.physical_turn(1)
        dispatch.assert_called_once();rotate.assert_called_once_with(1,1)
        t.rotate(1,1);self.assertEqual(self.a.project,b.project)
    def test_knob_follow_dispatches_once_and_edits_once(self):
        self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0
        with patch.object(self.s,'dispatch',wraps=self.s.dispatch) as dispatch,patch.object(self.s,'rotate',wraps=self.s.rotate) as rotate:
            self.s.physical_rotate(4,1)
        dispatch.assert_called_once();rotate.assert_called_once_with(4,1)
        self.assertEqual(self.s.cursor_cell(),3)
    def test_none_disables_input_and_swallows_release(self):
        # From SAMPLER, LEFT is already at the chain start; step to the plug-in so LEFT has an effect.
        self.sampler();self.s.button('MASTER DOWN',True);self.s.button('MASTER DOWN',False)
        self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN',0))
        self.use('mute',{'input':'4D LEFT','action':'none'})
        before=(self.a.page,self.a.plugin_slot,set(self.s.held));b,t=self.twin();b.plugin_slot=self.a.plugin_slot
        self.s.physical_button('MASTER LEFT',True);self.assertEqual((self.a.page,self.a.plugin_slot),before[:2])
        self.s.physical_button('MASTER LEFT',False);self.assertEqual((self.a.page,self.a.plugin_slot,set(self.s.held)),before)
        self.use('original');self.press('MASTER LEFT');t.button('MASTER LEFT',True);t.button('MASTER LEFT',False)
        self.assertEqual(self.a.page,'SAMPLER');self.assertEqual(self.state(self.a,self.s),self.state(b,t))
    def test_push_page_next(self):
        self.use('push',{'input':'4D PUSH','action':'page.next'});self.a.page='CHANNEL';self.a.channel_page=0
        self.press('MASTER PUSH');self.assertEqual(self.a.channel_page,1)
    def test_not_applicable_falls_back_without_later_bindings(self):
        self.use('na',{'input':'4D LEFT','action':'chain.next'},{'input':'4D LEFT','action':'page.next'})
        self.a.page='CHANNEL';self.a.channel_page=1;self.a.shift=True;b,t=self.twin()
        self.press('MASTER LEFT');t.button('MASTER LEFT',True);t.button('MASTER LEFT',False)
        self.assertEqual(self.state(self.a,self.s),self.state(b,t));self.assertNotEqual(self.a.channel_page,2)
    def test_press_owner_fixed_at_press_time(self):
        for change in ('shift','page','profile'):
            with self.subTest(change=change):
                self.fresh();self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0
                self.s.physical_button('MASTER RIGHT',True);self.assertEqual(self.s.cursor_cell(),2)
                if change=='shift':self.s.physical_button('SHIFT',True)
                elif change=='page':self.a.page='INPUT'
                else:self.a.settings['controllers']['mk3']['profile']='original'
                self.s.physical_button('MASTER RIGHT',False)
                if change=='shift':self.s.physical_button('SHIFT',False)
                self.assertNotIn('MASTER RIGHT',self.s.held)
                self.assertNotIn('NAV RIGHT',self.inputs.buttons);self.assertNotIn('NAV RIGHT',self.a.held_buttons)
                self.assertEqual(self.s.press_owner,{})
        self.fresh();self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0
        with patch.object(self.s,'button',wraps=self.s.button) as button:
            self.s.physical_button('SHIFT',True);self.s.physical_button('MASTER RIGHT',True)
            self.s.physical_button('SHIFT',False);self.s.physical_button('MASTER RIGHT',False)
        button.assert_any_call('MASTER RIGHT',False);self.assertEqual(self.s.press_owner,{})
    def test_repeat_press_while_owned_runs_once(self):
        self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0
        self.s.physical_button('MASTER RIGHT',True);self.s.physical_button('MASTER RIGHT',True)
        self.assertEqual(self.s.cursor_cell(),2);self.s.physical_button('MASTER RIGHT',False)
    def test_knob_touch_none_and_follow(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.use('t',{'input':'KNOB TOUCH','action':'none'})
        self.s.physical_button('KNOB 3 TOUCH',True);self.assertEqual(self.s.touched,set())
        self.s.physical_button('KNOB 3 TOUCH',False);self.assertEqual(self.s.touched,set())
        self.use('f',{'input':'KNOB TOUCH','action':'cursor.follow'})
        self.s.physical_button('KNOB 3 TOUCH',True)
        self.assertEqual(self.s.touched,{'KNOB 3 TOUCH'});self.assertEqual(self.s.cursor_cell(),2)
        self.s.physical_button('KNOB 3 TOUCH',False);self.assertEqual(self.s.touched,set())
    def test_action_error_consumes_event(self):
        self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0;before=copy.deepcopy(self.a.project)
        with patch('app.mk3_actions.run',side_effect=RuntimeError('boom')),redirect_stdout(io.StringIO()) as out:
            self.s.physical_turn(1)
        self.assertEqual(self.a.project,before);self.assertEqual(self.a.message,'PROFILE ERROR')
        self.assertIn("RuntimeError('boom')",out.getvalue())
        self.s.physical_turn(1);self.assertNotEqual(self.a.project,before)
    def test_failed_button_action_keeps_profile_ownership(self):
        self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0
        with patch('app.mk3_actions.run',side_effect=RuntimeError),redirect_stdout(io.StringIO()),patch.object(self.s,'button',wraps=self.s.button) as button:
            self.s.physical_button('MASTER RIGHT',True)
            self.s.physical_button('SHIFT',True);self.a.channel_page=2
            self.s.physical_button('MASTER RIGHT',False)
        self.assertEqual(self.s.press_owner,{});self.assertNotIn('MASTER RIGHT',self.s.held)
        self.assertNotIn(('MASTER RIGHT',False),[c.args for c in button.call_args_list])
        self.assertNotIn('NAV RIGHT',self.inputs.buttons);self.assertNotIn('NAV RIGHT',self.a.held_buttons)
    def test_update_lock_blocks_profile_actions(self):
        self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0
        self.a.update_lock_until=time.monotonic()+60;before=copy.deepcopy(self.a.project)
        self.s.physical_turn(1);self.press('MASTER RIGHT')
        self.assertEqual(self.a.project,before);self.assertEqual(self.s.cursor_cell(),0)
    def test_master_mode_overrides_binding(self):
        self.use('k1',{'input':'4D TURN','action':'edit.knob1'});self.a.page='CHANNEL';self.a.channel_page=0
        b,t=self.twin();self.press('TEMPO');t.button('TEMPO',True);t.button('TEMPO',False)
        start=copy.deepcopy(self.a.project)
        self.s.physical_turn(2);t.rotate(0,2)
        self.assertEqual(self.a.project,b.project);self.assertNotEqual(self.a.project,start)
    def test_missing_profile_falls_back_once(self):
        self.a.settings['controllers']['mk3']['profile']='gone'
        self.assertIs(self.s.active_profile(),ORIGINAL);self.assertEqual(self.a.message,'PROFILE NOT FOUND')
        self.a.message='';self.assertIs(self.s.active_profile(),ORIGINAL);self.assertEqual(self.a.message,'')
        self.assertEqual(self.a.settings['controllers']['mk3']['profile'],'gone')
    def test_plus_ignores_profiles(self):
        from app.plus_session import PlusSurface
        p=PlusSurface(self.a,self.inputs);self.use('cursor');self.a.page='CHANNEL';self.a.channel_page=0
        self.a.settings['arrange_grid']='1/4';before=copy.deepcopy(self.a.project)
        p.physical_turn(1);self.assertGreater(self.a.clock_phase,0);self.assertEqual(self.a.project,before)

if __name__=='__main__':unittest.main()
