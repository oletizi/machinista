"""Install an optional private inference environment and checksum-pinned model.

No root privileges, no global Python packages, no cloud processing. Internet is
used only for this explicit setup. Code and model credits: docs/STEM_SEPARATION.md.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import venv
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.stem_models import paths,MODEL_BASE,MODELS,MODEL_LICENSE


def install(root):
    base,python,model,receipt=paths(root);base.mkdir(parents=True,exist_ok=True)
    receipt.unlink(missing_ok=True)
    print('Creating isolated stem engine.',flush=True)
    if not python.exists():venv.EnvBuilder(with_pip=True).create(base/'venv')
    print('Installing numerical runtime.',flush=True)
    subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','--no-input','--only-binary=:all:',
                    'numpy==2.5.4','onnxruntime==1.31.1'],check=True)
    model.mkdir(exist_ok=True)
    for name,info in MODELS.items():
        temporary=base/'model.download'
        try:
            print('Downloading '+name+' (20 MB).',flush=True)
            digest=hashlib.sha256();total=0
            with urllib.request.urlopen(MODEL_BASE+name,timeout=60) as source,temporary.open('wb') as dest:
                while block:=source.read(1024*1024):
                    total+=len(block)
                    if total>info['size']:raise ValueError('Unexpected model size.')
                    digest.update(block);dest.write(block)
            if total!=info['size'] or digest.hexdigest()!=info['sha256']:raise ValueError('Stem model verification failed.')
            temporary.replace(model/name)
        finally:temporary.unlink(missing_ok=True)
    (base/'MODEL-LICENSE.txt').write_text('Spleeter ONNX exports: Apache-2.0; original Spleeter: MIT. See model card for pretrained-weight licensing notes.\n'+MODEL_LICENSE+'\nOriginal: https://github.com/deezer/spleeter\nConverter: https://github.com/matthewbae/spleeter-onnx-models\n')
    receipt.write_text(json.dumps(dict(models=MODELS,license='Apache-2.0 / upstream MIT',source=MODEL_BASE))+'\n')
    print('Stem engine ready.',flush=True)


if __name__=='__main__':install(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT)
