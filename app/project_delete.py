"""Confirmed project removal with retained assets and a recoverable manifest."""
import json
import os
from pathlib import Path
import re
import secrets
from app.storage import save_json


def delete(root,value,app=None):
    if not isinstance(value,dict) or value.get('confirmed') is not True:raise ValueError('Confirm project deletion first.')
    identity=value.get('id')
    if not isinstance(identity,str) or identity!='current.json' and not re.fullmatch(r'PROJECT-[0-9]{4}\.json',identity):raise ValueError('Invalid project ID.')
    if app and (app.playing or app.recording or app.export_busy or app.capture_armed or app.capture_started is not None):raise ValueError('Stop playback and recording first.')
    folder=Path(root)/'projects';target=folder/identity
    if folder.is_symlink() or target.is_symlink() or not target.is_file():raise ValueError('Project not found.')
    if target.stat().st_size>8*1024**2:raise ValueError('Invalid project file.')
    document=json.loads(target.read_text())
    if not isinstance(document,dict):raise ValueError('Invalid project file.')
    if document.get('name')!=value.get('name') or str(target.stat().st_mtime_ns)!=value.get('version'):raise ValueError('Project changed. Refresh and try again.')
    current=folder/'current.json'
    active=app.active_project_file() if app else None
    if app and identity=='current.json' and app.project['name']!=value['name']:raise ValueError('Loaded project changed. Save and refresh first.')
    if app is None and current.exists():
        if current.is_symlink():raise ValueError('Invalid current project.')
        active_id=json.loads(current.read_text()).get('file_id');active=folder/(active_id+'.json') if isinstance(active_id,str) and re.fullmatch(r'PROJECT-[0-9]{4}',active_id) else None
    clear=identity=='current.json' or target==active
    paths=[target]
    if clear:
        for p in (active,current):
            if p is not None and p.exists() and p not in paths:paths.append(p)
    if any(p.is_symlink() or not p.is_file() or p.parent!=folder for p in paths):raise ValueError('Invalid project file.')
    trash=folder/'.trash'
    if trash.is_symlink():raise ValueError('Invalid project recovery folder.')
    trash.mkdir(mode=0o700,exist_ok=True);backup=trash/secrets.token_hex(16);backup.mkdir(mode=0o700)
    if app and clear:
        from app.assets import relative_assets
        save_json(backup/'Working.json',relative_assets(app.project_for_save(),folder))
    moved=[]
    try:
        for p in paths:p.rename(backup/p.name);moved.append(p)
        if clear:
            if app:app.reset_project()
            else:
                from app.model import new_project
                save_json(current,new_project())
        elif app:app.project_label_cache.pop(target,None)
    except BaseException:
        for p in reversed(moved):os.replace(backup/p.name,p)
        raise
    return dict(ok=True,message='Project deleted. A recovery copy was kept.',cleared=clear)
