"""Download and verify the requested pretrained pose model (no webcam access)."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'models').mkdir(parents=True, exist_ok=True)
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'artifacts' / 'ultralytics'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'artifacts' / 'matplotlib'))
os.chdir(ROOT / 'models')
from ultralytics import YOLO

model = YOLO('yolo11n-pose.pt')
assert model.task == 'pose', f'Expected pose weights, got {model.task}'
print(f'Pose model ready: {ROOT / "models" / "yolo11n-pose.pt"}')
