"""Serialize native patch/FX controls for the isolated exact-DSP audit renderer."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.plugin_profiles import profile,banks
from app.synth_library import URI,asset
from app.synth_patch_fx import effects

def lines(patches,wet=True,root=ROOT):
 ports=profile(URI)['parameters'];rows=[];spec=json.loads((ROOT/'app/native_effects_data.json').read_text());indices={r['uri']:i for i,r in enumerate(spec)}
 for p in patches:
  c=p['controls'];paths=[str(asset(root,p['synth_waves'][str(o)]['id'])) if str(o) in p.get('synth_waves',{}) else '' for o in range(1,5)]
  row=json.dumps(p['name'])+' '+str(int(c['mono']))+' '+' '.join(str(c[v['symbol']]) for v in ports)+' '+' '.join(json.dumps(x) for x in paths)
  inserts=effects(p) if wet else [];row+=' '+str(len(inserts))
  for insert in inserts:
   k=indices[insert['uri']];params=[insert['controls'][v['symbol']] for v in spec[k]['parameters']];row+=' '+str(k)+' '+' '.join(str(x) for x in params+[0]*(32-len(params)))
  rows.append(row)
 return '\n'.join(rows)+'\n'
if __name__=='__main__':
 mode=sys.argv[1];existing=banks(ROOT,profile(URI));patches=[p for b in existing if (b['id']=='spectral-machines' if mode=='new' else any(p.get('effects') for p in b['patches']) and b['id']!='spectral-machines') for p in b['patches'] if mode=='new' or p.get('effects')]
 print(lines(patches,wet='--dry' not in sys.argv),end='')
