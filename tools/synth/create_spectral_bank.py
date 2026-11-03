"""Original spectral tables and curated patches, with an audit against existing sources.

Development tool only: numpy is not a runtime dependency. No recordings or
manufacturer data. Existing patch controls/assets are preserved.
"""
import copy,hashlib,io,json,math,struct,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.plugin_profiles import banks,profile,validate_bank
from app.synth_library import URI
from app.synth_patch_fx import effects
OUT=ROOT/'output/native-synth/spectral-machines';OUT.mkdir(parents=True,exist_ok=True)
WORK=ROOT/'.build/spectral-machines-20261103';WORK.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'presets/Oscillators';BASE.mkdir(exist_ok=True);(BASE/'.assets').mkdir(exist_ok=True)
P=profile(URI);DEFAULT={p['symbol']:p['default'] for p in P['parameters']}
TARGETS={label:i for i,label in next(p for p in P['parameters'] if p['symbol']=='mod1_target')['choices']}


def read_wave(path):
 data=Path(path).read_bytes();frames,n=struct.unpack_from('<II',data,8);mips=10 if data[:8]==b'MWAVET02' else 1
 return np.frombuffer(data,dtype='<f4',offset=16).reshape(frames,mips,n)[:,0,:].copy()


def feature(x):
 # Spectral amplitudes ignore phase offsets and overall level. Harmonic bins
 # make single-cycle files of different lengths comparable.
 a=np.abs(np.fft.rfft(x,axis=1))[:,1:129]
 if a.shape[1]<128:a=np.pad(a,((0,0),(0,128-a.shape[1])))
 a=np.sqrt(a);return a/np.maximum(1e-12,np.linalg.norm(a,axis=1,keepdims=True))


def generate(kind,seed):
 rng=np.random.default_rng(seed);n=1024;p=np.arange(n)/n;h=np.arange(1,129);result=[]
 phase=rng.uniform(-np.pi,np.pi,len(h))
 for t in np.linspace(0,1,32):
  if kind=='comb':a=(.025+np.sin(h*(.16+.41*t))**12)*np.exp(-h/43)/h**.22
  elif kind=='prism':
   a=sum(np.exp(-.5*((h-k)/(.18+.16*t))**2)*v for k,v in zip((1,7,13,23,37,53,79),(1,.7,.8,.6,.4,.35,.22)))
   a*=.25+.75*(.5+.5*np.sin(h*.21+2*np.pi*t))
  elif kind=='formant':
   a=(.03+.9*np.exp(-.5*((h-(6+31*t))/1.2)**2)+.65*np.exp(-.5*((h-(43-21*t))/2.2)**2)+.3*np.exp(-.5*((h-(72-14*t))/3)**2))/h**.22
  elif kind=='hollow':a=(.03+(h%3==1)*(.6+.4*np.cos(h*.2+t*np.pi))**2)*np.exp(-h/(18+24*t))/h**.3
  elif kind=='cloud':
   centers=np.array((9,21,42,67))+np.sin(t*2*np.pi+np.arange(4))*np.array((5,8,12,17))
   a=sum(np.exp(-.5*((h-c)/(2+i))**2) for i,c in enumerate(centers))*np.exp(-h/100)*(.4+.6*rng.random(len(h)))
  elif kind=='sideband':
   centers=1+np.arange(12)*(3+int(seed%4));weights=np.abs(np.sin(np.arange(12)*(.17+2.5*t)+.3))
   a=sum(w*np.exp(-.5*((h-c)/.3)**2) for w,c in zip(weights,centers))/h**.15
  elif kind=='fold':
   carrier=3+seed%9;modulator=5+seed%5
   v=np.sin(2*np.pi*p*carrier+(1+15*t)*np.sin(2*np.pi*p*modulator))
   v+=.12*np.sin(2*np.pi*p);result.append(v);continue
  else:
   steps=np.array([1 if ((i^(i>>1))&int(seed*13+37)).bit_count()%2 else -1 for i in range(32)])
   x=steps[np.minimum(31,(p*32).astype(int))];y=np.roll(steps,int(1+13*t))[np.minimum(31,(p*32).astype(int))]
   v=(1-t)*x+t*y+.24*np.sin(2*np.pi*p*(5+int(seed%5)))
   # Circular lowpass removes the very highest digital edge before preparation.
   f=np.fft.rfft(v);f[180:]=0;result.append(np.fft.irfft(f,n));continue
  a*=1+.12*np.sin(h*.37+seed);v=np.sin(2*np.pi*p[:,None]*h[None,:]+phase[None,:]*(.2+.8*t))@a
  result.append(v)
 values=np.array(result);values-=values.mean(axis=1,keepdims=True)
 values*=.72/max(1e-9,np.abs(values).max());return values


