"""MK3 recording peaks and threshold share the MK2 -60..0 dBFS scale."""
import tempfile
import unittest
from PIL import ImageColor
from app.mk3_graphics import Canvas,ACCENT,PANEL,content_y
from app.mk3_style import GREEN
from app.mk3_display import Mk3Renderer
from app.mk3_state import snapshot
from app.mk3_surface import Mk3Surface
from app.model import Application
from app.controller_inputs import ControllerInputs

class CaptureMeterTests(unittest.TestCase):
    def setUp(self):
        self.r=Mk3Renderer();self.addCleanup(self.r.close)
    def test_threshold_and_peak_agree_across_db_range(self):
        for db in (-60,-48,-36,-24,-12,0):
            for compact in (False,True):
                with self.subTest(db=db,compact=compact):
                    c=Canvas(compact_header=compact)
                    peak=10**(db/20)
                    self.r.capture_meter(c,(peak,peak),db)
                    x=18+round(439*(db+60)/60)
                    for y in (100,143):
                        self.assertEqual(c.image.getpixel((x,content_y(y+10,compact))),ImageColor.getrgb(ACCENT))
                        if x>20:self.assertEqual(c.image.getpixel((x-3,content_y(y+10,compact))),ImageColor.getrgb(GREEN))
                        if x<454:self.assertEqual(c.image.getpixel((x+4,content_y(y+10,compact))),ImageColor.getrgb(PANEL))
    def test_minus_20_db_uses_two_thirds_and_channels_are_independent(self):
        c=Canvas();self.r.capture_meter(c,(.1,0))
        green=ImageColor.getrgb(GREEN)
        self.assertEqual(sum(c.image.getpixel((x,110))==green for x in range(18,458)),293)
        self.assertFalse(any(c.image.getpixel((x,153))==green for x in range(18,458)))
    def test_sampling_screen_uses_meter_and_hides_marker_outside_detect(self):
        with tempfile.TemporaryDirectory() as root:
            a=Application(root);a.page='SAMPLING';a.capture_stereo_peak=(.1,.01)
            a.settings['controllers']['mk3']['color_scheme']='current'
            s=Mk3Surface(a,ControllerInputs(a));a.capture_options().update(mode='DETECT',threshold=-24)
            images=self.r.images(snapshot(s));x=18+round(439*.6)
            self.assertEqual(images[1].getpixel((x,84)),ImageColor.getrgb(ACCENT))
            a.capture_options()['mode']='SYNC'
            images=self.r.images(snapshot(s))
            self.assertNotEqual(images[1].getpixel((x,84)),ImageColor.getrgb(ACCENT))
