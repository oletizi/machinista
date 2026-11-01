"""Exercise all native inserts through the real offline host, state and automation."""
import array,json,math,os,subprocess,sys,wave
from pathlib import Path
engine=Path(sys.argv[1]).resolve();work=Path(sys.argv[2]).resolve();work.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,LV2_PATH='/nonexistent');catalog=json.loads(subprocess.check_output([str(engine),'--plugins'],env=env,text=True))
metadata=json.loads((Path(__file__).resolve().parents[1]/'app/native_effects_data.json').read_text());results=[]
for rate in (44100,48000):
 source=work/f'input-{rate}.f32';samples=array.array('f')
 for i in range(rate*2):
  value=.2*math.sin(math.tau*220*i/rate)+.1*math.sin(math.tau*1760*i/rate);samples.extend((value,.6*value))
 source.write_bytes(samples.tobytes())
 for row in metadata:
  meta=next(p for p in catalog if p['uri']==row['uri']);assert meta['builtin'] and meta['supported'] and meta['kind']=='EFFECT'
  assert [p['symbol'] for p in meta['ports']]==[p['symbol'] for p in row['parameters']]
  ports={p['symbol']:p['index'] for p in meta['ports']};output=work/f'{row["id"]}-{rate}.wav';state=work/f'state-{row["id"]}-{rate}'
  commands=[f'offline_rate {rate}',f'load 0 {rate} '+json.dumps(str(source)),'plugins 0 '+json.dumps(row['uri']),
   'plugin_save 0 0 '+json.dumps(str(state)),'plugin_restore 0 0 '+json.dumps(str(state/'state.ttl')),
   'sequence_begin','sequence_lane 768','sequence_event 0 768 100 0','hit 0 1 1','sequence_commit','sequence_seek 0 1','sequence_transport 120 1 0 0']
  # Host automation reaches the native control atomics and preserves later audio.
  symbol='output' if 'output' in ports else 'input';value=-12 if symbol=='output' else 6
  commands+=['offline_control '+str(rate)+' '+json.dumps(f'plugin_param 0 0 {ports[symbol]} {value}'),
   'render_start '+json.dumps(str(output))+f' {rate*2} 0 16 WAV 0 0','dsp_status','quit','']
  run=subprocess.run([str(engine),'--offline-render'],input='\n'.join(commands),env=env,text=True,capture_output=True,timeout=45)
  assert run.returncode==0,(row['id'],run.stderr);responses=[json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
  assert not any(v.get('status')=='error' for v in responses),(row['id'],responses)
  with wave.open(str(output)) as f:
   assert f.getnchannels()==2 and f.getframerate()==rate;audio=array.array('h');audio.frombytes(f.readframes(f.getnframes()))
  def rms(start,end):
   data=audio[int(start*rate)*2:int(end*rate)*2];return math.sqrt(sum(v*v for v in data)/len(data))
  before=rms(.5,.8);after=rms(1.5,1.8);assert before>100 and after>10,(row['id'],before,after)
  if row['id'] in ('eq','transient','chorus','flanger','phaser','vibrato'):assert .15<after/before<.4,(row['id'],before,after)
  export=next(v for v in responses if v.get('kind')=='export');assert export['overflow']==0
  results.append(dict(effect=row['id'],rate=rate,before=before,after=after,dsp=next(v for v in responses if v.get('kind')=='dsp_status')))
(work/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(dict(renders=len(results),max_block_ms=max(v['dsp']['max_ms'] for v in results),overruns=sum(v['dsp']['overruns'] for v in results))))
