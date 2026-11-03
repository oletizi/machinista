"""Current native-effect screenshots and musician-facing EN/DE workflow."""
import json,tempfile,hashlib
from pathlib import Path
from PIL import Image

def effect_catalog(assets):
 from app.model import Application
 from app.controller_inputs import ControllerInputs
 from app.mk1_session import Mk1Surface
 from app.mk2_surface import Mk2Surface
 from app.mk3_surface import Mk3Surface
 from app.mk2_display import Mk2Renderer,snapshot
 from app.mk3_display import Mk3Renderer
 from app.mk3_state import snapshot as color_snapshot
 from app.ni_display import frame
 rows=json.loads((Path(__file__).resolve().parents[1]/'app/native_effects_data.json').read_text());result=[]
 with tempfile.TemporaryDirectory() as root:
  a=Application(root);a.page='PLUGIN';a.control_level=2
  a.plugin_catalog=[dict(uri=r['uri'],name=r['name'],kind='EFFECT',supported=True,builtin=True,ports=[dict(p,index=i) for i,p in enumerate(r['parameters'])]) for r in rows]
  inputs=ControllerInputs(a);surfaces={'mk1':Mk1Surface(a,inputs),'mk2':Mk2Surface(a,inputs),'mk3':Mk3Surface(a,inputs)};mono=Mk2Renderer();color=Mk3Renderer()
  try:
   for row in rows:
    a.track()['name']='Keys';a.track()['plugins']=[dict(uri=row['uri'],kind='EFFECT',controls={p['symbol']:p['default'] for p in row['parameters']})];a.plugin_slot=0;a.plugin_param=0;paths={};hashes={};fields={}
    for device in ('mikro','mk1','mk2','mk3'):
     if device=='mikro':im=Image.new('L',(128,64));im.putdata([(1-v)*255 for v in frame(a)]);im=im.convert('RGB')
     else:
      state=color_snapshot(surfaces[device]) if device=='mk3' else snapshot(surfaces[device]);fields[device]=[(v[0],v[1]) for v in state['fields'] if v]
      if device=='mk3':screens=color.images(state);im=Image.new('RGB',(976,272),'#29231e');im.paste(screens[0],(0,0));im.paste(screens[1],(496,0))
      else:
       im=Image.new('RGB',(528,64),'#29231e')
       for i,pixels in enumerate(mono.draw(state)):im.paste(Image.frombytes('L',(256,64),bytes(v*255 for v in pixels)),(i*272,0))
     hashes[device]=hashlib.sha256(im.tobytes()).hexdigest();path=assets/('effect-'+row['id']+'-'+device+'.png');im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST).save(path);paths[device]=str(path)
    result.append(dict(label='Native Effects / '+row['id'].upper(),page='PLUGIN',paths=paths,hashes=hashes,fields=fields['mk2'],fields_by_device=fields))
  finally:mono.close();color.close()
 return result

def enrich(chapters,lang='en'):
 text=lambda en,de:de if lang=='de' else en
 by={c.get('source_title',c['title']):c for c in chapters}
 ch=by['Channel routing and the Mixer']
 ch.setdefault('supplements',[]).append(dict(title=text('Built-in studio effects','Eingebaute Studioeffekte'),intro=text('These effects are ready to use without installing extra plug-ins: EQ, Compressor, Limiter, Transient, Reverb, Delay, Chorus, Flanger, Phaser, Tremolo, Vibrato and Auto Pan.','Diese Effekte kannst du ohne zusätzliche Plug-ins nutzen: EQ, Compressor, Limiter, Transient, Reverb, Delay, Chorus, Flanger, Phaser, Tremolo, Vibrato und Auto Pan.'),figures=['Native Effects / REVERB','Native Effects / DELAY'],steps=[text('Choose SOUND, GROUP or MASTER. Open the plug-in chain, choose ADD PLUG and select an effect from EFFECT.','Wähle SOUND, GROUP oder MASTER. Öffne die Plug-in-Kette, wähle ADD PLUG und danach unter EFFECT den gewünschten Effekt.'),text('Play your sound and turn the labelled encoders. Reverb offers ROOM, HALL and PLATE. Delay offers STEREO, PING PONG, TAPE and DUB; SYNC follows the project tempo and DIVISION sets the echo spacing.','Spiele deinen Sound und drehe die beschrifteten Encoder. Reverb bietet ROOM, HALL und PLATE. Delay bietet STEREO, PING PONG, TAPE und DUB; SYNC folgt dem Projekttempo und DIVISION bestimmt die Echoabstände.'),text('Adjust MIX to blend the effect with the original sound. Save the project to keep the settings. Use the existing automation workflow to record parameter changes.','Mit MIX mischst du Effekt und Originalsignal. Speichere das Projekt zum Erhalten der Einstellungen. Über die gewohnte Automation kannst du Parameteränderungen aufnehmen.')],notes=[]))
 ch=by['Audio and controller settings']
 ch['notes'].append((text('Smaller audio buffers','Kleinere Audiopuffer'),text('AUDIO > BUFFER offers AUTO, 128, 256, 512, 1024, 2048 and 4096 frames. Try 256 first. If playback crackles, choose a larger value. ACTIVE shows the size actually accepted by the interface. Internal processing still uses 256-frame blocks; queue duration is not the total playing latency.','AUDIO > BUFFER bietet AUTO, 128, 256, 512, 1024, 2048 und 4096 Frames. Probiere zuerst 256. Bei Knacksern wähle einen größeren Wert. ACTIVE zeigt die vom Interface tatsächlich angenommene Größe. Intern wird weiterhin in 256-Frame-Blöcken verarbeitet; die Warteschlangendauer ist nicht die gesamte Spiellatenz.')))
