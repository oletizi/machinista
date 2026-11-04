"""Navigate uses shared native coordinates and cached, legible artwork."""
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageColor
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_display import Mk3Renderer
from app.mk3_state import snapshot
from app.mk3_graphics import BG,LINE,ACCENT
from app import navigation_art

class NavigateArtworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=Application(self.tmp.name);self.surface=Mk3Surface(self.app,ControllerInputs(self.app))
        self.app.settings['controllers']['mk3']['color_scheme']='current'
        self.renderer=Mk3Renderer();self.addCleanup(self.renderer.close)
        self.surface.button('VARIATION',True)

    def test_both_display_cards_have_identical_top_and_bottom(self):
        state=snapshot(self.surface);state['active_left']=();state['active_right']=()
        left,right=self.renderer.draw(state)
        for image in (left,right):
            for slot in range(4):
                x=3+slot*120+57
                self.assertEqual(image.getpixel((x,91)),ImageColor.getrgb(LINE))
                self.assertEqual(image.getpixel((x,205)),ImageColor.getrgb(LINE))
                self.assertEqual(image.getpixel((x,90)),ImageColor.getrgb(BG))
                self.assertEqual(image.getpixel((x,206)),ImageColor.getrgb(BG))

    def test_artwork_is_rgba_and_decoded_once_per_icon(self):
        navigation_art.image.cache_clear();navigation_art._source.cache_clear()
        with patch('PIL.Image.open',wraps=Image.open) as opened:
            for i in range(8):
                normal=navigation_art.image(i);active=navigation_art.image(i,True)
                self.assertIsNotNone(normal);self.assertEqual(normal.size,(76,76))
                self.assertEqual(normal.mode,'RGBA');self.assertIsNotNone(normal.getbbox())
                self.assertLess(normal.getchannel('A').getextrema()[0],255)
                self.assertIs(navigation_art.image(i,True),active)
            self.assertEqual(opened.call_count,8)

    def test_highlight_follows_selected_destination_on_either_display(self):
        self.surface.softkey(5)
        state=snapshot(self.surface);left,right=self.renderer.draw(state)
        self.assertEqual(right.getpixel((180,202)),ImageColor.getrgb(ACCENT))
        self.surface.button('VARIATION',False)
        self.assertEqual(self.app.page,'PATTERN GRID')

if __name__=='__main__':unittest.main()
