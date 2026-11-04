"""Controller front end for the shared WebUI stem worker; never runs DSP in UI."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import urllib.request
import urllib.error
from app.sound_library import worker_priority

PAGE='STEM SEPARATION'

def initial():return dict(state='IDLE',progress=0,busy=False,ready=False,known=False,message='Checking stem engine...')

def browser_sample(app):
    path=app.browser.selected()
    return path if path and path.suffix.lower() in ('.wav','.mp3') and path.is_file() else None

def open_page(app,browser=False):
    path=browser_sample(app) if browser else app.track().get('sample')
    if not path:app.message='SELECT A SAMPLE FIRST';return
    app.stem_origin=app.page;app.stem_asset={'browser' if browser else 'current':str(path)}
    app.stem_name=Path(path).name;app.page=PAGE;app.message=''
    app.actions.append(('preview_stop',None))
    app.actions.append(('stems',('status',{})))

def start(app):
    state=app.stem_status
    if app.stem_command_pending:return
    if not state.get('known'):app.message='CHECKING STEM ENGINE';return
    if app.playing or app.recording or app.capture_armed or app.capture_started is not None or app.export_busy:
        app.message='STOP PLAY/REC FIRST';return
    if state.get('busy'):app.message='STEMS ALREADY RUNNING';return
    if not state.get('can_separate',True):app.message='STEM ENGINE UNAVAILABLE';return
    install=not state.get('ready')
    def confirmed():
        app.stem_status=dict(app.stem_status,state='REQUESTING',busy=True,progress=0,message='Preparing stem engine...' if install else 'Preparing selected sample...')
        app.stem_command_pending=True
        app.actions.append(('stems',('install' if install else 'start',{} if install else {'asset':dict(app.stem_asset)})))
    app.confirm('INSTALL STEM ENGINE?' if install else 'SEPARATE WHOLE SAMPLE?',confirmed,origin=PAGE)

def cancel(app):
    if app.stem_status.get('busy') and not app.stem_command_pending:
        app.stem_command_pending=True;app.actions.append(('stems',('cancel',{})))

def open_folder(app):
    state=app.stem_status;folder=state.get('folder')
    if state.get('state')!='DONE' or not folder:return
    path=Path(folder)
    if path.is_absolute() or '..' in path.parts or path.parts[:2]!=('Library','Stems'):
        app.message='STEM FOLDER UNAVAILABLE';return
    destination=app.root/'samples'/path
    if not destination.is_dir():app.message='STEM FOLDER MISSING';return
    app.browser.prehear=False;app.browser.directory=destination;app.browser.index=0;app.browser.started=True;app.page='BROWSE'

def keys(app):
    s=app.stem_status
    return ('BACK','CANCEL' if s.get('busy') else ('START' if s.get('ready') else 'INSTALL') if s.get('known') else 'WAIT','OPEN' if s.get('state')=='DONE' and s.get('folder') else '')

def button(app,name,pressed):
    if app.page=='BROWSE' and app.shift and name=='F3':
        if pressed:open_page(app,True)
        return True
    if app.page!=PAGE:return False
    if pressed:
        if name in ('F1','NAV LEFT'):app.page=app.stem_origin
        elif name in ('F2','ENTER','ENCODER PUSH'):
            cancel(app) if app.stem_status.get('busy') else start(app)
        elif name=='F3':open_folder(app)
    # Keep generic encoder/buttons from mutating the selected pad while in this tool.
    return name in ('F1','F2','F3','ENTER','ENCODER PUSH','NAV LEFT','NAV RIGHT')

def display(app):
    s=app.stem_status
    stage=s.get('state','IDLE').replace('_',' ')
    if stage=='IDLE':stage='READY' if s.get('ready') else 'ENGINE NOT INSTALLED'
    return PAGE,((s.get('name') if s.get('busy') else '') or app.stem_name,stage+(' '+str(s.get('progress',0))+'%' if s.get('busy') else ''),s.get('message','')),'WHOLE SAMPLE / MAX 60 SEC'

class Control:
    def __init__(self,base='http://127.0.0.1:8080',call=None):
        self.base=base;self.call=call or self.exchange;self.token=None;self.future=None;self.queue=[];self.next=0
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='controller-stems',initializer=worker_priority)
    def submit(self,value):
        if len(self.queue)<3:self.queue.append(value)
    def exchange(self,value):
        op,body=value
        def get(path):
            with urllib.request.urlopen(self.base+path,timeout=2) as r:return json.load(r)
        try:
            if op!='status':
                self.token=get('/api/session')['token']
                req=urllib.request.Request(self.base+'/api/stems/'+op,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Machinista-Token':self.token},method='POST')
                with urllib.request.urlopen(req,timeout=3) as r:json.load(r)
            return dict(get('/api/stems'),known=True)
        except urllib.error.HTTPError as e:
            try:message=json.load(e).get('error',str(e))
            except (ValueError,OSError):message=str(e)
            raise ValueError(message)
    def poll(self,app,now):
        if self.future is not None and self.future.done():
            try:
                state=self.future.result()
                # A prior separation result must not appear to belong to a new source.
                if state.get('source_path') and not state.get('busy') and state['source_path'] not in app.stem_asset.values():
                    state=dict(state,state='IDLE',progress=0,message='Start to separate the selected whole sample')
                    state.pop('folder',None)
                app.stem_status=state
            except (OSError,ValueError) as e:app.stem_status=dict(app.stem_status,state='ERROR',busy=False,message=str(e))
            self.future=None;app.stem_command_pending=False
        if self.future is None and (self.queue or (app.page==PAGE or app.stem_status.get('busy')) and now>=self.next):
            self.next=now+.5;value=self.queue.pop(0) if self.queue else ('status',{})
            self.future=self.pool.submit(self.call,value)
    def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
