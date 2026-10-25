"""Identify the exact local model assets covered by a parity check."""
import hashlib
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact_hashes(directory, kind):
    directory = Path(directory)
    names = ['evaluation.json', f'{kind}.onnx']
    if kind != 'baseline':
        names.append('normalization.npz')
    return {name: sha256(directory / name) for name in names}
