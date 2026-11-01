"""Cached native-size MK3 navigation artwork; no file reads after first use."""
from functools import lru_cache
from pathlib import Path

NAMES=('pin','ideas','song','mixer','browse','events','live-fx','back')
SIZE=76

@lru_cache(maxsize=8)
def _source(index):
    from PIL import Image
    try:
        with Image.open(Path(__file__).resolve().parents[1]/'assets/navigation-art'/(NAMES[index]+'.png')) as source:
            if source.size!=(SIZE,SIZE):return None
            return source.convert('RGBA')
    except (OSError,IndexError):return None

@lru_cache(maxsize=16)
def image(index,selected=False):
    source=_source(index)
    if source is None:return None
    if selected:return source
    tile=source.copy()
    tile.putalpha(tile.getchannel('A').point(lambda v:v*205//255))
    return tile
