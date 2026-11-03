import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
from app.web_server import Library
from app.stem_models import paths,ready


class StemJobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'samples/Library').mkdir(parents=True)
        self.library=Library(self.root,lambda:[]);self.stems=self.library.stems
        self.addCleanup(self.stems.pool.shutdown,wait=True)
        self.encoder=patch('app.export_mp3.tools',return_value=('ffmpeg','ffprobe'));self.encoder.start();self.addCleanup(self.encoder.stop)
        self.capacity=patch('app.web_stems.service_memory_limit',return_value=None);self.capacity.start();self.addCleanup(self.capacity.stop)
        self.context={'available':True,'playing':False,'recording':False,'capturing':False,'busy':False}
        self.library.sounds.runtime=lambda:self.context.copy()
        self.source=self.root/'samples/Library/Example.wav'
        with wave.open(str(self.source),'wb') as f:f.setparams((2,2,44100,100,'NONE','NONE'));f.writeframes(bytes(400))
        self.value=dict(source='sd',path='Library',name='Example.wav')
    def complete(self):
        if self.stems.future:self.stems.future.result(timeout=5)
        return self.stems.status()
    def fake_process(self,command,timeout):
        if '-m' in command:
            dest=Path(command[-1]);dest.mkdir()
            for name in ('vocals','drums','bass','other'):
                with wave.open(str(dest/(name+'.wav')),'wb') as f:f.setparams((2,3,44100,100,'NONE','NONE'));f.writeframes(bytes(600))
            (dest/'Separation.json').write_text('{}')
        else:Path(command[-1]).write_bytes(bytes(800))
    def start(self):
        with patch('app.web_stems.ready',return_value=True):return self.stems.start(self.value)
    def test_stopped_guard_covers_play_record_capture_and_busy(self):
        for field in ('playing','recording','capturing','busy'):
            with self.subTest(field=field):
                self.context[field]=True
                with self.assertRaisesRegex(ValueError,'Stop'):self.start()
                self.context[field]=False
        self.context['available']=False
        with self.assertRaisesRegex(ValueError,'unavailable'):self.start()
    def test_symlinks_and_traversal_cannot_be_selected(self):
        link=self.source.with_name('Link.wav');link.symlink_to(self.source)
        for value in [dict(self.value,name='Link.wav'),dict(self.value,path='../'),dict(self.value,name='../Example.wav')]:
            with patch('app.web_stems.ready',return_value=True),self.assertRaises((ValueError,OSError)):self.stems.start(value)
        self.assertFalse(self.library.upload_lock.locked())
    def test_success_keeps_original_and_publishes_complete_unique_folder(self):
        original=self.source.read_bytes()
        with patch.object(self.stems,'process',side_effect=self.fake_process):
            self.start();status=self.complete()
        self.assertEqual(status['state'],'DONE');self.assertEqual(self.source.read_bytes(),original)
        target=self.root/'samples'/status['folder'];self.assertEqual(len(list(target.glob('*.wav'))),4)
        self.assertFalse(self.library.upload_lock.locked());self.assertFalse(list((self.root/'cache').glob('stems-*')))
    def test_too_long_fails_without_truncating_or_publishing(self):
        def decode(command,timeout):
            with Path(command[-1]).open('wb') as f:f.truncate(44100*61*8)
        with patch.object(self.stems,'process',side_effect=decode):
            self.start()
            with self.assertRaisesRegex(ValueError,'60 seconds'):self.complete()
        self.stems.status();self.assertFalse((self.root/'samples/Library/Stems').exists())
        self.assertFalse(self.library.upload_lock.locked())
    def test_output_symlink_cannot_escape_library(self):
        outside=self.root/'outside';outside.mkdir();(self.root/'samples/Library/Stems').symlink_to(outside,target_is_directory=True)
        with patch.object(self.stems,'process',side_effect=self.fake_process):
            self.start()
            with self.assertRaises(OSError):self.complete()
        self.stems.status();self.assertEqual(list(outside.iterdir()),[])
    def test_cancel_and_resume_playback_abort_before_publication(self):
        def decode(command,timeout):
            self.fake_process(command,timeout);self.context['playing']=True
        with patch.object(self.stems,'process',side_effect=decode):
            self.start()
            with self.assertRaisesRegex(ValueError,'Stop'):self.complete()
        self.stems.status();self.assertFalse((self.root/'samples/Library/Stems').exists())
        self.context['playing']=False;self.stems.cancel.set()
        with self.assertRaisesRegex(ValueError,'canceled'):self.stems.check()
    def test_missing_engine_and_duplicate_job_are_clear(self):
        with patch('app.web_stems.ready',return_value=False),self.assertRaisesRegex(ValueError,'Install'):self.stems.start(self.value)
        with self.library.upload_lock:
            with self.assertRaises(BlockingIOError):self.start()

class StemHttpTests(unittest.TestCase):
    def setUp(self):
        from tests.test_web_server import WebHttpTests
        WebHttpTests.setUp(self)
    def stop(self):
        from tests.test_web_server import WebHttpTests
        WebHttpTests.stop(self)
    def request(self,*a,**kw):
        from tests.test_web_server import WebHttpTests
        return WebHttpTests.request(self,*a,**kw)
    def test_routes_require_token_and_delegate_only_fixed_operations(self):
        body=json.dumps({'source':'sd','path':'Library','name':'Test.wav'})
        with patch.object(self.library.stems,'start',return_value={'ok':True}) as start:
            self.assertEqual(self.request('POST','/api/stems/start',body)[0],403);start.assert_not_called()
            self.assertEqual(self.request('POST','/api/stems/start',body,{'X-Machinista-Token':self.library.token})[0],200)
            start.assert_called_once_with(json.loads(body))
        self.assertEqual(self.request('GET','/api/stems/start')[0],404)
        self.assertEqual(self.request('GET','/api/stems')[0],200)

class SpectralRoundtripTests(unittest.TestCase):
    def test_first_last_samples_and_block_boundaries_reconstruct(self):
        try:import numpy as np
        except ImportError:self.skipTest('Optional NumPy not installed')
        from app.stem_worker import spectrum,reconstruct
        for length in (1,4096,44100,44100*13):
            with self.subTest(length=length):
                audio=np.random.default_rng(123).uniform(-.8,.8,(2,length)).astype(np.float32)
                restored=reconstruct(spectrum(audio),length)
                self.assertEqual(restored.shape,audio.shape)
                self.assertLess(float(np.max(np.abs(restored-audio))),5e-7)

class ServiceBudgetTests(unittest.TestCase):
    setUp=StemJobsTests.setUp
    start=StemJobsTests.start
    def test_low_service_ceiling_blocks_before_any_worker_starts(self):
        with patch('app.web_stems.service_memory_limit',return_value=192*1024**2):
            with self.assertRaisesRegex(ValueError,'service memory limit'):self.start()
            self.assertFalse(self.stems.status()['can_separate'])
            self.assertIsNone(self.stems.future)
