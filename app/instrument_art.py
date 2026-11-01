"""Static display-only illustrations. Decode each native-size asset once."""
from functools import lru_cache
from pathlib import Path

EFFECTS=('eq','compressor','limiter','transient','reverb','delay','chorus','flanger','phaser','tremolo','vibrato','autopan','ducktor')
EFFECT_ART={'urn:machinista:effect:'+name:'fx-'+name for name in EFFECTS}
KINDS=frozenset(('machinista-synth','generic-synth','generic-filter',*EFFECT_ART.values()))

def effect_art(uri):
    return EFFECT_ART.get(uri,'generic-filter')

def image(kind):
    if kind not in KINDS:return None
    return _image(kind)

@lru_cache(maxsize=len(KINDS))
def _image(kind):
    from PIL import Image
    try:
        with Image.open(Path(__file__).resolve().parents[1]/'assets/instrument-art'/(kind+'.png')) as source:
            if source.size!=(448,120):return None
            return source.convert('RGBA')
    except OSError:return None
