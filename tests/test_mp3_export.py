import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave
from app.export_formats import export_format
from app.export_mp3 import encode,BITRATES
from tests import test_export_audio as export_tests


class MenuTests(unittest.TestCase):
    setUp=export_tests.ExportTests.setUp
    def test_mp3_bitrate_and_pcm_depth_are_independent(self):
        a=self.a;a.open_export();a.export_field=4;a.rotate(2)
        self.assertEqual(a.export_value(),'MP3');self.assertEqual(a.export_fields()[5],'BITRATE')
        a.export_field=5;a.rotate(-2);self.assertEqual(a.export_value(),'192 KBPS')
        a.export_field=4;a.rotate(-2);self.assertEqual(a.export_fields()[5],'DEPTH');self.assertEqual(a.export_bits,16)
        a.export_field=4;a.rotate(2);a.export_request();req=a.actions[-1][1]
        self.assertEqual((req['format'],req['bitrate']),('MP3',192))
        for invalid in (True,123,'320'):
            with self.assertRaisesRegex(ValueError,'BITRATE'):export_format(dict(format='MP3',bitrate=invalid))
    def test_encoder_absence_is_clear(self):
        with patch('app.export_mp3.shutil.which',return_value=None):
            from app.export_mp3 import tools
            with self.assertRaisesRegex(ValueError,'FFMPEG'):tools()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'ffmpeg/ffprobe required')
class CodecTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/'source.wav';self.frames=48000
        with wave.open(str(self.source),'wb') as w:
            w.setparams((2,2,48000,self.frames,'NONE','not compressed'))
            w.writeframes(array.array('h',[int(8000*math.sin(i*2*math.pi*440/48000)) for i in range(self.frames) for _ in range(2)]).tobytes())
    def test_real_encoder_bitrates_metadata_and_decoded_signal(self):
        for quality in BITRATES:
            with self.subTest(quality=quality):
                target=self.root/f'{quality}.mp3';encode(self.source,target,48000,self.frames,quality)
                output=subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','s16le','-'],capture_output=True,check=True).stdout
                decoded=array.array('h');decoded.frombytes(output)
                self.assertLess(abs(len(decoded)//2-self.frames),1153)
                self.assertGreater(max(decoded),6000);self.assertLess(max(decoded),10000)
    def test_cancel_and_device_removal_leave_no_partial_file(self):
        cancel=threading.Event();cancel.set();target=self.root/'cancel.mp3'
        with self.assertRaisesRegex(ValueError,'CANCELED'):encode(self.source,target,48000,self.frames,cancel=cancel)
        self.assertFalse(target.exists())
        def removed():raise ValueError('USB REMOVED')
        with self.assertRaisesRegex(ValueError,'USB REMOVED'):encode(self.source,target,48000,self.frames,verify_location=removed)
        self.assertFalse(target.exists());self.assertTrue(self.source.exists())


@unittest.skipUnless((export_tests.ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists() and shutil.which('ffmpeg') and shutil.which('ffprobe'),'Linux native engine and ffmpeg required')
class NativeMP3Tests(unittest.TestCase):
    setUp=export_tests.NativeExportTests.setUp
    request=export_tests.ExportTests.request
    def test_native_render_publishes_only_complete_mp3(self):
        from app.export_audio import render_export
        target=render_export(self.request(format='MP3',bitrate=256),self.root)
        self.assertTrue((target/'Mix.mp3').is_file());self.assertFalse((target/'Mix.wav').exists())
        info=json.loads((target/'Export.json').read_text())
        self.assertEqual((info['container'],info['encoding'],info['bitrate'],info['bits']),('MP3','MP3',256,None))
