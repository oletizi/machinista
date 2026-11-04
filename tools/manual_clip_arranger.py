"""Controller-specific Clip Arranger workflow and actual renderer captures."""
import hashlib,tempfile
from pathlib import Path
from PIL import Image

def catalog(assets):
 from app.model import Application
 from app.clip_arranger import new_clip
 from app.controller_inputs import ControllerInputs
 from app.mk2_surface import Mk2Surface
 from app.mk1_session import Mk1Surface
 from app.mk3_surface import Mk3Surface
 from app.mk2_display import snapshot,Mk2Renderer
 from app.mk3_state import snapshot as color_snapshot
 from app.mk3_display import Mk3Renderer
 from app.ni_display import frame
 result=[]
 with tempfile.TemporaryDirectory() as tmp:
  a=Application(tmp);a.project['name']='FIRST BEAT';a.arranger_open()
  a.project['arrangement']=dict(mode='CLIPS',clips=[new_clip(0,0,0,1536),new_clip(0,1,1536,1536),new_clip(1,0,768,2304),new_clip(2,0,0,768),new_clip(2,1,1536,768),new_clip(3,0,384,1536)])
  for g in range(4):
   for tick in (0,96,192,288):a.put_note(g%4,tick,dict(velocity=100,length=48,probability=100,note=60+g),group=g)
  a.arranger_id=a.project['arrangement']['clips'][0]['id'];a.arranger_zoom=3072;a.arranger_cursor=384;a.clock_phase=384;a.clip_transport=True;a.arranger_field=2
  inputs=ControllerInputs(a);mono=Mk2Renderer();color=Mk3Renderer()
  try:
   for page,name in [('CLIP ARRANGER','Timeline'),('CLIP MENU','Actions')]:
    a.page=page;paths={};hashes={};fields={}
    for device,surface in [('mk1',Mk1Surface(a,inputs)),('mk2',Mk2Surface(a,inputs)),('mk3',Mk3Surface(a,inputs)),('mikro',None)]:
     if device=='mk3':
      st=color_snapshot(surface);im=Image.new('RGB',(976,272),'#29231e')
      for i,part in enumerate(color.images(st)):im.paste(part,(i*496,0))
     elif surface:
      st=snapshot(surface);im=Image.new('RGB',(528,64),'#29231e')
      for i,part in enumerate(mono(st)):
       one=Image.new('L',(256,64));one.putdata([v*255 for v in part]);im.paste(one,(i*272,0))
     else:
      im=Image.new('L',(128,64));im.putdata([(1-v)*255 for v in frame(a)]);im=im.convert('RGB');st=dict(fields=())
     fields[device]=[f for f in st['fields'] if f];hashes[device]=hashlib.sha256(im.tobytes()).hexdigest()
     path=Path(assets)/f'clip-arranger-{name.lower()}-{device}.png';im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST).save(path);paths[device]=str(path)
    result.append(dict(label='Clip Arranger / '+name,page=page,paths=paths,hashes=hashes,fields=fields['mk2'],fields_by_device=fields))
  finally:mono.close();color.close()
 return result

