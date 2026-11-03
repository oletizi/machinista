"""Original spectral bank remains portable and complete without external plugins."""
import json,math,struct,unittest
from pathlib import Path
from app.plugin_profiles import profile,validate_bank,patch_identity,banks
from app.synth_library import URI,preset_waves
from app.synth_patch_fx import effects
ROOT=Path(__file__).resolve().parents[1]

class SpectralMachinesTests(unittest.TestCase):
 def test_24_distinct_patches_and_eight_complete_prepared_tables(self):
  p=ROOT/'presets/plugin-banks/machinista-synth/spectral-machines.json'
  bank=validate_bank(json.loads(p.read_text()),profile(URI));self.assertEqual(len(bank['patches']),24)
  self.assertEqual(len({patch_identity(v) for v in bank['patches']}),24);waves={}
  for patch in bank['patches']:
   waves.update({row['id']:row for row in preset_waves(ROOT,patch).values()})
   self.assertLessEqual(len(effects(patch)),2)
   self.assertFalse(any(w in patch['name'].lower() for w in ('kick','snare','drum')))
  self.assertEqual(len(waves),8)
  for identity,row in waves.items():
   self.assertEqual((row['frames'],row['cycle']),(32,1024))
   data=(ROOT/'presets/Oscillators/.assets'/(identity+'.mwave')).read_bytes()
   self.assertEqual(data[:8],b'MWAVET02');self.assertEqual(len(data),16+32*1024*10*4)
   frames=[]
   for f in (0,15,31):
    values=struct.unpack_from('<1024f',data,16+f*1024*10*4);frames.append(values)
    self.assertTrue(all(math.isfinite(x) for x in values));self.assertLessEqual(max(map(abs,values)),.721)
    self.assertLess(abs(sum(values)/1024),.00001)
   self.assertGreater(max(sum(abs(a-b) for a,b in zip(frames[0],other)) for other in frames[1:]),1)
 def test_legacy_factory_stays_consolidated_and_old_controls_stay_intact(self):
  available=banks(ROOT,profile(URI));self.assertNotIn('factory',[b['id'] for b in available])
  self.assertEqual(available[-1]['id'],'init');self.assertEqual(sum(len(b['patches']) for b in available),289)
  factory=json.loads((ROOT/'presets/plugin-banks/machinista-synth/factory.json').read_text())
  self.assertEqual(len(factory['patches']),264)
  self.assertEqual(sum(bool(p.get('effects')) for p in factory['patches']),16)
