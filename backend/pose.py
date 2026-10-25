"""Confidence-aware COCO pose features and optional local YOLO inference."""
import math
import os
import threading
import time
import numpy as np

JOINTS = {'shoulder': (5, 6), 'elbow': (7, 8), 'wrist': (9, 10),
          'hip': (11, 12), 'knee': (13, 14), 'ankle': (15, 16)}

def angle(a, b, c):
    u, v = np.asarray(a[:2]) - b[:2], np.asarray(c[:2]) - b[:2]
    norm = np.linalg.norm(u) * np.linalg.norm(v)
    if norm < 1e-8:
        return None
    return float(np.degrees(np.arccos(np.clip(np.dot(u, v) / norm, -1, 1))))

class OneEuro:
    def __init__(self, min_cutoff=1.0, beta=0.025, derivative_cutoff=1.0):
        self.min_cutoff, self.beta, self.derivative_cutoff = min_cutoff, beta, derivative_cutoff
        self.previous = self.derivative = self.t = None

    def reset(self):
        self.previous = self.derivative = self.t = None

    @staticmethod
    def alpha(cutoff, dt):
        return 1 / (1 + 1 / (2 * np.pi * cutoff * dt))

    def __call__(self, values, now):
        values = np.asarray(values, dtype=float)
        if self.previous is None:
            self.previous, self.derivative, self.t = values.copy(), np.zeros_like(values), now
            return values.copy()
        dt = max(now - self.t, 1e-4)
        a = self.alpha(self.derivative_cutoff, dt)
        self.derivative = a * ((values - self.previous) / dt) + (1-a) * self.derivative
        a = self.alpha(self.min_cutoff + self.beta * np.abs(self.derivative), dt)
        self.previous = a * values + (1-a) * self.previous
        self.t = now
        return self.previous.copy()

def extract_features(points, required, width=1, height=1, confidence=0.4, preferred_side=None):
    """Retain a visible preferred side; angles use aspect-correct pixels."""
    points = np.asarray(points, dtype=float)
    if points.shape != (17, 3) or not np.isfinite(points).all():
        return None, None
    sides = [[JOINTS[name][side] for name in required] for side in (0, 1)]
    visibility=[min(points[i, 2] for i in indices) for indices in sides]
    side=preferred_side if preferred_side in (0,1) and visibility[preferred_side]>=confidence else int(np.argmax(visibility))
    if any(points[i, 2] < confidence for i in sides[side]):
        return None, side
    p = points.copy()
    p[:, 0] *= width
    p[:, 1] *= height
    def j(name): return p[JOINTS[name][side]]
    def joint_angle(a, b, c):
        if any(j(name)[2] < confidence for name in (a,b,c)): return None
        return angle(j(a), j(b), j(c))
    torso = j('shoulder')[:2] - j('hip')[:2]
    torso_length = float(np.linalg.norm(torso))
    if torso_length < 1e-6: return None, side
    features = {
        'knee_angle': joint_angle('hip', 'knee', 'ankle'),
        'elbow_angle': joint_angle('shoulder', 'elbow', 'wrist'),
        'body_angle': joint_angle('shoulder', 'hip', 'ankle'),
        'torso_lean': float(np.degrees(np.arctan2(abs(torso[0]), abs(torso[1])))),
        'torso_length': torso_length,
    }
    return features, side

class PoseEstimator:
    def __init__(self):
        self.model = None
        self.lock = threading.Lock()
        self.error = None

    def infer(self, jpeg):
        import cv2
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None: raise ValueError('Invalid JPEG image')
        height, width = frame.shape[:2]
        if width * height > 1920 * 1080: raise ValueError('Use a camera resolution at or below 1920×1080')
        with self.lock:
            if self.model is None:
                from .config import ROOT
                os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'artifacts' / 'ultralytics'))
                os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'artifacts' / 'matplotlib'))
                from ultralytics import YOLO
                model_path = ROOT / 'models' / 'yolo11n-pose.pt'
                model_path.parent.mkdir(parents=True, exist_ok=True)
                if not model_path.is_file():
                    raise FileNotFoundError('Pose weights missing. Run scripts/download_model.py first.')
                self.model = YOLO(str(model_path))
            result = self.model.predict(frame, imgsz=640, verbose=False, device='cpu')[0]
            if result.keypoints is None or len(result.keypoints.data) == 0:
                return [], width, height
            # Single-user coaching: reject ambiguous multi-person frames.
            if len(result.keypoints.data) != 1:
                return [], width, height
            points = result.keypoints.data[0].cpu().numpy()
            points[:,0] /= width
            points[:,1] /= height
            return points.tolist(), width, height

ESTIMATOR = PoseEstimator()
