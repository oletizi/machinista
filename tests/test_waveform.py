import array
from pathlib import Path
import tempfile
import time
import unittest
import wave
from unittest.mock import patch
from app.waveform import read_envelope, Waveforms


class WaveformTests(unittest.TestCase):
    def test_mikro_zoom_reuses_pcm_index_and_cached_views_without_loading_blanks(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'zoom.wav'
            with wave.open(str(path),'wb') as wav:
                wav.setparams((2,2,48000,0,'NONE','not compressed'))
                wav.writeframes(array.array('h',[-32768,32767]*240000).tobytes())
            reader=Waveforms()
            try:
                with patch('app.waveform_index.wave.open',wraps=wave.open) as opened:
                    result=None;deadline=time.monotonic()+3
                    while result is None and time.monotonic()<deadline:
                        result=reader.envelope(path);time.sleep(.001)
                    self.assertIsNotNone(result);self.assertEqual(opened.call_count,1)
                    # No worker round-trip or disk read for any new zoom/scroll window.
                    with patch('app.waveform_index.WaveformIndex',side_effect=AssertionError('PCM reread')):
                        for start,end in ((0,120000),(123,60123),(4000,16000),(5990,6110),(0,240000)):
                            result=reader.envelope(path,start,end)
                            self.assertIsNotNone(result);self.assertEqual((result.start,result.end),(start,end))
                        self.assertIs(reader.envelope(path,0,240000),result)
                    self.assertEqual(opened.call_count,1)
            finally:reader.close()
    def test_pcm_peaks_preserve_transients_and_silence(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'fixture.wav'
            samples = array.array('h', [0]*240)
            samples[20], samples[21] = -32768, 32767
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
                wav.writeframes(samples.tobytes())
            envelope = read_envelope(path)
            self.assertEqual(envelope.frames, 240)
            self.assertEqual(envelope.peaks[10], (-1.0, 32767/32768))
            self.assertEqual(envelope.peaks[11], (0.0, 0.0))

    def test_short_unsigned_pcm_has_correct_zero_baseline(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'short.wav'
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(1); wav.setframerate(8000)
                wav.writeframes(bytes([128, 255]))
            envelope = read_envelope(path, 2)
            self.assertEqual(envelope.peaks, ((0.0, 0.0), (127/128, 127/128)))

    def test_async_envelope_is_ready_and_displayed_with_trim_markers(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'fixture.wav'
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
                wav.writeframes(array.array('h', [-32768, 32767]*120).tobytes())
            reader = Waveforms()
            try:
                envelope = None
                deadline = time.monotonic()+2
                while envelope is None and time.monotonic() < deadline:
                    envelope = reader.envelope(path)
                    time.sleep(0.005)
                self.assertIsNotNone(envelope)
                import sys
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'tools'))
                from machinista import display_pixels
                from app.model import Application
                app = Application(root)
                app.button('SAMPLING', True)
                app.page = 'SAMPLE EDIT'
                app.track().update(sample=str(path), start=0, end=240)
                pixels = display_pixels(app, envelope)
                self.assertGreater(sum(pixels[25*128:45*128]), 1800)
                self.assertEqual(pixels[24*128+4], 1)
                self.assertEqual(pixels[24*128+123], 1)
            finally:
                reader.close()


if __name__ == '__main__':
    unittest.main()
