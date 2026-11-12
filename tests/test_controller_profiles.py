import json,os,tempfile,unittest
from unittest import mock
from pathlib import Path
from app.controller_profiles import (validate,ProfileError,ProfileStore,ORIGINAL,GROUPS,INPUTS,ACTIONS,BUILTIN_DIR)

def doc(*bindings,**top):
    d={'format':1,'name':'Test','device':'mk3','bindings':list(bindings)};d.update(top);return d

class ValidateTests(unittest.TestCase):
    def test_minimal_valid_profile(self):
        p=validate('mine',doc());self.assertEqual((p.ident,p.name,p.bindings),('mine','Test',()))
    def test_binding_defaults_expand_to_parameter_pages(self):
        b=validate('x',doc({'input':'4D TURN','action':'cursor.edit'})).bindings[0]
        self.assertEqual((b.index,b.pages,b.shift,b.cursor),(0,frozenset(GROUPS['parameters']),None,None))
    def test_pages_accept_name_group_and_mixed_list(self):
        for pages,expected in (('MACRO',{'MACRO'}),('chain',set(GROUPS['chain'])),(['MACRO','chain'],{'MACRO',*GROUPS['chain']})):
            with self.subTest(pages=pages):
                b=validate('x',doc({'input':'4D LEFT','action':'page.next','pages':pages})).bindings[0]
                self.assertEqual(b.pages,frozenset(expected))
    def test_rejections(self):
        cases={
          'format 2 says newer':(doc(format=2),'newer Machinista'),
          'format bool':(doc(format=True),'format'),
          'device':(doc(device='mk2'),'device'),
          'unknown top key':(doc(extra=1),'extra'),
          'empty name':(doc(name=''),'name'),
          'newline name':(doc(name='a\nb'),'name'),
          'tab name':(doc(name='a\tb'),'name'),
          'top note not string':(doc(note=5),'note'),
          'binding note not string':(doc({'input':'4D TURN','action':'none','note':['x']}),'note'),
          'shift null':(doc({'input':'4D TURN','action':'none','shift':None}),'shift'),
          'cursor null':(doc({'input':'4D TURN','action':'none','cursor':None}),'cursor'),
          'long name':(doc(name='x'*25),'name'),
          'bindings not list':(doc(bindings={}),'bindings'),
          'too many':(doc(*[{'input':'4D TURN','action':'none'}]*65),'64'),
          'unknown input':(doc({'input':'4D SPIN','action':'none'}),"unknown input '4D SPIN'"),
          'unknown action':(doc({'input':'4D TURN','action':'cursor.nxt'}),"unknown action 'cursor.nxt' (misspelt, or added in a newer Machinista)"),
          'action wrong input':(doc({'input':'4D TURN','action':'cursor.next'}),'not valid for 4D TURN'),
          'unknown binding key':(doc({'input':'4D TURN','action':'none','when':1}),'when'),
          'bad page':(doc({'input':'4D TURN','action':'none','pages':'BROWSE'}),'BROWSE'),
          'bad group in list':(doc({'input':'4D TURN','action':'none','pages':['MACRO','chains']}),'chains'),
          'empty pages list':(doc({'input':'4D TURN','action':'none','pages':[]}),'pages'),
          'shift not bool':(doc({'input':'4D TURN','action':'none','shift':1}),'shift'),
          'cursor not bool':(doc({'input':'4D TURN','action':'none','cursor':'yes'}),'cursor'),
          'binding not object':(doc('4D TURN'),'binding 0'),
          'not an object':([], 'object'),
        }
        for label,(data,fragment) in cases.items():
            with self.subTest(label):
                with self.assertRaises(ProfileError) as e:validate('x',data)
                self.assertIn(fragment,str(e.exception))
    def test_note_fields_are_ignored(self):
        validate('x',doc({'input':'4D TURN','action':'none','note':'n'},note='top'))

