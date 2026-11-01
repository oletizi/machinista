"""Dedicated EVENTS follows hold/PIN semantics without stealing editor controls."""
import tempfile
import unittest
from unittest.mock import patch
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.ui_context import pinned

class EventsHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.s=Mk3Surface(self.a,ControllerInputs(self.a))
        self.a.page='CHANNEL'

    def press(self,name):
        self.s.button(name,True);self.s.button(name,False)

    def test_unpinned_release_returns_from_both_editor_pages(self):
        for page in ('PATTERN GRID','GRID EDIT'):
            with self.subTest(page=page):
                self.a.page='CHANNEL';self.s.button('EVENTS',True)
                self.assertEqual(self.a.page,'PATTERN GRID')
                self.a.page=page;self.s.button('EVENTS',False)
                self.assertEqual(self.a.page,'CHANNEL')
                self.assertNotIn('EVENTS',self.a.mode_origins)
                self.assertNotIn('EVENTS',self.a.held_buttons)

    def test_pin_on_button_one_survives_release_and_can_be_closed(self):
        self.s.button('EVENTS',True)
        self.assertEqual(self.s.softkeys()[0],'PIN')
        self.assertEqual(self.s.softkeys()[3],'SELECT')
        self.assertIsNone(self.s.held_mode())
        self.press('DISPLAY 1');self.assertIn('EVENTS',self.a.pinned_modes)
        self.assertTrue(pinned(self.a))
        self.s.button('EVENTS',False);self.assertEqual(self.a.page,'PATTERN GRID')
        self.a.page='GRID EDIT';self.assertTrue(pinned(self.a))
        self.press('EVENTS');self.assertEqual(self.a.page,'CHANNEL')
        # Reopen the pinned mode, disable PIN while held, and release.
        self.s.button('EVENTS',True);self.press('DISPLAY 1')
        self.assertNotIn('EVENTS',self.a.pinned_modes)
        self.assertFalse(pinned(self.a))
        self.s.button('EVENTS',False);self.assertEqual(self.a.page,'CHANNEL')
        restored=Application(self.tmp.name);self.assertNotIn('EVENTS',restored.pinned_modes)

    def test_select_and_follow_keep_their_functions(self):
        self.s.button('EVENTS',True)
        self.press('DISPLAY 4');self.assertNotIn('EVENTS',self.a.pinned_modes)
        follow=self.a.grid_follow;self.press('DISPLAY 3')
        self.assertEqual(self.a.grid_follow,not follow)
        self.s.button('EVENTS',False)

    def test_button_four_range_and_selection_feedback(self):
        from app.mk2_display import snapshot
        self.a.put_note(0,0,dict(velocity=100,note=36))
        self.a.put_note(0,48,dict(velocity=100,note=36))
        self.a.put_note(1,48,dict(velocity=100,note=37))
        self.s.button('EVENTS',True);self.a.grid_step=0
        self.s.button('DISPLAY 4',True);self.s.rotate(0,2)
        self.s.button('DISPLAY 4',False)
        self.assertEqual(self.a.grid_selected,{(0,0),(0,48)})
        self.assertNotIn('EVENTS',self.a.pinned_modes)
        self.a.grid_step=0
        state=snapshot(self.s)
        self.assertIn(3,state['active_left']);self.assertNotIn(0,state['active_left'])
        self.assertEqual(state['keys'][3],'SELECTED')
        self.s.button('EVENTS',False)

    def test_release_does_not_replace_another_chosen_view(self):
        self.s.button('EVENTS',True);self.press('SETTINGS')
        self.s.button('EVENTS',False);self.assertEqual(self.a.page,'SETTINGS')

    def test_repeated_keydown_does_not_reopen_or_reset_editor(self):
        with patch.object(self.a,'open_pattern_grid',wraps=self.a.open_pattern_grid) as opened:
            self.s.button('EVENTS',True);self.a.grid_step=7
            self.s.button('EVENTS',True)
            self.assertEqual(self.a.grid_step,7);self.assertEqual(opened.call_count,1)
        self.s.button('EVENTS',False)

    def test_direct_navigation_editor_can_be_closed_with_events(self):
        self.a.open_pattern_grid();self.press('EVENTS')
        self.assertNotIn(self.a.page,('PATTERN GRID','GRID EDIT'))

if __name__=='__main__':unittest.main()
