"""Optional native insert recipes owned by a Synth patch, separate from user FX."""
import json
import math
from functools import lru_cache
from pathlib import Path

URI='urn:machinista:instrument:synth'
MARK='synth_patch_fx'

@lru_cache(maxsize=1)
def specifications():
    rows=json.loads(Path(__file__).with_name('native_effects_data.json').read_text())
    return {r['uri']:r for r in rows if r['id'] in ('chorus','delay','reverb')}

def effects(preset):
    """Only our three built-in processors; no external bundles or state paths."""
    rows=preset.get('effects',[])
    if not isinstance(rows,list) or len(rows)>3:raise ValueError('Maximum three patch effects.')
    result=[];seen=set();specs=specifications()
    for row in rows:
        if not isinstance(row,dict) or set(row)-{'uri','controls'}:raise ValueError('Invalid patch effect.')
        uri=row.get('uri')
        if not isinstance(uri,str) or uri not in specs or uri in seen:raise ValueError('Choose unique native Chorus, Delay or Reverb.')
        seen.add(uri);ports={p['symbol']:p for p in specs[uri]['parameters']};controls=row.get('controls',{})
        if not isinstance(controls,dict) or set(controls)-ports.keys():raise ValueError('Unknown patch effect parameter.')
        values={k:p['default'] for k,p in ports.items()}
        for k,v in controls.items():
            p=ports[k]
            if type(v) not in (int,float) or not math.isfinite(v) or not p['min']<=v<=p['max'] or p.get('integer') and int(v)!=v:raise ValueError('Invalid patch effect parameter.')
            values[k]=v
        result.append(dict(uri=uri,name=specs[uri]['name'],kind='EFFECT',bypass=False,controls=values,**{MARK:True}))
    return result

def prepare(app,selected,preset,target=None,bus=None):
    """Plan a complete chain before undo/project changes, including slot limits."""
    target=app.plugin_target() if target is None else target
    bus=app.plugin_bus() if bus is None else bus
    plugins=target.get('plugins',[])
    if not plugins or plugins[0] is not selected or selected.get('uri')!=URI:raise ValueError('Select the Synth instrument first.')
    added=effects(preset)
    if not added and not any(p.get(MARK) is True for p in plugins[1:]):return None
    kept=[(i,p) for i,p in enumerate(plugins[1:],1) if p.get(MARK) is not True]
    if 1+len(added)+len(kept)>16:raise ValueError('Not enough free slots for patch effects.')
    chain=[selected]+added+[p for _,p in kept];mapping={0:0}
    mapping.update({old:1+len(added)+n for n,(old,_) in enumerate(kept)})
    # Keep automation for the same owned processor; drop only removed FX lanes.
    for old,p in enumerate(plugins[1:],1):
        if p.get(MARK) is True:
            for new,q in enumerate(added,1):
                if p['uri']==q['uri']:mapping[old]=new
    return chain,mapping,target,bus

def commit(app,plan):
    chain,mapping,target,bus=plan
    app.plugin_reindex(bus,mapping)
    target['plugins']=chain