class MatchTests(unittest.TestCase):
    def test_first_match_wins_in_file_order(self):
        broad={'input':'4D LEFT','action':'page.previous'};narrow={'input':'4D LEFT','action':'cursor.previous','pages':'MACRO'}
        self.assertEqual(validate('a',doc(broad,narrow)).match('4D LEFT','MACRO',False,True).action,'page.previous')
        self.assertEqual(validate('b',doc(narrow,broad)).match('4D LEFT','MACRO',False,True).action,'cursor.previous')
        self.assertEqual(validate('b',doc(narrow,broad)).match('4D LEFT','GROOVE',False,True).action,'page.previous')
    def test_conditions(self):
        p=validate('x',doc({'input':'4D TURN','action':'cursor.edit','shift':False,'cursor':True}))
        self.assertIsNotNone(p.match('4D TURN','CHANNEL',False,True))
        self.assertIsNone(p.match('4D TURN','CHANNEL',True,True))
        self.assertIsNone(p.match('4D TURN','CHANNEL',False,False))
        self.assertIsNone(p.match('4D LEFT','CHANNEL',False,True))
        self.assertIsNone(p.match('4D TURN','BROWSE',False,True))
    def test_omitted_conditions_match_either_value(self):
        p=validate('x',doc({'input':'4D PUSH','action':'page.next'}))
        for shift in (False,True):
            for cursor in (False,True):self.assertIsNotNone(p.match('4D PUSH','GROOVE',shift,cursor))
    def test_shows_cursor(self):
        p=validate('x',doc({'input':'4D TURN','action':'cursor.edit','pages':'MACRO','shift':True},{'input':'4D LEFT','action':'page.next'}))
        self.assertTrue(p.shows_cursor('MACRO'));self.assertFalse(p.shows_cursor('GROOVE'))
        self.assertFalse(validate('y',doc({'input':'4D TURN','action':'cursor.edit','cursor':False})).shows_cursor('MACRO'))
        self.assertFalse(ORIGINAL.shows_cursor('MACRO'))

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dir=Path(self.tmp.name)/'controller-profiles'
    def write(self,name,data):
        self.dir.mkdir(exist_ok=True);path=self.dir/name
        path.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode());return path
    def test_builtins_validate_and_order(self):
        s=ProfileStore(self.dir);s.load()
        self.assertEqual(s.ids(),['original','cursor']);self.assertEqual(s.errors,[])
        self.assertEqual(s.get('cursor').name,'4D cursor');self.assertIs(s.get('original'),ORIGINAL)
    def test_missing_user_folder_is_fine(self):
        s=ProfileStore(self.dir);s.load();self.assertEqual(s.errors,[])
    def test_loader_skips_bad_files_and_keeps_good_ones(self):
        self.write('zeta.json',doc(name='Zeta'));self.write('alpha.json',doc(name='Alpha'))
        self.write('bad-json.json',b'{');self.write('bom.json',b'\xef\xbb\xbf'+json.dumps(doc()).encode())
        self.write('latin.json',b'{"name":"\xff"}');self.write('Upper.json',doc());self.write('cursor.json',doc())
        self.write('big.json',b' '*65537);(self.dir/'dir.json').mkdir()
        os.symlink(self.dir/'alpha.json',self.dir/'link.json');self.write('notes.txt',b'x');self.write('deep.json',b'['*60000)
        s=ProfileStore(self.dir);s.load()
        self.assertEqual(s.ids(),['original','cursor','alpha','zeta'])
        joined='\n'.join(s.errors)
        for name in ('bad-json.json','bom.json','latin.json','Upper.json','cursor.json','big.json','dir.json','link.json','deep.json'):
            self.assertIn(name,joined)
        self.assertNotIn('notes.txt',joined)
    def test_unlistable_user_folder_keeps_builtins(self):
        self.dir.mkdir();real=Path.glob
        def glob(path,pattern):
            if path==self.dir:raise PermissionError('denied')
            return real(path,pattern)
        s=ProfileStore(self.dir)
        with mock.patch.object(Path,'glob',glob):s.load()
        self.assertEqual(s.ids(),['original','cursor']);self.assertEqual(len(s.errors),1);self.assertIn('denied',s.errors[0])
    def test_reload_picks_up_changes(self):
        s=ProfileStore(self.dir);s.load();self.write('mine.json',doc());s.load();self.assertIn('mine',s.ids())
        (self.dir/'mine.json').write_text('{');s.load();self.assertNotIn('mine',s.ids())

class DocsTests(unittest.TestCase):
    def test_documented_examples_validate_and_document_every_name(self):
        import re
        text=(Path(__file__).resolve().parent.parent/'docs'/'CONTROLLER_PROFILES.md').read_text('utf-8')
        blocks=re.findall(r'```json\n(.*?)```',text,re.S)
        self.assertGreaterEqual(len(blocks),3)
        for i,block in enumerate(blocks):
            with self.subTest(block=i):validate('doc',json.loads(block))
        shipped=[json.loads(b) for b in blocks if json.loads(b).get('name')=='4D cursor']
        self.assertEqual(len(shipped),1)
        self.assertEqual(shipped[0],json.loads((BUILTIN_DIR/'cursor.json').read_text('utf-8')))
        names=set(INPUTS)|set(GROUPS)|{a for acts in ACTIONS.values() for a in acts}
        for name in sorted(names):
            with self.subTest(name=name):self.assertIn(f'`{name}`',text)
