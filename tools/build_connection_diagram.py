"""Generate the bilingual, editable setup diagram without external assets."""
from pathlib import Path
from html import escape
ROOT=Path(__file__).resolve().parents[1]

def build(de=False):
 words=(['So verbindest du Machinista','Der Pi macht den Klang. Dein Controller bedient ihn.','Controller','Pads · Regler · Displays','Mikro / MK1 / MK2 / MK3 / +','Raspberry Pi 4 / 5','Machinista läuft hier','SD-Karte: System, Projekte, Samples','USB-Kabel','Bedienung + Displaydaten','Audio: Wähle einen Weg','MK3 / Maschine+','Kopfhörer / Boxen am Controller','Audio läuft über dasselbe USB-Kabel','Mikro / MK1 / MK2','USB-Audiointerface oder Audio-HAT','Kopfhörer / Boxen am Audiogerät','Optional: Browser / WebUI','Handy · Tablet · Computer','Samples übertragen, Sounds bearbeiten','WLAN / Ethernet','Kein Laptop zum Musikmachen nötig','Netzteil für den Pi','Optional: USB-Speicher','Weitere Samples und Projekt-Backups','Keine Controller-Firmware wird ersetzt.','Zurück zur Originalsoftware: USB wieder mit deinem Computer verbinden.','Maschine+ verwendet den Controller-Modus und ebenfalls einen externen Pi.'] if de else ['Connect Machinista','The Pi makes the sound. Your controller operates it.','Controller','Pads · knobs · displays','Mikro / MK1 / MK2 / MK3 / +','Raspberry Pi 4 / 5','Machinista runs here','SD card: system, projects, samples','USB cable','Controls + display data','Audio: choose one route','MK3 / Maschine+','Headphones / speakers on the controller','Audio uses the same USB cable','Mikro / MK1 / MK2','USB audio interface or audio HAT','Headphones / speakers on the audio device','Optional: browser / WebUI','Phone · tablet · computer','Transfer samples, edit Sounds','Wi-Fi / Ethernet','No laptop needed while making music','Power supply for the Pi','Optional: USB storage','More samples and project backups','No controller firmware is replaced.','To use the original software, reconnect USB to your computer.','Maschine+ uses Controller mode and also needs an external Pi.'])
 def t(x,y,s,size=18,color='#f6ede3',weight=400):return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}">{escape(s)}</text>'
 def box(x,y,w,h):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="#252a32" stroke="#46505c"/>'
 def line(path,color='#ff912e'):return f'<path d="{path}" fill="none" stroke="{color}" stroke-width="4" marker-end="url(#arrow)"/>'
 s='<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1000" viewBox="0 0 1200 1000" role="img" aria-labelledby="title desc"><title id="title">'+escape(words[0])+'</title><desc id="desc">'+escape(words[1])+'</desc><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#ff912e"/></marker></defs><rect width="1200" height="1000" rx="20" fill="#13171d"/><g font-family="Arial, sans-serif">'
 s+=t(48,65,'MACHINISTA',18,'#ff912e',700)+t(48,115,words[0],38,weight=700)+t(48,150,words[1],23,'#c9d1da')
 s+=box(48,200,400,250)+box(750,200,402,250)
 # Original generic controller icon with a correctly laid out 4 x 4 grid.
 s+='<g fill="none" stroke="#ff912e" stroke-width="3"><rect x="74" y="225" width="122" height="110" rx="9"/><rect x="86" y="236" width="44" height="15"/><rect x="140" y="236" width="44" height="15"/>'
 for r in range(4):
  for c in range(4):s+=f'<rect x="{112+c*18}" y="{261+r*16}" width="12" height="10" rx="1"/>'
 s+='</g>'+t(220,260,words[2],25,weight=700)+t(220,291,words[3],17)+t(76,385,words[4],21)+t(76,416,'USB',17,'#ff912e',700)
 s+=t(778,251,words[5],28,weight=700)+t(778,293,words[6],22,'#ff912e',700)+t(778,332,words[7],18)
 s+=line('M460 304 H738')+t(487,264,words[8],22,'#ff912e',700)+t(468,344,words[9],17)
 s+=t(48,500,words[10],25,weight=700)+box(48,522,537,153)+box(607,522,545,153)
 s+=t(72,560,words[11],24,'#ff912e',700)+t(72,602,words[12],21)+t(72,640,words[13],19,'#c9d1da')
 s+=t(631,560,words[14],24,'#ff912e',700)+t(631,602,words[15],21)+t(631,640,words[16],18,'#c9d1da')
 s+=box(48,709,537,132)+box(607,709,545,132)+t(72,747,words[17],23,weight=700)+t(72,781,words[18],20)+t(72,815,words[19],18,'#c9d1da')
 s+=t(631,747,words[22],22,weight=700)+t(631,781,words[23],21)+t(631,815,words[24],18,'#c9d1da')
 s+=t(48,880,words[20]+' · '+words[21],20,'#ff912e',700)+t(48,922,words[25],22,weight=700)+t(48,951,words[26],19)+t(48,978,words[27],18,'#c9d1da')
 return s+'</g></svg>'

if __name__=='__main__':
 for language in ('en','de'):(ROOT/'assets/setup'/f'connections-{language}.svg').write_text(build(language=='de'))
