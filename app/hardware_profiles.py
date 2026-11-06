"""Runtime capabilities shared by controller UI, WebUI and the native engine.

A root-owned image marker selects the hardware target. User projects/settings
are never rewritten when a capability is unavailable on a smaller machine.
"""
import os
from pathlib import Path

PROFILES={
 'standard':dict(id='standard',name='Standard',architecture='arm64',sampler_voices=64,sample_memory_mib=512,audio_buffer=0,lv2=True,synth=True,stems=True),
 'pi3b-sampler':dict(id='pi3b-sampler',name='Pi 3B Sampler (experimental)',architecture='arm64',sampler_voices=16,sample_memory_mib=192,audio_buffer=512,lv2=False,synth=False,stems=False),
}

def current(marker=Path('/etc/machinista/hardware-profile')):
 identity=os.environ.get('MACHINISTA_HARDWARE_PROFILE')
 if identity is None:
  try:identity=Path(marker).read_text().strip()
  except FileNotFoundError:identity='standard'
 if identity not in PROFILES:raise ValueError('Unknown Machinista hardware profile: '+str(identity))
 return dict(PROFILES[identity])

def environment():
 result=os.environ.copy();result['MACHINISTA_HARDWARE_PROFILE']=current()['id'];return result
