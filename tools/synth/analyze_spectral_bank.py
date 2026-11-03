"""Reproducible dry-patch comparison; similarity scores are not listening verdicts."""
import json,sys,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'.build/spectral-machines-20261103';OUT=ROOT/'output/native-synth/spectral-machines'

def read(path):
 with wave.open(str(path)) as f:return f.getframerate(),np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float).reshape(-1,2)/32768

def descriptor(path):
 rate,x=read(path);mono=x.mean(axis=1);n=2048;frames=np.lib.stride_tricks.sliding_window_view(mono,n)[::512]
 power=abs(np.fft.rfft(frames*np.hanning(n),axis=1))**2;hz=np.fft.rfftfreq(n,1/rate);edges=np.geomspace(40,18000,49)
 bands=np.array([power[:,(hz>=a)&(hz<b)].sum(axis=1) for a,b in zip(edges[:-1],edges[1:])]).T
 time=(np.arange(len(frames))*512+n/2)/rate;parts=[]
 for lo,hi in ((.11,.35),(.35,.8),(.8,1.35)):
  values=bands[(time>=lo)&(time<hi)].sum(axis=0);parts.append(np.sqrt(values/max(1e-16,values.sum())))
 env=np.array([np.sqrt(np.mean(mono[i:i+2205]**2)) for i in range(0,rate*2,2205)]);env=np.clip(20*np.log10(np.maximum(env/max(1e-10,env.max()),.001)),-60,0)/60
 return np.array(parts),env

def distance(a,b):return float(.75*np.mean(np.linalg.norm(a[0]-b[0],axis=1)/np.sqrt(2))+.25*np.sqrt(np.mean((a[1]-b[1])**2)))

def main():
 old={p.stem:descriptor(p) for p in (WORK/'existing-dry').glob('*.wav')};new={p.stem:descriptor(p) for p in (WORK/'new-dry').glob('*.wav')}
 pairs=[];items=list(old.items())
 for i,(name,a) in enumerate(items):
  for other,b in items[i+1:]:pairs.append(dict(a=name,b=other,distance=distance(a,b)))
 nearest=[]
 for name,a in new.items():
  other,score=min(((other,distance(a,b)) for other,b in old.items()),key=lambda x:x[1]);nearest.append(dict(new=name,existing=other,distance=score))
 report=dict(existing_patches=len(old),new_patches=len(new),closest_existing_pairs=sorted(pairs,key=lambda x:x['distance'])[:24],new_to_existing=nearest,method='Exact native DSP dry single C4, velocity 100, 44.1 kHz. 48 log-frequency power bands across three attack/sustain windows (75%) plus normalized amplitude envelope (25%). Level/phase independent. No perceptual or hardware-emulation claim; review candidates by listening.')
 (OUT/'patch-audit.json').write_text(json.dumps(report,indent=2)+'\n')
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 sys.path.insert(0,str(ROOT));from tools.synth.create_spectral_bank import read_wave
 rows=[json.loads(p.read_text()) for p in (ROOT/'presets/Oscillators').glob('*.json')];rows=sorted((r for r in rows if r.get('folder')=='Spectral Machines'),key=lambda r:r['name'])
 plt.style.use('dark_background');fig,axs=plt.subplots(4,2,figsize=(12,9));fig.suptitle('Machinista · Spectral Machines\nEight original moving wavetables',color='#ff8000',fontsize=18)
 for ax,r in zip(axs.flat,rows):
  values=read_wave(ROOT/'presets/Oscillators/.assets'/(r['id']+'.mwave'))
  for index,color in ((0,'#ff8000'),(15,'#00d9ff'),(31,'#eeeeee')):ax.plot(np.arange(1024)/1024,values[index],color=color,lw=.9,label=f'Frame {index+1}')
  ax.set_title(r['name']);ax.set_xlim(0,1);ax.set_ylim(-.8,.8);ax.set_xticks([]);ax.set_yticks([])
 axs.flat[0].legend(fontsize=7);fig.tight_layout(rect=(0,0,1,.92));fig.savefig(OUT/'wavetables.png',dpi=150);plt.close(fig)
 print(json.dumps(dict(existing=len(old),new=len(new),closest_existing_pairs=report['closest_existing_pairs'][:3],new_distance_range=[min(r['distance'] for r in nearest),max(r['distance'] for r in nearest)])))
if __name__=='__main__':main()
