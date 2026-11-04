"""Controller stem workflow and captures from the real display renderers."""
import tempfile,hashlib
from pathlib import Path
from PIL import Image

def catalog(assets):
 from app.model import Application
 from app.controller_inputs import ControllerInputs
 from app.mk1_session import Mk1Surface
 from app.mk2_surface import Mk2Surface
 from app.mk3_surface import Mk3Surface
 from app.mk2_display import Mk2Renderer,snapshot
 from app.mk3_display import Mk3Renderer
 from app.mk3_state import snapshot as color_snapshot
 from app.ni_display import frame
 result=[]
 with tempfile.TemporaryDirectory() as tmp:
  a=Application(tmp);a.page='STEM SEPARATION';a.stem_name='Example Loop.wav';inputs=ControllerInputs(a)
  mono=Mk2Renderer();color=Mk3Renderer()
  try:
   for phase,label,percent in [('IDLE','Ready',0),('SEPARATING','Progress',46),('DONE','Complete',100)]:
    a.stem_status=dict(known=True,ready=True,state=phase,progress=percent,busy=phase=='SEPARATING',message='Separating vocals' if phase=='SEPARATING' else 'Four stems saved in Library / Stems' if phase=='DONE' else 'Start to separate the whole sample',folder='Library/Stems/Example' if phase=='DONE' else '')
    paths={};hashes={};fields={}
    for device,cls in [('mikro',None),('mk1',Mk1Surface),('mk2',Mk2Surface),('mk3',Mk3Surface)]:
     if cls is None:
      im=Image.new('L',(128,64));im.putdata([(1-v)*255 for v in frame(a)]);im=im.convert('RGB');fields[device]=[]
     else:
      surface=cls(a,inputs)
      if device=='mk3':
       st=color_snapshot(surface);im=Image.new('RGB',(976,272),'#29231e')
       for i,one in enumerate(color.images(st)):im.paste(one,(i*496,0))
      else:
       st=snapshot(surface);im=Image.new('RGB',(528,64),'#29231e')
       for i,pixels in enumerate(mono(st)):
        one=Image.new('L',(256,64));one.putdata([v*255 for v in pixels]);im.paste(one,(i*272,0))
      fields[device]=[v for v in st['fields'] if v]
     path=Path(assets)/f'stems-{label.lower()}-{device}.png';im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST).save(path)
     paths[device]=str(path);hashes[device]=hashlib.sha256(im.tobytes()).hexdigest()
    result.append(dict(label='Stem Separation / '+label,page='STEM SEPARATION',paths=paths,hashes=hashes,fields=[],fields_by_device=fields))
  finally:mono.close();color.close()
 return result

def enrich(chapters,lang='en'):
 text=lambda en,de:de if lang=='de' else en
 ch=next(c for c in chapters if c.get('source_title',c['title'])=='Browse folders and load samples')
 ch.setdefault('supplements',[]).append(dict(title=text('Controller: separate a sample into stems','Controller: ein Sample in Stems trennen'),intro=text('Separate a whole WAV or MP3 into Vocals, Drums, Bass and Other without using a computer. The original file and pad assignments stay unchanged. Files are saved under SD CARD / Library / Stems.','Trenne eine ganze WAV- oder MP3-Datei ohne Computer in Vocals, Drums, Bass und Other. Originaldatei und Pad-Zuweisungen bleiben unverändert. Die Dateien werden unter SD CARD / Library / Stems gespeichert.'),figures=['Stem Separation / Progress','Stem Separation / Complete'],steps=[
  dict(mikro=text('In BROWSE, select a WAV or MP3, hold SHIFT and press F3 STEMS. F2 opens START, INSTALL or CANCEL as displayed; F1 BACK returns.','Wähle in BROWSE eine WAV oder MP3, halte SHIFT und drücke F3 STEMS. F2 zeigt START, INSTALL oder CANCEL; F1 BACK führt zurück.'),mk2=text('In BROWSE, select a WAV or MP3 and press display button 7 STEMS. In the stem tool, button 5 starts or installs, 6 cancels and 1 returns.','Wähle in BROWSE eine WAV oder MP3 und drücke Displaytaste 7 STEMS. Im Stem-Werkzeug startet oder installiert Taste 5, Taste 6 bricht ab und Taste 1 führt zurück.')),
  text('You can also open Sampling > Edit and choose the processing operation STEM SEPARATION alongside Truncate and Normalize. Use the displayed STEMS or APPLY action. This uses the selected pad sample, including samples collected with a project. It processes the whole source file, not just the visible zoom or selection.','Alternativ öffnest du Sampling > Edit und wählst bei den Bearbeitungsfunktionen neben Truncate und Normalize STEM SEPARATION. Nutze die angezeigte Aktion STEMS oder APPLY. Als Quelle dient das Sample des gewählten Pads, auch aus einem gesammelten Projekt. Bearbeitet wird die ganze Quelldatei, nicht nur der sichtbare Zoom oder die Auswahl.'),
  text('Stop playback, recording and other processing first. If the optional engine is missing, choose INSTALL and confirm. Installation needs internet; separation afterwards works locally. Then choose START and confirm separation of the whole sample.','Stoppe zuerst Wiedergabe, Aufnahme und andere Bearbeitung. Fehlt die optionale Engine, wähle INSTALL und bestätige. Die Installation benötigt Internet; spätere Trennungen laufen lokal. Wähle danach START und bestätige die Trennung des ganzen Samples.'),
  text('Watch the progress bar; CANCEL stops processing. With DONE, OPEN opens the four completed WAV files in BROWSE. Preview and load them onto pads as usual. This is the same job shown in WebUI, so you cannot start another separation simultaneously.','Beobachte den Fortschrittsbalken; CANCEL stoppt die Bearbeitung. Bei DONE öffnet OPEN die vier fertigen WAV-Dateien in BROWSE. Höre sie vor und lade sie wie gewohnt auf Pads. Die WebUI zeigt denselben Job; eine weitere Trennung kann nicht gleichzeitig starten.')],notes=[(text('Limits','Grenzen'),text('Up to 60 seconds / 64 MiB per source; at least 1.5 GiB free RAM and 512 MiB free storage. Model setup requires more free storage. Separation may leave artifacts. Opening the tool never overwrites or assigns a sample.','Bis 60 Sekunden / 64 MiB pro Quelle; mindestens 1,5 GiB freier RAM und 512 MiB freier Speicher. Die Modelleinrichtung benötigt mehr freien Speicher. Die Trennung kann Artefakte enthalten. Das Öffnen des Werkzeugs überschreibt keine Datei und weist kein Sample zu.'))]))
