"""Separately installed, version-pinned Spleeter model pack."""
from pathlib import Path
import json

MODEL_NAME='Spleeter · 4 stems'
MODEL_REVISION='486643021f18a4d057d282fff1d11b89a30e9887'
MODEL_BASE='https://huggingface.co/Best-Practice/spleeter-4stems-onnx/resolve/'+MODEL_REVISION+'/'
MODEL_LICENSE='https://huggingface.co/Best-Practice/spleeter-4stems-onnx/blob/'+MODEL_REVISION+'/README.md'
MODELS={'bass.fp16.onnx': {'size': 19714139, 'sha256': 'ba4c4949a27222492cca49859901a873b4b71461dc48c7c5a51f93d31eb11f55'}, 'drums.fp16.onnx': {'size': 19714140, 'sha256': '7ae4002e5633634674f74dc3356d5875b0da894d59ce0f60e844bb8f9cb8aa92'}, 'other.fp16.onnx': {'size': 19714140, 'sha256': '3cc59116cb7195946ab9596d8ca25984d09c0f8a70db8cf85d063132f97bc61d'}, 'vocals.fp16.onnx': {'size': 19714141, 'sha256': 'db47148ab1c52709ce694893f532c91abfe3edc4d46238939570e036a22878ca'}}


def paths(root):
    base=Path(root)/'presets/.stem-engine'
    return base,base/'venv/bin/python',base/'models',base/'ready.json'


def ready(root):
    base,python,folder,receipt=paths(root)
    if not python.is_file() or not receipt.is_file():return False
    try:
        return json.loads(receipt.read_text()).get('models')==MODELS and all((folder/name).stat().st_size==info['size'] for name,info in MODELS.items())
    except (OSError,ValueError):return False
