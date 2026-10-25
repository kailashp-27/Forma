"""Check local readiness without opening a webcam. --deep also imports native dependencies."""
import argparse
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'artifacts' / 'ultralytics'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'artifacts' / 'matplotlib'))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--deep', action='store_true')
args = parser.parse_args()
missing = []
for module in ('fastapi','uvicorn','numpy','yaml','cv2','sklearn','torch','torchvision','ultralytics','onnxruntime','onnx','skl2onnx'):
    detail = ''
    try:
        ready = find_spec(module) is not None
        if ready and args.deep:
            import_module(module)
    except Exception as error:
        ready = False
        detail = f' ({type(error).__name__}: {error})'
    print(f'{"OK     " if ready else "MISSING"} {module}{detail}', flush=True)
    if not ready:
        missing.append(module)
for relative in ('frontend/dist/index.html','models/yolo11n-pose.pt'):
    ready = (ROOT / relative).is_file()
    print(f'{"OK     " if ready else "MISSING"} {relative}', flush=True)
    if not ready:
        missing.append(relative)
if missing:
    print('Run scripts/setup.ps1 to repair the project environment.')
else:
    print('Dependencies and artifacts are ready. Physical camera testing is still required.')
sys.exit(2 if missing else 0)
