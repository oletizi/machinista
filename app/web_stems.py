"""Bounded, cancelable local separation jobs; no live engine mutations."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave
from app.sound_library import worker_priority
from app.stem_models import paths,ready,MODEL_NAME

MAX_SOURCE=64*1024**2
RESERVE=256*1024**2


def service_memory_limit():
    if not sys.platform.startswith('linux'):return None
    try:
        group=next(line.split(':',2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
        location=Path('/sys/fs/cgroup')/group.lstrip('/')/'memory.max'
        if not location.exists():location=Path('/sys/fs/cgroup/memory.max')
        value=location.read_text().strip()
        return None if value=='max' else int(value)
    except (OSError,ValueError,StopIteration):return None


class Stems:
    def __init__(self,library):
        self.library=library;self.guard=threading.Lock();self.cancel=threading.Event()
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='stem-separation',initializer=worker_priority)
        self.future=None;self.last=dict(state='IDLE',progress=0,message='Choose a sample in Sample Library.')
    def status(self):
        with self.guard:
            if self.future is not None and self.future.done():
                try:self.last.update(self.future.result())
                except Exception as error:self.last.update(state='ERROR',message=str(error),progress=0)
                self.future=None
            limit=service_memory_limit();allowed=limit is None or limit>=1024*1024**2
            return dict(self.last,ready=ready(self.library.root),model=MODEL_NAME,busy=self.future is not None,can_separate=allowed,memory_limit=limit,blocked_reason='' if allowed else 'The WebUI service memory limit must be configured before separation can run.')
    def stopped(self):
        context=self.library.sounds.runtime()
        if not context.get('available'):raise ValueError('Controller engine unavailable.')
        if any(context.get(k) for k in ('playing','recording','capturing','busy')):raise ValueError('Stop playback, recording and other jobs first.')
    def submit(self,state,work):
        with self.guard:
            if self.future is not None:raise BlockingIOError('A stem operation is already running.')
            if not self.library.upload_lock.acquire(blocking=False):raise BlockingIOError('Finish the current upload or import first.')
            self.cancel.clear();self.last=dict(state=state,progress=0,message='Preparing…')
            def run():
                try:return work()
                finally:self.library.upload_lock.release()
            self.future=self.pool.submit(run)
        return {'ok':True}
    def abort(self):self.cancel.set();return {'ok':True}
    def progress(self,message):
        with self.guard:self.last.update(message=message)
    def check(self):
        if self.cancel.is_set():raise ValueError('Stem operation canceled.')
        self.stopped()
    def process(self,command,timeout):
        # A separate process group lets cancellation also stop pip children.
        with tempfile.TemporaryFile() as output:
            proc=subprocess.Popen(command,cwd=self.library.root,stdin=subprocess.DEVNULL,stdout=output,stderr=output,
                                  start_new_session=True,env=os.environ|{'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','HF_HUB_OFFLINE':'1'})
            try:
                if hasattr(os,'setpriority'):
                    try:os.setpriority(os.PRIO_PROCESS,proc.pid,19)
                    except OSError:pass
                started=time.monotonic();read_offset=0;pending=''
                if sys.platform.startswith('linux'):
                    try:Path(f'/proc/{proc.pid}/oom_score_adj').write_text('750')
                    except OSError:pass
                while proc.poll() is None:
                    self.check()
                    chunk=os.pread(output.fileno(),65536,read_offset)
                    if chunk:
                        read_offset+=len(chunk);pending+=chunk.decode('utf-8',errors='replace')
                        lines=pending.split('\n');pending=lines.pop()[-8192:]
                        for line in lines:
                            if line.startswith('{'):
                                try:notice=json.loads(line)
                                except ValueError:continue
                                if type(notice.get('progress')) is int and isinstance(notice.get('message'),str):
                                    with self.guard:self.last.update(progress=max(0,min(99,notice['progress'])),message=notice['message'][:200])
                    if sys.platform.startswith('linux') and 'install_stems.py' not in ' '.join(command):
                        try:
                            status=Path(f'/proc/{proc.pid}/status').read_text()
                            rss=next((int(l.split()[1])*1024 for l in status.splitlines() if l.startswith('VmRSS:')),0)
                            memory=Path('/proc/meminfo').read_text()
                            free=next(int(l.split()[1])*1024 for l in memory.splitlines() if l.startswith('MemAvailable:'))
                            if rss>768*1024**2 or free<512*1024**2:raise ValueError('Stem processing stopped before exhausting RAM.')
                        except FileNotFoundError:pass
                    if time.monotonic()-started>timeout:raise ValueError('Stem operation timed out.')
                    time.sleep(.1)
                self.check()
                if proc.returncode:
                    raise ValueError('Stem engine setup failed. Check internet, free space and Python venv support.' if 'install_stems.py' in ' '.join(command) else 'Stem processing failed. The source may be unsupported or memory insufficient.')
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    def install(self):
        self.stopped()
        if shutil.disk_usage(self.library.root).free<1536*1024**2:raise ValueError('Stem setup needs 1.5 GiB free storage.')
        return self.submit('INSTALLING',lambda:self._install())
    def _install(self):
        self.progress('Installing local engine and downloading verified model. Keep power and internet connected.')
        self.process([sys.executable,str(self.library.root/'tools/install_stems.py'),str(self.library.root)],1800)
        if not ready(self.library.root):raise ValueError('Stem setup did not finish.')
        return dict(state='DONE',message='Stem engine installed. Separation now works offline.',progress=100)
    def start(self,value):
        limit=service_memory_limit()
        if limit is not None and limit<1024*1024**2:raise ValueError('WebUI service memory limit is too low for stem separation.')
        if not ready(self.library.root):raise ValueError('Install the local stem engine first.')
        self.stopped()
        if Path('/proc/meminfo').exists():
            available=next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
            if available<1536*1024**2:raise ValueError('Stem separation needs at least 1.5 GiB free RAM. Unload instruments or use a Pi with more RAM.')
        if shutil.disk_usage(self.library.root).free<512*1024**2:raise ValueError('Stem separation needs 512 MiB free storage.')
        from app.web_server import filename
        name=filename(value.get('name',''))
        if Path(name).suffix.lower() not in ('.wav','.mp3'):raise ValueError('Choose a WAV or MP3 sample.')
        source=self.library.source(value.get('source','sd'))
        # Pin and open the source before leaving the request; never reopen a client path.
        with self.library.directory(source,value.get('path','')) as parent:fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        stream=os.fdopen(fd,'rb');info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_SOURCE:
            stream.close();raise ValueError('Choose a regular sample up to 64 MiB.')
        try:return self.submit('SEPARATING',lambda:self._separate(stream,name))
        except BaseException:stream.close();raise
    def _separate(self,stream,name):
        cache=self.library.root/'presets/.stem-work';cache.mkdir(parents=True,exist_ok=True)
        with stream,tempfile.TemporaryDirectory(prefix='stems-',dir=cache) as temp:
            job=Path(temp);source=job/('source'+Path(name).suffix.lower())
            with source.open('wb') as output:
                for _ in range(MAX_SOURCE//65536+1):
                    self.check();block=stream.read(65536)
                    if not block:break
                    if output.tell()+len(block)>MAX_SOURCE:raise ValueError('Source grew during reading.')
                    output.write(block)
            from app.export_mp3 import tools
            encoder,_=tools();raw=job/'input.f32'
            self.progress('Preparing audio. Maximum length: 60 seconds.')
            self.process([encoder,'-nostdin','-v','error','-xerror','-y','-threads','1','-filter_threads','1','-protocol_whitelist','file,pipe',
                          '-i',str(source),'-map','0:a:0','-vn','-t','61','-ar','44100','-ac','2','-f','f32le',str(raw)],120)
            if not 0<raw.stat().st_size<=44100*60*8:raise ValueError('Choose a sample or loop up to 60 seconds. Longer files are not trimmed automatically.')
            _,python,model,_=paths(self.library.root)
            self.progress('Separating vocals, drums, bass and other instruments. This can take several minutes on a Pi.')
            result=job/'result'
            self.process([str(python),'-m','app.stem_worker',str(model),str(raw),str(result)],3600)
            for stem in ('vocals','drums','bass','other'):
                with wave.open(str(result/(stem+'.wav')),'rb') as w:
                    if w.getnchannels()!=2 or w.getsampwidth()!=3 or w.getframerate()!=44100 or w.getnframes()*8!=raw.stat().st_size:raise ValueError('Incomplete stem output.')
            self.check()
            # Publish through pinned, no-symlink library descriptors, without replacing content.
            sd=self.library.source('sd')
            if sd.read_only:raise ValueError('SD library is read-only.')
            for parent,child in (('','Library'),('Library','Stems')):
                with self.library.directory(sd,parent) as directory:
                    try:os.mkdir(child,dir_fd=directory)
                    except FileExistsError:pass
            title=Path(name).stem[:80]+'-'+uuid.uuid4().hex[:8]
            with self.library.directory(sd,'Library/Stems') as directory:
                temporary='.'+uuid.uuid4().hex;os.mkdir(temporary,dir_fd=directory)
                target=os.open(temporary,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
                try:
                    for file in result.iterdir():
                        out=os.open(file.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=target)
                        with os.fdopen(out,'wb') as output,file.open('rb') as input:
                            shutil.copyfileobj(input,output);output.flush();os.fsync(output.fileno())
                    self.check();os.rename(temporary,title,src_dir_fd=directory,dst_dir_fd=directory);os.fsync(directory)
                except BaseException:
                    for entry in os.listdir(target):os.unlink(entry,dir_fd=target)
                    os.rmdir(temporary,dir_fd=directory);raise
                finally:os.close(target)
            return dict(state='DONE',progress=100,message='Four stems saved in Library / Stems. Preview or load them as normal samples.',folder='Library/Stems/'+title,source='sd')
