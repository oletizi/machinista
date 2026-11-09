"""Install and user-data roots.

MACHINISTA_DATA moves user data (samples, projects, config, cache and saved
presets) out of the checkout. Unset, both roots are the checkout, which is the
Raspberry Pi image layout, and nothing is redirected.

Code passes one `root` around. Only when that root is the configured, separate
data root do code-side paths (native binaries, tools, web assets, captures) and
read-only factory presets come from the checkout instead. Any other root, such
as a test fixture, keeps its existing behavior.
"""
import os
from functools import lru_cache
from pathlib import Path

INSTALL = Path(__file__).resolve().parents[1]


def _configured():
    value = os.environ.get('MACHINISTA_DATA', '').strip()
    return Path(value).expanduser().resolve() if value else INSTALL


DATA = _configured()


@lru_cache(maxsize=64)
def _resolved(text):
    return Path(text).resolve()


def separate(root):
    """True when root is the configured data root and differs from the checkout."""
    return DATA != INSTALL and _resolved(str(root)) == DATA


def code(root):
    """Directory holding app code, native builds, tools, web assets and captures."""
    return INSTALL if separate(root) else Path(root)


def factory(root, relative):
    """Read-only factory folder layered under root/relative, or None."""
    return INSTALL / relative if separate(root) else None