def write_wave(title,kind,values):
 frames,n=values.shape;raw=b'MWAVE001'+struct.pack('<II',frames,n)+values.astype('<f4').tobytes();identity=hashlib.sha256(raw).hexdigest()[:32]
 row=dict(schema=1,id=identity,name=title,folder='Spectral Machines',tags=['original','spectral',kind],frames=frames,cycle=n,rate=44100,kind='Wavetable')
 path=BASE/'.assets'/(identity+'.mwave')
 if not path.exists():path.write_bytes(raw)
 pcm=values.astype('<f4').tobytes();fmt=struct.pack('<HHIIHH',3,1,44100,176400,4,32)
 wav=b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',len(pcm))+pcm
 (BASE/'.assets'/(identity+'.wav')).write_bytes(wav);(BASE/(identity+'.json')).write_text(json.dumps(row,indent=2)+'\n')
 return {k:row[k] for k in ('id','name','frames','cycle')}


def fx(kind,**values):return dict(uri='urn:machinista:effect:'+kind,controls=values)

def route(c,n,source,target,amount):c.update({f'mod{n}_source':source,f'mod{n}_target':TARGETS[target],f'mod{n}_amount':amount})

def make_patch(title,row,variant,index):
 c=copy.deepcopy(DEFAULT);c.update(output=.8,polyphony=8,velocity=.6,filter1_type=1,filter1_cutoff=14500,filter1_resonance=.06,voice_drift=0,global_drift=0)
 c.update(osc1_wave=32,osc1_level=.62,osc1_shape=.15,osc1_free=0,env1_depth=4,osc2_level=0,osc3_level=0,osc4_level=0)
 waves={'1':row};recipes=[]
 if variant==0:
  name='KEY '+title;c.update(env1_attack=2,env1_decay=950,env1_sustain=.06,env1_release=380,env3_attack=1,env3_decay=370,env3_sustain=0,env3_release=100)
  route(c,1,8,'osc1_shape',.72);route(c,2,1,'osc1_shape',.12)
  recipes=[fx('reverb',type=2,mix=.12,decay=1.7,lowcut=180)]
  if index%2:recipes=[fx('delay',mix=.14,feedback=.22,sync=1,division=4,mode=1,color=6400)]
 elif variant==1:
  name='PAD '+title;c.update(env1_attack=650+index*65,env1_decay=1500,env1_sustain=.78,env1_release=1600,osc1_shape=.5,lfo1_rate=.045+index*.013,lfo1_wave=1)
  route(c,1,10,'osc1_shape',.42);route(c,2,12,'filter1_cutoff',.04)
  c.update(osc2_wave=0,osc2_level=.12,osc2_semi=-12,osc2_pan=.2,filter1_cutoff=6500+index*700)
  recipes=[fx('chorus',mix=.18,depth=.35,rate=.25+index*.04),fx('reverb',mix=.17,decay=3.3,lowcut=230,damping=5400)]
 else:
  name=('BASS ' if index in (0,3,7) else 'LEAD ')+title
  c.update(mono=1,polyphony=4,glide=24 if index%2 else 0,env1_attack=4,env1_decay=480,env1_sustain=.68,env1_release=140,filter1_type=2,filter1_cutoff=1500+index*500,filter1_env=1.2,env2_attack=5,env2_decay=220,env2_sustain=.2,env2_release=120,osc1_shape=.3,lfo1_rate=.22+index*.05)
  route(c,1,10,'osc1_shape',.25)
  if index in (0,3,7):c.update(osc1_semi=-12,osc2_wave=0,osc2_semi=-12,osc2_level=.2)
  else:recipes=[fx('delay',mix=.13,feedback=.24,sync=1,division=5,mode=1,color=5800)]
 p=dict(name=name,description=f'Original {title.lower()} spectrum. '+('Velocity-driven spectral attack.' if variant==0 else 'Slow continuous spectral travel.' if variant==1 else 'Focused monophonic spectral motion.'),controls=c,synth_waves=waves,effects=recipes)
 effects(p);return p


