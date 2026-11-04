"""Independent finite Pattern clips on a tick timeline; legacy Scene songs remain intact."""
import copy
import re
import uuid

MAX_CLIPS=512
MAX_TICKS=384*1024
GRIDS=(24,48,96,192,384)
ZOOMS=(384,768,1536,3072,6144,12288)
MENU=('ADD','DUPLICATE','DELETE','MAKE UNIQUE','EDIT NOTES','FROM SONG','FOLLOW','AUTOMATION','SCENES','BACK')

def data(project):return project.get('arrangement',{'mode':'SCENES','clips':[]})
def length(project):return max((c['start']+c['length'] for c in data(project)['clips']),default=0)
def at(project,group,tick):return next((c for c in data(project)['clips'] if c['group']==group and c['start']<=tick<c['start']+c['length']),None)
def local(clip,tick):return tick-clip['start']+clip['offset']
def position(tick):return f'{tick//384+1}:{tick%384//96+1}:{tick%96//24+1}'
def duration(tick):return f'{tick/384:g} BAR' if tick%384==0 else f'{tick/96:g} BEAT'

def validate(project):
    if 'arrangement' not in project:return
    a=project['arrangement']
    if not isinstance(a,dict) or a.get('mode') not in ('SCENES','CLIPS'):raise ValueError('invalid clip arrangement')
    clips=a.get('clips');seen=set();ends={}
    if not isinstance(clips,list) or len(clips)>MAX_CLIPS:raise ValueError('clip limit')
    for c in clips:
        if not isinstance(c,dict) or not isinstance(c.get('id'),str) or not re.fullmatch('[a-f0-9]{32}',c['id']) or c['id'] in seen:raise ValueError('invalid clip identity')
        seen.add(c['id'])
        if any(type(c.get(k)) is not int for k in ('group','pattern','start','length','offset')):raise ValueError('invalid clip fields')
        g=c['group'];p=c['pattern']
        if not 0<=g<len(project['groups']) or not 0<=p<len(project['groups'][g]['patterns']):raise ValueError('invalid clip pattern')
        if c['start']<0 or c['length']<1 or c['start']+c['length']>MAX_TICKS or not 0<=c['offset']<98304:raise ValueError('clip outside timeline')
    for c in sorted(clips,key=lambda c:(c['group'],c['start'])):
        if c['start']<ends.get(c['group'],0):raise ValueError('CLIPS OVERLAP')
        ends[c['group']]=c['start']+c['length']

def new_clip(group,pattern,start,length,offset=0):return dict(id=uuid.uuid4().hex,group=group,pattern=pattern,start=start,length=length,offset=offset)