def enrich(chapters,lang='en'):
 de=lang=='de';text=lambda en,ger:ger if de else en
 chapter=next(c for c in chapters if c.get('source_title',c['title'])=='Scenes and Song arrangement')
 chapter.setdefault('supplements',[]).append(dict(title=text('Arrange independent Pattern clips','Unabhängige Pattern-Clips arrangieren'),intro=text('Each Group has a timeline lane. A clip chooses a Pattern, start, length and source offset. Clips repeat their source Pattern and can be placed independently of Scenes. The Scene song remains available.','Jede Gruppe hat eine Timeline-Zeile. Ein Clip wählt Pattern, Start, Länge und Startversatz. Clips wiederholen ihr Pattern und lassen sich unabhängig von Scenes platzieren. Der Scene-Song bleibt erhalten.'),figures=['Clip Arranger / Timeline','Clip Arranger / Actions'],steps=[
 dict(mikro=text('Open VIEW > SONG, then SHIFT + F2 CLIPS. F1 MENU offers the clip actions; F2 plays and F3 returns. Arrows select a field; turn the encoder to change it.','Öffne VIEW > SONG, dann SHIFT + F2 CLIPS. F1 MENU zeigt die Clip-Aktionen, F2 startet und F3 verlässt die Ansicht. Die Pfeile wählen das Feld, der Encoder ändert es.'),mk1=text('Open SONG and press display button 8 CLIPS. The eight encoders edit GROUP, CLIP, START, LENGTH, PATTERN, OFFSET, GRID and ZOOM. Page arrows move the cursor.','Öffne SONG und drücke Displaytaste 8 CLIPS. Die acht Encoder ändern GROUP, CLIP, START, LENGTH, PATTERN, OFFSET, GRID und ZOOM. Die Seitenpfeile bewegen den Cursor.'),mk2=text('Open SONG and press display button 8 CLIPS. The eight encoders edit GROUP, CLIP, START, LENGTH, PATTERN, OFFSET, GRID and ZOOM. Page/master arrows move the cursor.','Öffne SONG und drücke Displaytaste 8 CLIPS. Die acht Encoder ändern GROUP, CLIP, START, LENGTH, PATTERN, OFFSET, GRID und ZOOM. Seiten-/Master-Pfeile bewegen den Cursor.'),mk3=text('Open SONG and press display button 8 CLIPS. Once selected, ARRANGER returns to this timeline. Push the 4D encoder left/right for time and up/down for Group. The eight encoders edit the labelled fields.','Öffne SONG und drücke Displaytaste 8 CLIPS. Danach öffnet ARRANGER diese Timeline. Drücke den 4D-Encoder links/rechts für die Zeit und auf/ab für die Gruppe. Die acht Encoder ändern die beschrifteten Felder.')),
 text('Choose an empty position, a Group and a Pattern, then ADD. CLIP selects an existing clip; turning past the last one selects NEW. START moves it, LENGTH repeats or trims it, and OFFSET changes its source start. SHIFT gives fine 1/16-note steps.','Wähle eine freie Position, Gruppe und Pattern und dann ADD. CLIP wählt einen vorhandenen Clip; hinter dem letzten erscheint NEW. START verschiebt, LENGTH wiederholt oder kürzt und OFFSET ändert den Start im Quellpattern. SHIFT ermöglicht feine 1/16-Schritte.'),
 text('COPY duplicates into free space. DELETE asks before removal. Clips in one Group cannot overlap; different Groups can play together. Undo/Redo and project saving include clip edits.','COPY dupliziert in freien Platz. DELETE fragt vor dem Löschen. Clips derselben Gruppe dürfen sich nicht überlappen; verschiedene Gruppen spielen gleichzeitig. Undo/Redo und Projektspeicherung erfassen Clip-Änderungen.'),
 dict(mikro=text('Choose MENU > MAKE UNIQUE before editing just one occurrence; MENU > EDIT NOTES opens its Events editor. FROM SONG copies the Scene song without removing it.','Wähle MENU > MAKE UNIQUE, bevor du nur ein Vorkommen bearbeiten möchtest; MENU > EDIT NOTES öffnet dessen Events-Editor. FROM SONG kopiert den Scene-Song, ohne ihn zu entfernen.'),mk1=text('SHIFT + display button 3 UNIQUE copies the Pattern for this occurrence. SHIFT + display button 2 EDIT opens Events. FROM SONG copies the Scene sequence; SCENES returns to it.','SHIFT + Displaytaste 3 UNIQUE kopiert das Pattern für dieses Vorkommen. SHIFT + Displaytaste 2 EDIT öffnet Events. FROM SONG kopiert die Scene-Reihenfolge; SCENES kehrt zu ihr zurück.'),mk2=text('SHIFT + display button 3 UNIQUE copies the Pattern for this occurrence. SHIFT + display button 2 EDIT opens Events. FROM SONG copies the Scene sequence; SCENES returns to it.','SHIFT + Displaytaste 3 UNIQUE kopiert das Pattern für dieses Vorkommen. SHIFT + Displaytaste 2 EDIT öffnet Events. FROM SONG kopiert die Scene-Reihenfolge; SCENES kehrt zu ihr zurück.'),mk3=text('SHIFT + display button 3 UNIQUE copies the Pattern for this occurrence. SHIFT + display button 2 EDIT opens Events. FROM SONG copies the Scene sequence; SCENES returns to it.','SHIFT + Displaytaste 3 UNIQUE kopiert das Pattern für dieses Vorkommen. SHIFT + Displaytaste 2 EDIT öffnet Events. FROM SONG kopiert die Scene-Reihenfolge; SCENES kehrt zu ihr zurück.')),
 text('An empty clip timeline is silent. To play a Pattern again, hold PATTERN and select it with its pad. PLAY starts at the timeline cursor and stops after the final clip. FOLLOW returns the display to playback. SONG audio/MIDI export uses the selected CLIPS or SCENES arrangement. Limits: 512 clips, 1024 bars.','Eine leere Clip-Timeline bleibt stumm. Halte PATTERN und wähle es mit seinem Pad, um wieder ein Pattern abzuspielen. PLAY startet am Timeline-Cursor und stoppt nach dem letzten Clip. FOLLOW führt die Anzeige zurück zur Wiedergabe. SONG-Audio-/MIDI-Export nutzt die gewählte CLIPS- oder SCENES-Anordnung. Grenzen: 512 Clips, 1024 Takte.')],notes=[(text('Linked Patterns','Verknüpfte Patterns'),text('Editing a source Pattern changes every linked clip. MAKE UNIQUE copies notes and Pattern modulation into a free Pattern slot, without duplicating samples or plug-ins.','Änderungen am Quellpattern gelten für alle verknüpften Clips. MAKE UNIQUE kopiert Noten und Pattern-Modulation in einen freien Pattern-Platz, ohne Samples oder Plug-ins zu duplizieren.'))]))