def main():
 existing=banks(ROOT,P);patches=[p for b in existing if b['id'] not in ('factory','init','spectral-machines') for p in b['patches']]
 paths=WORK/'factory-waves'
 if not (paths/'0.mwave').is_file():
  subprocess.run(['c++','-O3','-std=c++20','-I'+str(ROOT/'src'),str(ROOT/'tools/synth/export_wave_catalog.cpp'),'-o',str(WORK/'export_wave_catalog')],check=True)
  subprocess.run([str(WORK/'export_wave_catalog'),str(paths)],check=True)
 from app.synth_library import FACTORY
 old=[];names=[]
 for i,n in enumerate(FACTORY):
  values=read_wave(paths/(str(i)+'.mwave'));f=feature(values);old.extend(f);names.extend([n]*len(f))
 for p in sorted(BASE.glob('*.json')):
  row=json.loads(p.read_text())
  if row.get('folder')=='Spectral Machines':continue
  f=feature(read_wave(BASE/'.assets'/(row['id']+'.mwave')));old.extend(f);names.extend([row['name']]*len(f))
 old=np.array(old);nearest=[]
 for i,a in enumerate(old):
  scores=old@a;scores[np.array(names)==names[i]]=-1;j=int(np.argmax(scores))
  nearest.append(dict(a=names[i],b=names[j],similarity=float(scores[j])))
 families=[('comb','Comb Reactor'),('prism','Prism Alloy'),('formant','Vox Turbine'),('hollow','Hollow Lattice'),('cloud','Spectral Vapor'),('sideband','Sideband Forge'),('fold','Fold Engine'),('binary','Binary Relay')]
 selected=[];newpatches=[];reference=old.copy()
 for index,(kind,title) in enumerate(families):
  best=None
  for seed in range(11,35):
   values=generate(kind,seed);f=feature(values);score=np.max(f@reference.T,axis=1);candidate=float(np.mean(score))
   if best is None or candidate<best[0]:best=(candidate,seed,values,f,score)
  score,seed,values,f,scores=best;j=int(np.argmax(f[len(f)//2]@old.T))
  row=write_wave(title,kind,values);selected.append(dict(name=title,kind=kind,seed=seed,id=row['id'],mean_nearest_spectral_similarity=score,max_nearest_spectral_similarity=float(scores.max()),nearest_existing_at_midpoint=names[j],frame_motion=float(np.mean(np.linalg.norm(np.diff(f,axis=0),axis=1)))))
  reference=np.vstack((reference,f));newpatches.extend(make_patch(title,row,v,index) for v in range(3))
 calibration=Path(__file__).with_name('spectral-calibration.json')
 if calibration.exists():
  corrections=json.loads(calibration.read_text())
  for preset in newpatches:preset['controls'].update(corrections.get(preset['name'],{}))
 bank=dict(schema=1,uri=URI,name='Spectral Machines',description='Eight original moving spectra, 24 contrasting keys/pads/leads/basses, optional native patch effects.',patches=newpatches)
 validate_bank(bank,P);(ROOT/'presets/plugin-banks/machinista-synth/spectral-machines.json').write_text(json.dumps(bank,sort_keys=True,indent=2)+'\n')
 combos={};modulated=0
 for p in patches:
  c=p['controls'];ws=tuple(c[f'osc{i}_wave'] for i in range(1,5) if c[f'osc{i}_on'] and c[f'osc{i}_level']>0)
  key='+'.join(str(w) for w in sorted(ws));combos[key]=combos.get(key,0)+1
  modulated+=any(c[f'mod{i}_source'] and c[f'mod{i}_target'] and c[f'mod{i}_amount'] for i in range(1,33))
 audit=dict(existing_unique_patches=len(patches),existing_sources=len(set(names)),existing_frames=len(old),existing_effect_recipes=sum(bool(p.get('effects')) for p in patches),patches_with_modulation=modulated,common_wave_combinations=sorted(combos.items(),key=lambda x:-x[1])[:12],closest_existing_wave_pairs=sorted(nearest,key=lambda x:-x['similarity'])[:24],new_tables=selected,new_patches=len(newpatches),method='Exact native factory cycles and stored user cycles. Cosine similarity of square-root harmonic amplitudes (128 bins), phase/level independent. Heuristic, not a listening verdict. Candidate selection also compares earlier new tables.')
 (OUT/'waveform-audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(dict(existing_patches=len(patches),new_tables=len(selected),new_patches=len(newpatches),similarities=[round(r['mean_nearest_spectral_similarity'],3) for r in selected])))
if __name__=='__main__':main()
