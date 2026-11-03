"""Add reviewed native recipes without changing any oscillator/filter controls."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def recipes():return json.loads(Path(__file__).with_name('factory-patch-effects.json').read_text())
def apply(root=ROOT):
 from app.plugin_profiles import validate_bank,profile
 from app.synth_library import URI
 selected=recipes();found=set();changed=[]
 for path in sorted((root/'presets/plugin-banks/machinista-synth').glob('*.json')):
  if path.stem!='factory' and not path.stem.startswith('category-'):continue
  bank=json.loads(path.read_text());dirty=False
  for p in bank['patches']:
   if p['name'] in selected:
    p['effects']=selected[p['name']];found.add(p['name']);dirty=True
  if dirty:
   validate_bank(bank,profile(URI));path.write_text(json.dumps(bank,sort_keys=True,indent=2)+'\n');changed.append(str(path.relative_to(root)))
 assert found==selected.keys(),sorted(selected.keys()-found)
 return dict(patches=len(found),files=changed)
if __name__=='__main__':
 import sys
 sys.path.insert(0,str(ROOT));print(json.dumps(apply()))
