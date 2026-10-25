"""Feature contract shared by training and later ONNX inference.

Input keypoints follow COCO's 17-joint order, in normalized image coordinates.
Low-confidence coordinates are interpolated only inside an otherwise valid rep;
records with no visible torso or excessive missing data are rejected.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

FEATURE_VERSION = "coco17-torso-angles-velocity-aspect-v2"
JOINTS = [(5, 7, 9), (6, 8, 10), (5, 11, 13), (6, 12, 14), (11, 13, 15), (12, 14, 16)]


def resample(values: np.ndarray, frames: int = 32, timestamps=None) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if len(values) < 2 or frames < 2 or not np.isfinite(values).all():
        raise ValueError("A rep needs at least two finite frames")
    source = np.linspace(0, 1, len(values)) if timestamps is None else np.asarray(timestamps, dtype=float)
    if source.shape != (len(values),) or not np.isfinite(source).all() or np.any(np.diff(source) <= 0):
        raise ValueError("Timestamps must be finite, strictly increasing, and match frames")
    source = (source - source[0]) / (source[-1] - source[0])
    target = np.linspace(0, 1, frames)
    flat = values.reshape(len(values), -1)
    return np.stack([np.interp(target, source, flat[:, j]) for j in range(flat.shape[1])], axis=1).reshape((frames,) + values.shape[1:]).astype(np.float32)


def temporal_features(keypoints, frames: int = 32, timestamps=None, aspect_ratio: float = 4/3) -> np.ndarray:
    points = np.asarray(keypoints, dtype=np.float32).copy()
    if points.ndim != 3 or points.shape[1:] != (17, 3) or len(points) < 2 or not np.isfinite(points).all():
        raise ValueError("Expected finite keypoints with shape [T,17,3], T >= 2")
    valid = points[:, :, 2] >= .35
    if not valid[:, [5, 6, 11, 12]].any(axis=0).all() or valid.mean() < .55:
        raise ValueError("Insufficient visible joints; label this recording unobservable")
    for joint in range(17):
        seen = np.flatnonzero(valid[:, joint])
        for axis in range(2):
            points[:, joint, axis] = np.interp(np.arange(len(points)), seen, points[seen, joint, axis]) if len(seen) else 0
    points = resample(points, frames, timestamps)
    if not np.isfinite(aspect_ratio) or aspect_ratio <= 0:
        raise ValueError("Aspect ratio must be positive and finite")
    xy = points[:, :, :2].copy()
    xy[:, :, 0] *= aspect_ratio
    hip = (xy[:, 11] + xy[:, 12]) / 2
    shoulder = (xy[:, 5] + xy[:, 6]) / 2
    scale = np.linalg.norm(shoulder - hip, axis=1)
    if np.any(scale < .015):
        raise ValueError("Degenerate torso scale")
    normalized = (xy - hip[:, None, :]) / scale[:, None, None]
    angles = []
    for a, b, c in JOINTS:
        u, v = xy[:, a] - xy[:, b], xy[:, c] - xy[:, b]
        denom = np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1)
        angles.append(np.arccos(np.clip(np.sum(u*v, axis=1) / np.maximum(denom, 1e-7), -1, 1)) / np.pi)
    positions = normalized.reshape(frames, -1)
    velocities = np.gradient(positions, axis=0)
    return np.concatenate([positions, np.stack(angles, axis=1), velocities, points[:, :, 2]], axis=1).astype(np.float32)


def tabular_features(sequence: np.ndarray) -> np.ndarray:
    """Temporal statistics and coarse phase samples for gradient boosting."""
    return np.concatenate([sequence.mean(0), sequence.std(0), sequence.min(0), sequence.max(0), sequence[::4].reshape(-1)]).astype(np.float32)


def augment(keypoints, rng: np.random.Generator, mirror=True):
    """Training-only augmentation, before feature extraction; never on test data."""
    points = np.asarray(keypoints, dtype=np.float32).copy()
    if mirror and rng.random() < .5:
        points[:, :, 0] = 1 - points[:, :, 0]
        for left, right in [(1,2),(3,4),(5,6),(7,8),(9,10),(11,12),(13,14),(15,16)]:
            points[:, [left,right]] = points[:, [right,left]]
    points[:, :, :2] += rng.normal(0, .002, points[:, :, :2].shape)
    # Monotonic time warp changes local speed while preserving endpoints.
    source = np.concatenate([[0.], np.cumsum(rng.uniform(.6, 1.4, len(points)-1))])
    return resample(points, len(points), source)


def load_records(path: str | Path):
    path = Path(path)
    records = []
    files = sorted(p for p in path.rglob('*') if p.suffix in {'.json', '.jsonl'}) if path.is_dir() else [path]
    for file in files:
        if file.suffix == ".jsonl":
            records.extend(json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip())
        else:
            data = json.loads(file.read_text(encoding="utf-8"))
            records.extend(data if isinstance(data, list) else [data])
    seen = set()
    for record in records:
        if not isinstance(record, dict) or not all(isinstance(record.get(key), str) and record[key].strip() for key in ("participant_id", "exercise", "label")):
            raise ValueError("Every record requires participant_id, exercise and label")
        if record.get('id'):
            record_id = str(record['id'])
            if record_id in seen:
                raise ValueError(f'Duplicate recording ID: {record_id}. Use one export of each rep.')
            seen.add(record_id)
        if record["label"] in {"unobservable", "unlabeled", "unusable"}:
            continue
        yield record


def record_features(record, feature_set='full'):
    """Use the same preprocessing at training, parity checking and inference."""
    sequence = temporal_features(record['keypoints'], timestamps=record.get('timestamps'),
                                 aspect_ratio=record.get('aspect_ratio', 4/3))
    if feature_set == 'angles':
        return sequence[:, 34:40]
    if feature_set == 'keypoints':
        return sequence[:, :34]
    if feature_set != 'full':
        raise ValueError('Unsupported feature set')
    return sequence


def grouped_split(groups, test_size=.25, seed=42):
    """Hold out whole people. No random rep-wise split is permitted."""
    groups = np.asarray(groups)
    people = np.unique(groups)
    if len(people) < 3:
        raise ValueError("Collect at least three participants before training/evaluation")
    shuffled = np.random.default_rng(seed).permutation(people)
    test_people = shuffled[:max(1, min(len(people)-2, int(np.ceil(len(people)*test_size))))]
    test = np.flatnonzero(np.isin(groups, test_people))
    train = np.flatnonzero(~np.isin(groups, test_people))
    return train, test
