"""Transactional bank/pad editing and bounded sample-only expansion transfers."""
from contextlib import contextmanager
from pathlib import Path
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
import threading
from functools import wraps
import uuid
import zipfile
from app.sample_set_import import AUDIO,METADATA,MAX_BANKS,convert,plan,title
from app.web_projects import parts,MAX_PACKAGE,RESERVE

MAX_FILES=8192


def one_import(function):
    @wraps(function)
    def run(self,*args,**kwargs):
        if not self.import_lock.acquire(blocking=False):raise BlockingIOError('An expansion import is already running.')
        try:return function(self,*args,**kwargs)
        finally:self.import_lock.release()
    return run


class SetEditor:
    def __init__(self,sets):
        self.sets=sets;self.library=sets.library;self.folder=sets.folder;self.staging=self.folder/'.uploads';self.import_lock=threading.RLock()

    def metadata(self,base):
        path=base/'Set.json'
        if path.is_symlink() or path.stat().st_size>256*1024:raise ValueError('Invalid sample-set manifest.')
        value=json.loads(path.read_text())
        if value.get('format')!='Machinista-sample-set' or value.get('version')!=1 or not isinstance(value.get('banks'),list) or not 1<=len(value['banks'])<=MAX_BANKS:raise ValueError('Invalid sample set.')
        for bank in value['banks']:
            if not isinstance(bank,dict) or not re.fullmatch(r'bank-[0-9]{3}',bank.get('id','')):raise ValueError('Invalid bank.')
        if len({b['id'] for b in value['banks']})!=len(value['banks']):raise ValueError('Duplicate bank ID.')
        return value

    def banks(self,identity):
        base=self.sets.bundle(identity)
        if (base/'Set.json').exists():
            meta=self.metadata(base)
            return meta,[(bank,base/bank['id']) for bank in meta['banks']]
        data=self.sets.document(base)
        return dict(name=data.get('name',identity),notes=[],banks=[dict(id='legacy',name='Bank A')]),[(dict(id='legacy',name='Bank A'),base)]

    def revision(self,identity):
        base=self.sets.bundle(identity);meta,rows=self.banks(identity);digest=hashlib.sha256()
        digest.update(json.dumps(meta,sort_keys=True).encode())
        for _,path in rows:digest.update((path/'Preset.json').read_bytes())
        return digest.hexdigest()

    def item(self,identity):
        meta,rows=self.banks(identity);revision=self.revision(identity);banks=[]
        for info,base in rows:
            if base.is_symlink():raise ValueError('Invalid bank directory.')
            data=self.sets.document(base);pads=[]
            for index,pad in enumerate(data['project']['groups'][0]['pads']):
                ref=pad.get('sample') or next((z.get('sample') for z in pad.get('zones',[]) if z.get('sample')),None)
                if not ref and not pad.get('plugins'):pads.append(None);continue
                absolute=Path(ref) if ref else None
                if absolute is not None and not absolute.is_absolute():absolute=base/absolute
                asset=dict(set=identity,path=str(absolute.relative_to(self.sets.bundle(identity)))) if absolute else None
                pads.append(dict(name=pad.get('name') or (absolute.stem if absolute else 'Instrument'),asset=asset,
                                 layers=len(pad.get('zones',[])) or (1 if ref else 0),
                                 origin=dict(set=identity,bank=info['id'],pad=index,revision=revision)))
            banks.append(dict(name=info['name'],pads=pads,origin=dict(set=identity,bank=info['id'],revision=revision)))
        return dict(id=identity,name=title(meta['name']),revision=revision,banks=banks,notes=meta.get('notes',[]))

    def listing(self,identity):
        item=self.item(identity)
        return dict(id=identity,name=item['name'],banks=len(item['banks']),pads=sum(p is not None for b in item['banks'] for p in b['pads']),notes=item['notes'])

    def stage(self,identity):
        if not isinstance(identity,str) or not re.fullmatch(r'[a-f0-9]{32}',identity):raise ValueError('Invalid upload session.')
        path=self.staging/identity
        if path.is_symlink() or not path.is_dir():raise ValueError('Upload session expired. Select the files again.')
        return path

    def start(self):
        self.staging.mkdir(exist_ok=True)
        # Only remove abandoned temporary transfers, never saved banks.
        for path in self.staging.iterdir():
            if path.is_dir() and not path.is_symlink() and time.time()-path.stat().st_mtime>24*3600:shutil.rmtree(path)
        identity=uuid.uuid4().hex;(self.staging/identity).mkdir()
        return dict(id=identity)

    def upload_file(self,identity,name,stream,length):
        components=parts(name)
        if any(p.startswith('.') or p=='__MACOSX' for p in components):raise ValueError('Hidden files are not imported.')
        suffix=Path(name).suffix.lower()
        if suffix not in AUDIO|METADATA:raise ValueError('Use an installed expansion folder or audio files, not an installer.')
        if not 0<length<=MAX_PACKAGE:raise ValueError('Maximum 1 GiB per transfer.')
        if not self.library.upload_lock.acquire(False):raise BlockingIOError('Another transfer is in progress.')
        try:
            base=self.stage(identity);files=[p for p in base.rglob('*') if p.is_file()]
            if len(files)>=MAX_FILES or sum(p.stat().st_size for p in files)+length>MAX_PACKAGE:raise ValueError('Folder exceeds 1 GiB or 8,192 files.')
            if shutil.disk_usage(base).free<length+RESERVE:raise ValueError('Not enough free storage.')
            target=base.joinpath(*components)
            if any(str(p.relative_to(base)).casefold()==str(target.relative_to(base)).casefold() for p in files):raise ValueError('Duplicate upload path.')
            target.parent.mkdir(parents=True,exist_ok=True)
            try:
                with target.open('xb') as out:
                    remaining=length
                    while remaining:
                        block=stream.read(min(65536,remaining))
                        if not block:raise ValueError('Incomplete sample upload.')
                        out.write(block);remaining-=len(block)
                os.utime(base,None)
            except BaseException:target.unlink(missing_ok=True);raise
            return dict(ok=True,asset=dict(upload=identity,path='/'.join(components)),name=target.name)
        finally:self.library.upload_lock.release()

    @contextmanager
    def asset(self,ref):
        if not isinstance(ref,dict):raise ValueError('Invalid pad sample.')
        if 'set' in ref:
            base=self.sets.bundle(ref['set']);relative=parts(ref.get('path',''));path=base.joinpath(*relative)
        elif 'upload' in ref:
            base=self.stage(ref['upload']);relative=parts(ref.get('path',''));path=base.joinpath(*relative)
        elif 'source' in ref:
            from app.web_server import filename
            source=self.library.source(ref['source']);name=filename(ref.get('name',''))
            if Path(name).suffix.lower() not in AUDIO:raise ValueError('Audio samples only.')
            with self.library.directory(source,ref.get('path','')) as parent:fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
            with os.fdopen(fd,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Not a sample file.')
                yield stream
            return
        else:
            with self.library.sounds.asset(ref) as stream:yield stream
            return
        if path.suffix.lower() not in AUDIO:raise ValueError('Audio samples only.')
        with self.library.projects.opened(path,[base]) as stream:yield stream

    def original(self,origin):
        if not isinstance(origin,dict):raise ValueError('Invalid bank reference.')
        identity=origin.get('set')
        if origin.get('revision')!=self.revision(identity):raise ValueError('Sample set changed. Reload before saving.')
        _,rows=self.banks(identity)
        base=next((base for info,base in rows if info['id']==origin.get('bank')),None)
        if base is None:raise ValueError('Bank unavailable.')
        data=self.sets.document(base)
        from app.assets import resolve_assets
        return resolve_assets(copy.deepcopy(data['project']),base)

    def save(self,value):
        if not isinstance(value,dict):raise ValueError('Invalid sample set.')
        rows=value.get('banks');name=title(value.get('name',''))
        if not str(value.get('name','')).strip():raise ValueError('Enter a sample-set name.')
        if not isinstance(rows,list) or not 1<=len(rows)<=MAX_BANKS:raise ValueError('Use 1–128 banks.')
        if not self.library.upload_lock.acquire(False):raise BlockingIOError('Another transfer is in progress.')
        try:
            identity=value.get('id');old=self.sets.bundle(identity) if identity else None
            if old is not None and value.get('revision')!=self.revision(identity):raise ValueError('Sample set changed. Reload before saving.')
            if shutil.disk_usage(self.folder).free<RESERVE:raise ValueError('Not enough free storage.')
            with tempfile.TemporaryDirectory(prefix='.edit-',dir=self.folder) as tmp:
                base=Path(tmp)/'set';base.mkdir();banks=[];size=0
                from app.model import new_project,validate_project
                from app.assets import collect_project
                for index,row in enumerate(rows):
                    if not isinstance(row,dict) or not isinstance(row.get('pads'),list) or len(row['pads'])!=16:raise ValueError('Each bank must contain 16 pads.')
                    project=self.original(row['origin']) if row.get('origin') else validate_project(new_project())
                    blank=validate_project(new_project());group=project['groups'][0]
                    for slot,pad in enumerate(row['pads']):
                        if pad is None:group['pads'][slot]=copy.deepcopy(blank['groups'][0]['pads'][slot]);continue
                        if not isinstance(pad,dict):raise ValueError('Invalid pad.')
                        if pad.get('origin'):
                            origin=pad['origin'];position=origin.get('pad')
                            if type(position) is not int or not 0<=position<16:raise ValueError('Invalid source pad.')
                            track=self.original(origin)['groups'][0]['pads'][position]
                        else:
                            track=copy.deepcopy(blank['groups'][0]['pads'][slot]);ref=pad.get('asset')
                            extension=Path(ref.get('name') or ref.get('path','')).suffix.lower() if isinstance(ref,dict) else ''
                            if extension not in AUDIO:raise ValueError('Choose an audio sample for this pad.')
                            # Work on private copies; source libraries are never rewritten.
                            source=Path(tmp)/('source-'+uuid.uuid4().hex+extension);dest=Path(tmp)/('pcm-'+uuid.uuid4().hex+'.wav')
                            with self.asset(ref) as stream,source.open('wb') as out:shutil.copyfileobj(stream,out,65536)
                            info=convert(source,dest);size+=dest.stat().st_size
                            if size>MAX_PACKAGE:raise ValueError('Sample set exceeds 1 GiB decoded audio.')
                            track.update(sample=str(dest),start=0,end=info['frames'],zones=[])
                        track['name']=title(pad.get('name','Sample'))[:32];group['pads'][slot]=track
                    # Sample sets never overwrite pattern/event content in a Group.
                    from app.presets import PATTERN_KEYS
                    for key in PATTERN_KEYS:
                        if key in blank['groups'][0]:group[key]=copy.deepcopy(blank['groups'][0][key])
                        else:group.pop(key,None)
                    group['name']=re.sub(r'[^A-Za-z0-9 _-]','',title(row.get('name','Bank')))[:32] or 'Bank'
                    bank_id=f'bank-{index+1:03}';bank=base/bank_id
                    validate_project(project);collect_project(project,bank)
                    doc=json.loads((bank/'Project.json').read_text());(bank/'Project.json').unlink()
                    (bank/'Preset.json').write_text(json.dumps(dict(format='Machinista-preset',version=1,kind='GROUP',name=group['name'],project=doc)))
                    banks.append(dict(id=bank_id,name=title(row.get('name','Bank '+str(index+1)))))
                    if sum(p.stat().st_size for p in base.rglob('*') if p.is_file())>MAX_PACKAGE:raise ValueError('Sample set exceeds 1 GiB.')
                notes=value.get('notes',[])
                notes=[title(n) for n in notes[:64]] if isinstance(notes,list) else []
                (base/'Set.json').write_text(json.dumps(dict(format='Machinista-sample-set',version=1,name=name,banks=banks,notes=notes),ensure_ascii=False))
                # A loaded/saved project may still reference an older sample by
                # its collected filename. Preserve those files at the same path.
                if old is not None:
                    for previous in old.rglob('*'):
                        if previous.is_symlink():raise ValueError('Set contains a symbolic link.')
                        if previous.is_file() and previous.suffix.lower() in {'.wav','.ttl'}:
                            destination=base/previous.relative_to(old)
                            if not destination.exists():
                                destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous,destination)
                if sum(p.stat().st_size for p in base.rglob('*') if p.is_file())>MAX_PACKAGE:raise ValueError('Sample set including preserved assets exceeds 1 GiB. Use Save copy.')
                identity=identity or 'set-'+uuid.uuid4().hex
                if old is None and (self.folder/identity).exists():raise FileExistsError('Sample set already exists.')
                backup=self.folder/('.replaced-'+uuid.uuid4().hex)
                if old is not None:old.rename(backup)
                try:base.rename(self.folder/identity)
                except BaseException:
                    if backup.exists():backup.rename(old)
                    raise
                if backup.exists():
                    # Keep old assets for projects that still reference the previous preset.
                    self._trash_folder().mkdir(exist_ok=True)
                    backup.rename(self._trash_folder()/uuid.uuid4().hex)
            return dict(ok=True,id=identity,name=name)
        finally:self.library.upload_lock.release()

    def _trash_folder(self):return self.folder/'.trash'

    def delete(self,value):
        if not isinstance(value,dict) or value.get('confirmed') is not True:raise ValueError('Confirm deletion first.')
        if not self.library.upload_lock.acquire(False):raise BlockingIOError('Another transfer is in progress.')
        try:
            identity=value.get('id');base=self.sets.bundle(identity)
            if value.get('revision')!=self.revision(identity):raise ValueError('Sample set changed. Reload before deleting.')
            self._trash_folder().mkdir(exist_ok=True);base.rename(self._trash_folder()/uuid.uuid4().hex)
            return dict(ok=True,message='Sample set removed. A recovery copy is kept in Trash.')
        finally:self.library.upload_lock.release()

    @one_import
    def import_folder(self,value):
        base=self.stage(value.get('upload'));name=title(value.get('name','Sample Set'))
        # Native saved sets round-trip without losing their portable pad state.
        manifests=list(base.rglob('Set.json'))
        presets=list(base.rglob('Preset.json'))
        if manifests or presets:
            return self.import_native(base,manifests,presets)
        draft=plan(base,name)
        with tempfile.TemporaryDirectory(prefix='.decode-',dir=self.folder) as tmp:
            cache={};used=0
            for bank in draft['banks']:
                for pad in bank['pads']:
                    if not pad:continue
                    for layer in pad['layers']:
                        p=layer['path']
                        if p not in cache:
                            dest=Path(tmp)/(uuid.uuid4().hex+'.wav');info=convert(p,dest);used+=dest.stat().st_size
                            if used>MAX_PACKAGE:raise ValueError('Decoded expansion exceeds 1 GiB.')
                            cache[p]=(dest,info)
            # Build bank presets with velocity zones, then use the same atomic publisher.
            from app.model import new_project,validate_project
            from app.assets import collect_project
            prepared=Path(tmp)/'native';prepared.mkdir();meta=[]
            for index,bank in enumerate(draft['banks']):
                project=validate_project(new_project())
                for slot,pad in enumerate(bank['pads']):
                    if not pad:continue
                    dest,info=cache[pad['layers'][0]['path']];track=project['groups'][0]['pads'][slot]
                    track.update(name=title(pad['name'])[:32],sample=str(dest),start=0,end=info['frames'],zones=[])
                    if len(pad['layers'])>1:
                        from app.sampler import default_zone
                        for layer in pad['layers']:
                            wav,stats=cache[layer['path']];zone=default_zone(track);zone.update(sample=str(wav),start=0,end=stats['frames'],loop_end=stats['frames'],vel_lo=layer['vel_lo'],vel_hi=layer['vel_hi']);track['zones'].append(zone)
                bank_id=f'bank-{index+1:03}';directory=prepared/bank_id;collect_project(project,directory)
                doc=json.loads((directory/'Project.json').read_text());(directory/'Project.json').unlink()
                (directory/'Preset.json').write_text(json.dumps(dict(format='Machinista-preset',version=1,kind='GROUP',name=bank['name'],project=doc)))
                meta.append(dict(id=bank_id,name=bank['name']))
            (prepared/'Set.json').write_text(json.dumps(dict(format='Machinista-sample-set',version=1,name=draft['name'],banks=meta,notes=draft['notes'])))
            result=self.import_native(prepared,[prepared/'Set.json'],[])
        shutil.rmtree(base)
        return result

    def import_native(self,base,manifests,presets):
        if not self.library.upload_lock.acquire(False):raise BlockingIOError('Another transfer is in progress.')
        try:
            if manifests:
                if len(manifests)!=1:raise ValueError('Import one saved sample set per archive.')
                source=manifests[0].parent;meta=self.metadata(source)
                for bank in meta['banks']:
                    if (source/bank['id']).is_symlink():raise ValueError('Invalid bank directory.')
                    self.sets.document(source/bank['id'])
                name=meta['name']
            else:
                if len(presets)!=1:raise ValueError('Import one saved Group per archive.')
                source=presets[0].parent;doc=self.sets.document(source);name=doc.get('name',source.name)
            # Validate every member even when the manifest doesn't refer to it.
            size=0
            for p in source.rglob('*'):
                if p.is_symlink():raise ValueError('Symbolic links are not supported.')
                if p.is_file():
                    if p.suffix.lower() not in {'.wav','.json','.ttl'}:raise ValueError('Saved sample sets contain only WAV/JSON/TTL assets.')
                    size+=p.stat().st_size
                    if p.suffix.lower()=='.wav':
                        from app.wav_validation import validate_pcm
                        with p.open('r+b') as stream:validate_pcm(stream,{})
            if size>MAX_PACKAGE:raise ValueError('Sample set exceeds 1 GiB.')
            if shutil.disk_usage(self.folder).free<size+RESERVE:raise ValueError('Not enough free storage.')
            identity='set-'+uuid.uuid4().hex
            with tempfile.TemporaryDirectory(prefix='.publish-',dir=self.folder) as tmp:
                target=Path(tmp)/'set';shutil.copytree(source,target);target.rename(self.folder/identity)
            return dict(ok=True,id=identity,name=title(name),sets=[identity],notes=meta.get('notes',[]) if manifests else [])
        finally:self.library.upload_lock.release()

    @one_import
    def import_archive(self,name,stream,length):
        if Path(name).suffix.lower() not in ('.zip','.xpn') or not 0<length<=MAX_PACKAGE:raise ValueError('Upload a ZIP or MPC XPN up to 1 GiB. For Maschine, use its installed audio folder.')
        identity=self.start()['id'];base=self.stage(identity)
        try:
            with tempfile.TemporaryFile(dir=self.staging) as archive:
                remaining=length
                while remaining:
                    block=stream.read(min(65536,remaining))
                    if not block:raise ValueError('Incomplete expansion upload.')
                    archive.write(block);remaining-=len(block)
                archive.seek(0);seen=set();total=0
                with zipfile.ZipFile(archive) as z:
                    if len(z.infolist())>MAX_FILES:raise ValueError('Archive exceeds 8,192 entries.')
                    for info in z.infolist():
                        components=parts(info.filename);mode=info.external_attr>>16
                        if info.flag_bits&1 or stat.S_ISLNK(mode) or mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR):raise ValueError('Encrypted archives and special files are not supported.')
                        if any(p.startswith('.') or p=='__MACOSX' for p in components):continue
                        key='/'.join(components).casefold()
                        if key in seen:raise ValueError('Duplicate archive path.')
                        seen.add(key);total+=info.file_size
                        if total>MAX_PACKAGE:raise ValueError('Expanded archive exceeds 1 GiB.')
                        if info.is_dir():continue
                        if Path(info.filename).suffix.lower() not in AUDIO|METADATA:continue
                        if shutil.disk_usage(base).free<info.file_size+RESERVE:raise ValueError('Not enough free storage.')
                        target=base.joinpath(*components);target.parent.mkdir(parents=True,exist_ok=True)
                        with z.open(info) as inp,target.open('xb') as out:shutil.copyfileobj(inp,out,65536)
            return self.import_folder(dict(upload=identity,name=Path(name).stem))
        except zipfile.BadZipFile as error:raise ValueError('Invalid or damaged ZIP/XPN.') from error
        finally:
            if base.exists():shutil.rmtree(base)
