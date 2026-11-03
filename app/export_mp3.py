"""Cancelable, isolated MP3 encoding of an already rendered stereo WAV."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

BITRATES=(128,192,256,320)


def tools():
    encoder=shutil.which('ffmpeg');probe=shutil.which('ffprobe')
    if not encoder or not probe:raise ValueError('MP3 EXPORT NEEDS FFMPEG / FFPROBE')
    return encoder,probe


def bitrate(value):
    if type(value) is not int or value not in BITRATES:raise ValueError('INVALID MP3 BITRATE')
    return value


def encode(source,destination,rate,frames,quality=320,cancel=None,verify_location=lambda:None):
    encoder,probe=tools();quality=bitrate(quality)
    command=[encoder,'-nostdin','-hide_banner','-loglevel','error','-xerror','-y',
             '-threads','1','-filter_threads','1','-protocol_whitelist','file,pipe',
             '-i',str(source),'-map','0:a:0','-map_metadata','-1','-vn','-sn','-dn',
             '-c:a','libmp3lame','-threads','1','-b:a',str(quality)+'k','-ar',str(rate),'-ac','2',
             '-write_xing','1','-f','mp3',str(destination)]
    try:
        with tempfile.TemporaryFile() as errors:
            process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors)
            try:
                if hasattr(os,'setpriority'):
                    try:os.setpriority(os.PRIO_PROCESS,process.pid,19)
                    except OSError:pass
                start=time.monotonic()
                while True:
                    if cancel is not None and cancel.is_set():raise ValueError('EXPORT CANCELED')
                    verify_location()
                    if process.poll() is not None:break
                    if time.monotonic()-start>max(120,frames/rate*2):raise ValueError('MP3 ENCODING TIMED OUT')
                    time.sleep(.025)
                if process.returncode:raise ValueError('MP3 ENCODING FAILED')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
        if cancel is not None and cancel.is_set():raise ValueError('EXPORT CANCELED')
        verify_location()
        result=subprocess.run([probe,'-v','error','-select_streams','a:0','-show_entries',
                               'stream=codec_name,sample_rate,channels,bit_rate:format=duration',
                               '-of','json',str(destination)],capture_output=True,text=True,timeout=20,check=True)
        details=json.loads(result.stdout);stream=details['streams'][0]
        if (stream['codec_name']!='mp3' or int(stream['sample_rate'])!=rate or stream['channels']!=2
            or abs(float(details['format']['duration'])-frames/rate)>.15
            or abs(int(stream['bit_rate'])-quality*1000)>5000
            or Path(destination).stat().st_size<100):raise ValueError('INVALID MP3 EXPORT')
        with Path(destination).open('rb') as output:os.fsync(output.fileno())
    except BaseException:
        Path(destination).unlink(missing_ok=True)
        raise
