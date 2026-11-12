"""Declarative MK3 controller profiles. Profiles are data only: JSON files are parsed and validated, never executed, imported or evaluated."""
import json,os,re,stat
from dataclasses import dataclass
from pathlib import Path

INPUTS=('4D TURN','4D UP','4D DOWN','4D LEFT','4D RIGHT','4D PUSH','KNOB TURN','KNOB TOUCH')
GROUPS={'parameters':('PAD','SAMPLER','PLUGIN','CHANNEL','INPUT','GROOVE','MACRO','AUDIO LOOP'),'chain':('SAMPLER','PLUGIN','AUDIO LOOP')}
_DIRECTION=frozenset(('cursor.previous','cursor.next','page.previous','page.next','chain.previous','chain.next','transport.back','transport.forward'))
ACTIONS={i:frozenset(('default','none'))|a for i,a in (
    ('4D TURN',frozenset(('cursor.edit','transport.move',*(f'edit.knob{n}' for n in range(1,9))))),
    *((i,_DIRECTION) for i in ('4D UP','4D DOWN','4D LEFT','4D RIGHT','4D PUSH')),
    ('KNOB TURN',frozenset(('cursor.follow',))),('KNOB TOUCH',frozenset(('cursor.follow',))))}
BUILTIN_DIR=Path(__file__).parent/'controller_profiles_data'
MAX_BINDINGS=64;MAX_FILE_BYTES=65536;MAX_NAME=24
_TOP_KEYS=frozenset(('format','name','device','bindings','note'))
_BINDING_KEYS=frozenset(('input','action','pages','shift','cursor','note'))
_IDENT=re.compile(r'[a-z0-9][a-z0-9-]{0,31}')

class ProfileError(ValueError):pass

@dataclass(frozen=True)
class Binding:
    index:int;input:str;action:str;pages:frozenset;shift:bool|None;cursor:bool|None

@dataclass(frozen=True)
class Profile:
    ident:str;name:str;bindings:tuple
    def match(self,input,page,shift,cursor):
        for b in self.bindings:
            if b.input==input and page in b.pages and b.shift in (None,shift) and b.cursor in (None,cursor):return b
        return None
    def shows_cursor(self,page):
        return any(b.action.startswith('cursor.') and page in b.pages and b.cursor in (None,True) for b in self.bindings)

ORIGINAL=Profile('original','Original',())

def _pages(index,value):
    items=[value] if isinstance(value,str) else value
    if not isinstance(items,list) or not items:raise ProfileError(f'binding {index}: pages must be a page name, a group, or a non-empty list of them')
    out=set()
    for p in items:
        if isinstance(p,str) and p in GROUPS:out.update(GROUPS[p])
        elif isinstance(p,str) and p in GROUPS['parameters']:out.add(p)
        else:raise ProfileError(f'binding {index}: unknown page {p!r}')
    return frozenset(out)

def _binding(index,raw):
    if not isinstance(raw,dict):raise ProfileError(f'binding {index}: must be an object')
    extra=sorted(str(k) for k in raw if k not in _BINDING_KEYS)
    if extra:raise ProfileError(f'binding {index}: unknown key {extra[0]!r}')
    inp=raw.get('input')
    if not isinstance(inp,str) or inp not in ACTIONS:raise ProfileError(f'binding {index}: unknown input {inp!r}')
    act=raw.get('action')
    if not isinstance(act,str) or not any(act in a for a in ACTIONS.values()):raise ProfileError(f"binding {index}: unknown action {act!r} (misspelt, or added in a newer Machinista)")
    if act not in ACTIONS[inp]:raise ProfileError(f'binding {index}: action {act!r} is not valid for {inp}')
    for key in ('shift','cursor'):
        if key in raw and not isinstance(raw[key],bool):raise ProfileError(f'binding {index}: {key} must be true or false')
    if 'note' in raw and not isinstance(raw['note'],str):raise ProfileError(f'binding {index}: note must be text')
    pages=_pages(index,raw['pages']) if 'pages' in raw else frozenset(GROUPS['parameters'])
    return Binding(index,inp,act,pages,raw.get('shift'),raw.get('cursor'))

def validate(ident,data):
    if not isinstance(data,dict):raise ProfileError('profile must be a JSON object')
    extra=sorted(str(k) for k in data if k not in _TOP_KEYS)
    if extra:raise ProfileError(f'unknown key {extra[0]!r}')
    fmt=data.get('format')
    if not isinstance(fmt,int) or isinstance(fmt,bool):raise ProfileError('format must be the number 1')
    if fmt>1:raise ProfileError(f'format {fmt} needs a newer Machinista')
    if fmt!=1:raise ProfileError('format must be the number 1')
    if data.get('device')!='mk3':raise ProfileError('device must be "mk3"')
    name=data.get('name')
    if not isinstance(name,str) or not 1<=len(name)<=MAX_NAME or not name.isprintable():raise ProfileError(f'name must be 1 to {MAX_NAME} printable characters')
    if 'note' in data and not isinstance(data['note'],str):raise ProfileError('note must be text')
    raw=data.get('bindings')
    if not isinstance(raw,list):raise ProfileError('bindings must be a list')
    if len(raw)>MAX_BINDINGS:raise ProfileError(f'at most {MAX_BINDINGS} bindings are allowed')
    return Profile(ident,name,tuple(_binding(i,b) for i,b in enumerate(raw)))

class ProfileStore:
    def __init__(self,user_dir,builtin_dir=BUILTIN_DIR):
        self.user_dir=Path(user_dir);self.builtin_dir=Path(builtin_dir);self.profiles={'original':ORIGINAL};self.errors=[]
    def _read(self,path):
        st=os.lstat(path)
        if not stat.S_ISREG(st.st_mode):raise ProfileError('not a regular file')
        if st.st_size>MAX_FILE_BYTES:raise ProfileError(f'file is larger than {MAX_FILE_BYTES} bytes')
        if not _IDENT.fullmatch(path.stem):raise ProfileError('file name must match [a-z0-9][a-z0-9-]{0,31}.json')
        return validate(path.stem,json.loads(path.read_bytes().decode('utf-8')))
    def load(self):
        profiles={'original':ORIGINAL};errors=[]
        for path in sorted(self.builtin_dir.glob('*.json')):
            profiles[path.stem]=validate(path.stem,json.loads(path.read_text('utf-8')))
        builtin=set(profiles)
        user={}
        try:paths=sorted(self.user_dir.glob('*.json')) if self.user_dir.is_dir() else []
        except OSError as e:
            paths=[];errors.append(f'{self.user_dir}: {e}');print(f'controller profile skipped: {errors[-1]}',flush=True)
        for path in paths:
            try:
                if path.stem in builtin:raise ProfileError('name is reserved for a built-in profile')
                user[path.stem]=self._read(path)
            except (OSError,UnicodeError,ValueError,RecursionError) as e:
                errors.append(f'{path.name}: {e}');print(f'controller profile skipped: {errors[-1]}',flush=True)
        profiles.update(sorted(user.items()));self.profiles=profiles;self.errors=errors
    def get(self,ident):return self.profiles.get(ident)
    def ids(self):return list(self.profiles)