class ClipArranger:
    def init_arranger(self):
        self.clip_transport=False;self.arranger_group=self.group;self.arranger_cursor=0;self.arranger_id=None
        self.arranger_field=0;self.arranger_first=0;self.arranger_zoom=1536;self.arranger_grid=384;self.arranger_follow=True;self.arranger_menu=0
        self.arranger_origins=None
    def arranger_clip(self,group,tick):
        from bisect import bisect_right
        key=(id(self.project),self.revision)
        if getattr(self,'arranger_cache_key',None)!=key:
            self.arranger_cache_key=key;self.arranger_cache={}
            for c in sorted(data(self.project)['clips'],key=lambda c:c['start']):self.arranger_cache.setdefault(c['group'],[]).append(c)
            self.arranger_cache={g:([c['start'] for c in clips],clips) for g,clips in self.arranger_cache.items()}
        starts,clips=self.arranger_cache.get(group,([],[]));i=bisect_right(starts,tick)-1
        return clips[i] if i>=0 and tick<clips[i]['start']+clips[i]['length'] else None
    def arranger_selected(self):
        return next((c for c in data(self.project)['clips'] if c['id']==self.arranger_id),None)
    def arranger_open(self):
        self.arranger_group=self.group;self.page='CLIP ARRANGER';self.arranger_sync_selection()
    def arranger_sync_selection(self):
        c=self.arranger_selected()
        if c and c['group']==self.arranger_group:return
        c=at(self.project,self.arranger_group,self.arranger_cursor)
        self.arranger_id=c['id'] if c else None
    def arranger_commit(self,clips):
        a=dict(data(self.project),clips=clips,mode='CLIPS');p=dict(self.project,arrangement=a)
        try:validate(p)
        except ValueError as e:self.message=str(e).upper();return False
        self.remember();self.project['arrangement']=a;self.automation_cache=None
        if not clips and self.clip_transport:self.playing=self.recording=False;self.actions.append(('panic',None))
        return True
    def arranger_add(self):
        if self.playing and self.recording:self.message='STOP RECORDING FIRST';return
        pattern=self.active_patterns[self.arranger_group]
        c=new_clip(self.arranger_group,pattern,self.arranger_cursor,self.pattern_ticks(self.arranger_group,pattern))
        if self.arranger_commit([*data(self.project)['clips'],c]):self.arranger_id=c['id'];self.message='CLIP ADDED'
    def arranger_duplicate(self):
        c=self.arranger_selected()
        if not c:self.message='SELECT A CLIP';return
        n=dict(c,id=uuid.uuid4().hex,start=c['start']+c['length'])
        for other in sorted(data(self.project)['clips'],key=lambda c:c['start']):
            if other['group']==n['group'] and n['start']<other['start']+other['length'] and n['start']+n['length']>other['start']:n['start']=other['start']+other['length']
        if self.arranger_commit([*data(self.project)['clips'],n]):self.arranger_id=n['id'];self.arranger_cursor=n['start'];self.arranger_ensure_view()
    def arranger_delete(self):
        c=self.arranger_selected()
        if c and self.arranger_commit([x for x in data(self.project)['clips'] if x['id']!=c['id']]):self.arranger_id=None;self.message='CLIP DELETED'
    def arranger_unique(self):
        c=self.arranger_selected()
        if not c:self.message='SELECT A CLIP';return
        g=self.project['groups'][c['group']];created=set(g['pattern_created'])
        used={x['pattern'] for x in data(self.project)['clips'] if x['group']==c['group']}|{s[c['group']] for s in self.project['scenes']}
        dest=next((i for i in range(len(g['patterns'])) if i not in created and i not in used and not self.notes(c['group'],i) and not any(k.startswith(str(i)+':') for k in g.get('automation',{}))),None)
        if dest is None:self.message='NO FREE PATTERN';return
        self.remember();source=c['pattern'];g['patterns'][dest]=copy.deepcopy(g['patterns'][source])
        g['pattern_lengths'][str(dest)]=self.pattern_steps(c['group'],source)
        for field in ('events','extra_events','automation'):
            for key,value in list(g.get(field,{}).items()):
                if key.startswith(str(source)+':'):g[field][str(dest)+':'+key.split(':',1)[1]]=copy.deepcopy(value)
        g['pattern_created'].append(dest);c['pattern']=dest;self.automation_cache=None;self.message='CLIP HAS OWN PATTERN'
    def arranger_from_song(self):
        clips=[];cursor=0;master={}
        for entry,scene in enumerate(self.project.get('song',[])):
            span=self.scene_steps(scene)*24
            for g,p in enumerate(self.project['scenes'][scene]):
                if p is not None:clips.append(new_clip(g,p,cursor,span,0 if self.settings['scene_retrigger']=='ON' else cursor%self.pattern_ticks(g,p)))
            for name,lane in self.project.get('master_automation',{}).items():
                prefix,tail=name.split(':',1)
                if int(prefix)!=entry:continue
                target=master.setdefault('0:'+tail,dict(copy.deepcopy(lane),points={}))
                target['points'][str(cursor)]=copy.deepcopy(lane['base'])
                target['points'].update({str(cursor+int(t)):copy.deepcopy(v) for t,v in lane['points'].items() if int(t)<span})
                if cursor+span<MAX_TICKS:target['points'][str(cursor+span)]=copy.deepcopy(lane['base'])
            cursor+=span
        if not clips:self.message='SCENE SONG IS EMPTY';return
        if self.arranger_commit(clips):
            self.project['arrangement_automation']=master;self.arranger_cursor=self.arranger_first=0;self.arranger_id=None;self.arranger_sync_selection();self.message='SCENE SONG COPIED'
    def arranger_stop_mode(self):
        if not self.clip_transport:return
        self.clip_transport=False;self.native_sequence_serial=getattr(self,'native_sequence_serial',0)+1
        if self.arranger_origins and len(self.arranger_origins[0])==len(self.project['groups']):
            self.active_patterns,self.active_clips=self.arranger_origins;self.pattern=self.active_patterns[self.group]
        else:self.activate_scene(self.scene)
        self.arranger_origins=None;self.automation_restore()
    def arranger_play(self):
        if self.clip_transport and self.playing:
            self.playing=self.recording=False;self.actions.append(('panic',None));return
        if not length(self.project):self.message='CLIP ARRANGEMENT EMPTY';return
        if not self.clip_transport:self.arranger_origins=(list(self.active_patterns),list(self.active_clips))
        self.clip_transport=True;self.song_playing=False;self.pending_scene=None
        a=dict(data(self.project),mode='CLIPS')
        if data(self.project).get('mode')!='CLIPS':self.remember();self.project['arrangement']=a
        if self.clip_transport and self.clock_phase>=length(self.project):self.arranger_cursor=0
        self.native_arranger_seek=min(self.arranger_cursor,length(self.project)-1)
        self.clock_phase=self.native_arranger_seek-1;self.step=self.clock_phase//24
        self.playing=True;self.actions.append(('panic',None));self.native_transport_revision=getattr(self,'native_transport_revision',0)+1
        self.arranger_update(max(0,self.clock_phase))
    def arranger_update(self,tick):
        previous=self.active_patterns[self.group]
        for g in range(len(self.project['groups'])):
            c=self.arranger_clip(g,tick);self.active_clips[g]=bool(c)
            if c:self.active_patterns[g]=c['pattern']
        if self.page in ('CLIP ARRANGER','CLIP MENU') or self.pattern==previous:self.pattern=self.active_patterns[self.group]
        if self.arranger_follow:
            self.arranger_cursor=tick;self.arranger_ensure_view()
    def arranger_phase(self,group,tick):
        c=self.arranger_clip(group,max(0,tick))
        return local(c,max(0,tick)) if c else None
    def arranger_ensure_view(self):
        if self.arranger_cursor<self.arranger_first or self.arranger_cursor>=self.arranger_first+self.arranger_zoom:
            self.arranger_first=max(0,self.arranger_cursor//self.arranger_zoom*self.arranger_zoom)
    def arranger_rows(self):
        c=self.arranger_selected();clips=sorted((c for c in data(self.project)['clips'] if c['group']==self.arranger_group),key=lambda c:c['start'])
        n=next((i+1 for i,v in enumerate(clips) if c and c['id']==v['id']),0)
        return [('GROUP',self.group_name(self.arranger_group)),('CLIP',(str(n) if c else 'NEW')+'/'+str(len(clips))),('START',position(c['start'] if c else self.arranger_cursor)),('LENGTH',duration(c['length']) if c else '—'),('PATTERN',str(c['pattern']+1) if c else str(self.active_patterns[self.arranger_group]+1)),('OFFSET',position(c['offset']) if c else '1:1:1'),('GRID',dict(zip(GRIDS,('1/16','1/8','1/4','1/2','1 BAR')))[self.arranger_grid]),('ZOOM',duration(self.arranger_zoom))]
    def arranger_rotate(self,index,delta):
        if not delta:return
        c=self.arranger_selected();self.arranger_follow=False
        if index==0:
            self.arranger_group=max(0,min(len(self.project['groups'])-1,self.arranger_group+delta));self.arranger_id=None;self.arranger_sync_selection();return
        if index==1:
            clips=sorted((v for v in data(self.project)['clips'] if v['group']==self.arranger_group),key=lambda v:v['start'])
            if clips:
                old=next((i for i,v in enumerate(clips) if c and v['id']==c['id']),len(clips))
                target=max(0,min(len(clips),old+delta))
                if target==len(clips):self.arranger_id=None;self.arranger_cursor=clips[-1]['start']+clips[-1]['length']
                else:c=clips[target];self.arranger_id=c['id'];self.arranger_cursor=c['start']
                self.arranger_ensure_view()
            return
        if index==6:self.arranger_grid=GRIDS[max(0,min(len(GRIDS)-1,GRIDS.index(self.arranger_grid)+delta))];return
        if index==7:self.arranger_zoom=ZOOMS[max(0,min(len(ZOOMS)-1,ZOOMS.index(self.arranger_zoom)+delta))];self.arranger_ensure_view();return
        unit=24 if self.shift else self.arranger_grid
        if not c:
            if index==2:self.arranger_cursor=max(0,min(MAX_TICKS-1,self.arranger_cursor+delta*unit));self.arranger_ensure_view()
            elif index==4:self.active_patterns[self.arranger_group]=max(0,min(len(self.project['groups'][self.arranger_group]['patterns'])-1,self.active_patterns[self.arranger_group]+delta))
            return
        key={2:'start',3:'length',4:'pattern',5:'offset'}[index];value=c[key]+delta*(1 if key=='pattern' else unit)
        limits={'start':(0,MAX_TICKS-c['length']),'length':(24,MAX_TICKS-c['start']),'pattern':(0,len(self.project['groups'][c['group']]['patterns'])-1),'offset':(0,self.pattern_ticks(c['group'],c['pattern'])-1)}
        value=max(limits[key][0],min(limits[key][1],value))
        if value==c[key]:return
        clips=[dict(v,**{key:value}) if v['id']==c['id'] else v for v in data(self.project)['clips']]
        if self.arranger_commit(clips):
            updated=self.arranger_selected();self.arranger_cursor=updated['start'];self.arranger_ensure_view()
    def arranger_action(self,name):
        if name=='ADD':self.arranger_add()
        elif name=='DUPLICATE':self.arranger_duplicate()
        elif name=='DELETE':self.confirm('DELETE THIS CLIP?',self.arranger_delete,'CLIP ARRANGER')
        elif name=='MAKE UNIQUE':self.arranger_unique()
        elif name=='FROM SONG':
            if data(self.project)['clips']:self.confirm('REPLACE ARRANGEMENT?',self.arranger_from_song,'CLIP ARRANGER')
            else:self.arranger_from_song()
        elif name=='EDIT NOTES':
            c=self.arranger_selected()
            if c:
                self.group=c['group'];self.pattern=c['pattern'];self.open_pattern_grid()
            else:self.message='SELECT A CLIP'
        elif name=='PLAY':self.arranger_play()
        elif name=='FOLLOW':self.arranger_follow=not self.arranger_follow
        elif name=='AUTOMATION':self.page='SONG AUTO';self.midi_map_index=0
        elif name=='SCENES':
            if self.clip_transport:self.playing=self.recording=False;self.actions.append(('panic',None));self.arranger_stop_mode()
            self.remember();self.project['arrangement']=dict(data(self.project),mode='SCENES');self.page='SONG'
        elif name=='BACK':self.page=self.control_home()
    def arranger_button(self,name,pressed):
        if self.page=='SONG' and pressed and self.shift and name=='F2':self.arranger_open();return True
        if self.page not in ('CLIP ARRANGER','CLIP MENU'):return False
        if name=='PLAY' and not self.shift:
            if pressed:self.arranger_play()
            return True
        if name in ('PLAY','RESTART','REC','SHIFT','MUTE'):return False
        if name in ('MAIN','F1','F2','F3','ENTER','ENCODER PUSH','NAV LEFT','NAV RIGHT'):
            if not pressed:return True
            if self.page=='CLIP MENU':
                if name in ('F1','F3','MAIN'):self.page='CLIP ARRANGER'
                elif name in ('F2','ENTER','ENCODER PUSH'):
                    action=MENU[self.arranger_menu];self.page='CLIP ARRANGER';self.arranger_action(action)
                return True
            if name=='F1' and not self.shift:self.page='CLIP MENU';return True
            if name=='F2' and not self.shift:self.arranger_play();return True
            if name=='F3' and not self.shift or name=='MAIN':self.page=self.control_home();return True
            if self.shift and name in ('F1','F2','F3'):self.arranger_action({'F1':'DUPLICATE','F2':'DELETE','F3':'SCENES'}[name]);return True
            if name in ('NAV LEFT','NAV RIGHT'):self.arranger_field=max(0,min(7,self.arranger_field+(-1 if name=='NAV LEFT' else 1)));return True
            if name in ('ENTER','ENCODER PUSH'):self.arranger_action('EDIT NOTES' if self.arranger_selected() else 'ADD');return True
        return False

class PatternSpan(list):
    """Scene-export compatible span with explicit per-group source phase/end."""
    def __init__(self,patterns,offsets,ends):super().__init__(patterns);self.offsets=offsets;self.ends=ends

def spans(app):
    clips=data(app.project)['clips'];bounds=sorted({0,*[v for c in clips for v in (c['start'],c['start']+c['length'])]})
    if len(bounds)<2:raise ValueError('CLIP ARRANGEMENT EMPTY')
    result=[]
    for start,end in zip(bounds,bounds[1:]):
        active=[at(app.project,g,start) for g in range(len(app.project['groups']))]
        result.append((PatternSpan([c['pattern'] if c else None for c in active],[local(c,start) if c else 0 for c in active],[c['start']+c['length'] if c else end for c in active]),end-start))
    return result
