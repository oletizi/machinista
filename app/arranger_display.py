"""Bounded, detached timeline snapshots and native monochrome views."""
from app.clip_arranger import data,length,position,duration,MENU

def state(app):
    selected=app.arranger_selected();first=app.arranger_first;last=first+app.arranger_zoom
    group_first=app.arranger_group//8*8
    clips=tuple(dict(c) for c in data(app.project)['clips'] if group_first<=c['group']<group_first+8 and c['start']<last and c['start']+c['length']>first)
    preview=[]
    if selected:
        g,p=selected['group'],selected['pattern'];span=app.pattern_ticks(g,p)
        for identity,event in app.event_notes(g,p).items():
            for voice in [event,*event.get('poly',{}).values()]:
                preview.append((identity[0],identity[1],min(span,voice.get('length',24))))
                if len(preview)>=256:break
            if len(preview)>=256:break
    return dict(first=first,last=last,groups=tuple((g,app.group_name(g)) for g in range(group_first,min(group_first+8,len(app.project['groups'])))),clips=clips,selected=dict(selected) if selected else None,group=app.arranger_group,cursor=app.arranger_cursor,phase=max(0,app.clock_phase) if app.clip_transport else None,total=length(app.project),follow=app.arranger_follow,rows=tuple(app.arranger_rows()),field=app.arranger_field,menu=app.arranger_menu,preview=tuple(preview),pattern_ticks=app.pattern_ticks(selected['group'],selected['pattern']) if selected else 384,links=sum(c['group']==selected['group'] and c['pattern']==selected['pattern'] for c in data(app.project)['clips']) if selected else 0)

def mono(state,keys,active=(),micro=False,message=''):
    from app.fokus import Canvas
    c=Canvas(128 if micro else 256);w=c.w
    c.header(keys[:3] if micro else keys[:4],active)
    a=state;selected=a['selected'];c.title('CLIPS',position(a['cursor']))
    group_first=a['group']//4*4;groups=[(g,label) for g,label in a['groups'] if group_first<=g<group_first+4]
    x0=15;span=a['last']-a['first'];width=w-20
    for row,(g,label) in enumerate(groups):
        y=26+row*5;c.text(3,y,label,11,font='regular5')
        for clip in a['clips']:
            if clip['group']!=g:continue
            left=x0+round(max(0,clip['start']-a['first'])*width/span);right=x0+round(min(span,clip['start']+clip['length']-a['first'])*width/span)
            chosen=selected and clip['id']==selected['id'];c.rect(left,y,max(1,right-left-1),4,fill=not chosen)
            if chosen and right-left>5:c.rect(left+2,y+1,max(1,right-left-5),2)
    phase=a['phase'] if a['phase'] is not None else a['cursor']
    if a['first']<=phase<=a['last']:
        x=x0+round((phase-a['first'])*width/span);c.rect(x,25,1,21)
    if micro:
        label,value=a['rows'][a['field']];c.field(label,value)
        c.message(message);return c.finish()
    c.text(4,48,'START '+position(selected['start']) if selected else 'ADD AT '+position(a['cursor']),244)
    q=Canvas(256);q.header(keys[4:8],tuple(i-4 for i in active if i>=4));q.title('PATTERN '+str(selected['pattern']+1) if selected else 'NO CLIP')
    if selected:
        q.text(4,27,'LENGTH '+duration(selected['length']),246)
        q.text(4,37,'OFFSET '+position(selected['offset']),246)
        q.text(4,47,'LINKED / '+str(a['links'])+' CLIPS',246)
    else:q.text(4,28,'ADD OR COPY FROM SCENE SONG',246)
    from app.fokus_mk2_style import parameters
    for side,canvas in enumerate((c,q)):parameters(canvas,a['rows'][side*4:side*4+4])
    return c.finish(),q.finish()

def menu_mono(index,micro=False):
    from app.fokus import Canvas
    c=Canvas(128 if micro else 256);c.header(('BACK','SELECT','BACK') if micro else ('BACK','SELECT','',''));c.title('CLIP ACTIONS')
    first=max(0,min(index-1,len(MENU)-3))
    c.rows([('> ' if first+i==index else '  ')+v for i,v in enumerate(MENU[first:first+3])],y=25 if micro else 24,step=8 if micro else 7)
    if micro:return c.finish()
    q=Canvas(256);q.title(MENU[index]);q.text(4,30,'SELECT TO APPLY',245)
    from app.fokus_mk2_style import parameters
    parameters(c,(('SELECT',MENU[index]),None,None,None))
    return c.finish(),q.finish()
