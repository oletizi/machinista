"""Native project list keeps fixed rows and moves the color selection."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import ImageColor
from app.model import Application,new_project
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot
from app.mk2_display import snapshot as mono_snapshot
from app.mk3_display import Mk3Renderer
from app.mk3_graphics import Canvas,ACCENT,BG

class ProjectListTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=Application(self.tmp.name)
        self.app.settings['controllers']['mk3']['color_scheme']='current'
        self.surface=Mk3Surface(self.app,ControllerInputs(self.app))
        self.renderer=Mk3Renderer();self.addCleanup(self.renderer.close)
        self.app.page='PROJECT LOAD'

    def projects(self,count):
        (Path(self.tmp.name)/'projects').mkdir(exist_ok=True)
        for i in range(count):
            p=new_project();p['name']=f'PROJECT {i+1}';p['file_id']=f'PROJECT-{i+1:04}'
            (Path(self.tmp.name)/'projects'/f'PROJECT-{i+1:04}.json').write_text(json.dumps(p))

    def test_snapshot_has_all_names_and_real_index_without_monochrome_arrows(self):
        self.projects(9);self.app.project_choice=7
        names,index=snapshot(self.surface)['project_list']
        self.assertEqual(names,tuple(f'PROJECT {i+1}' for i in range(9)))
        self.assertEqual(index,7)
        self.assertNotIn('project_list',mono_snapshot(self.surface))

    def test_highlight_visits_all_six_rows_in_both_directions(self):
        self.projects(8)
        for index in (*range(6),*reversed(range(6))):
            self.app.project_choice=index
            left,_=self.renderer.draw(snapshot(self.surface))
            for row in range(6):
                self.assertEqual(left.getpixel((450,95+row*21)),ImageColor.getrgb(ACCENT if row==index else BG))

    def test_encoder_moves_highlight_without_shifting_names_inside_a_page(self):
        self.projects(8);original=snapshot(self.surface)['project_list'][0]
        for index in range(1,6):
            self.surface.rotate(0,1);state=snapshot(self.surface)
            self.assertEqual(state['project_list'],(original,index))
            with patch.object(Canvas,'text',autospec=True) as text:
                self.renderer.draw(state)
            rendered=[str(call.args[3]) for call in text.call_args_list]
            self.assertIn('PROJECT 1',rendered);self.assertIn('PROJECT 6',rendered)
            self.assertFalse(any(t.startswith(('>','▸')) for t in rendered))

    def test_page_changes_only_after_last_visible_row_and_returns_back(self):
        self.projects(8)
        for index,visible in ((5,range(1,7)),(6,range(7,9)),(7,range(7,9)),(5,range(1,7))):
            self.app.project_choice=index
            with patch.object(Canvas,'text',autospec=True) as text:
                self.renderer.draw(snapshot(self.surface))
            rendered=[str(call.args[3]) for call in text.call_args_list]
            for i in visible:self.assertIn(f'PROJECT {i}',rendered)
            hidden=set(range(1,9))-set(visible)
            for i in hidden:self.assertNotIn(f'PROJECT {i}',rendered)
            left,_=self.renderer.draw(snapshot(self.surface))
            self.assertEqual(left.getpixel((450,95+(index%6)*21)),ImageColor.getrgb(ACCENT))

    def test_empty_and_stale_selection_do_not_create_a_fake_highlight(self):
        self.app.project_choice=99;state=snapshot(self.surface)
        self.assertEqual(state['project_list'],((),0))
        with patch.object(Canvas,'text',autospec=True) as text:self.renderer.draw(state)
        self.assertIn('No saved projects',[call.args[3] for call in text.call_args_list])
        self.projects(2);self.assertEqual(snapshot(self.surface)['project_list'][1],1)

    def test_manage_actions_use_real_selection_and_fixed_pages_without_arrows(self):
        from app.project_manager import MANAGE
        self.app.page='PROJECT MANAGE'
        for index in (*range(len(MANAGE)),*reversed(range(len(MANAGE)))):
            self.app.manage_index=index;state=snapshot(self.surface)
            self.assertEqual(state['project_list'],(MANAGE,index))
            with patch.object(Canvas,'text',autospec=True) as text:left,_=self.renderer.draw(state)
            rendered=[str(call.args[3]) for call in text.call_args_list]
            self.assertFalse(any(t.startswith(('>','▸')) for t in rendered))
            first=index//6*6
            for row in range(min(6,len(MANAGE)-first)):
                self.assertEqual(left.getpixel((450,95+row*21)),ImageColor.getrgb(ACCENT if first+row==index else BG))
                self.assertIn(MANAGE[first+row],rendered)
            self.assertIn('Press encoder to open',rendered)
        self.assertNotIn('project_list',mono_snapshot(self.surface))

if __name__=='__main__':unittest.main()
