import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from ml.artifacts import artifact_hashes
from ml.audit import audit_records
from ml.preprocess import FEATURE_VERSION, load_records
from ml.validate_onnx import compare_predictions
from ml.inference import OnnxFormClassifier


def record(person='a', label='good'):
    points = np.zeros((8, 17, 3))
    points[:, :, 0] = np.linspace(.2, .8, 17)
    points[:, :, 1] = np.linspace(.1, .9, 17)
    points[:, :, 2] = .9
    return {'participant_id': person, 'exercise': 'squat', 'label': label, 'keypoints': points.tolist()}


class ValidationTests(unittest.TestCase):
    def test_parity_fails_label_or_probability_mismatch(self):
        expected = [{'label': 'good', 'confidence': .95}]
        self.assertEqual(compare_predictions(expected, expected)['status'], 'passed')
        self.assertEqual(compare_predictions(expected, [{'label': 'depth', 'confidence': .95}])['status'], 'failed')
        self.assertEqual(compare_predictions(expected, [{'label': 'good', 'confidence': .90}])['status'], 'failed')
        full = [{'label': 'good', 'confidence': .6, 'probabilities': {'good': .6, 'depth': .3, 'torso_lean': .1}}]
        changed = [{'label': 'good', 'confidence': .6, 'probabilities': {'good': .6, 'depth': .1, 'torso_lean': .3}}]
        self.assertEqual(compare_predictions(full, changed)['status'], 'failed')
        with self.assertRaises(ValueError):
            compare_predictions(expected, [{'label': 'good', 'confidence': float('nan')}])

    def test_live_activation_requires_parity_and_unchanged_artifacts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            folder = Path(folder)
            (folder / 'evaluation.json').write_text(json.dumps({'model': 'baseline', 'feature_version': FEATURE_VERSION}), encoding='utf-8')
            (folder / 'baseline.onnx').write_bytes(b'fake test artifact, never executed')
            with self.assertRaisesRegex(ValueError, 'validate_onnx'):
                OnnxFormClassifier(folder)
            validation = {'status': 'passed', 'samples': 3, 'artifact_sha256': artifact_hashes(folder, 'baseline')}
            (folder / 'onnx-validation.json').write_text(json.dumps(validation), encoding='utf-8')
            (folder / 'baseline.onnx').write_bytes(b'changed artifact')
            with self.assertRaisesRegex(ValueError, 'changed after'):
                OnnxFormClassifier(folder)

    def test_adapter_decodes_probabilities_and_rejects_wrong_exercise(self):
        outputs = [np.array(['good']), np.array([[.8, .2]])]
        session = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name='features')], run=lambda *_: outputs)
        fake_ort = SimpleNamespace(InferenceSession=lambda *_args, **_kwargs: session)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder, patch.dict('sys.modules', {'onnxruntime': fake_ort}):
            folder = Path(folder)
            (folder / 'evaluation.json').write_text(json.dumps({'model': 'baseline', 'exercise': 'squat',
                'feature_version': FEATURE_VERSION, 'labels': ['good', 'depth']}), encoding='utf-8')
            adapter = OnnxFormClassifier(folder, require_validation=False)
            result = adapter.predict_record(record())
            self.assertEqual(result['probabilities'], {'good': .8, 'depth': .2})
            with self.assertRaisesRegex(ValueError, 'exercise differs'):
                adapter.predict_record(dict(record(), exercise='pushup'))
            outputs[1] = np.array([[.8, .8]])
            with self.assertRaisesRegex(ValueError, 'Invalid classifier'):
                adapter.predict_record(record())

    def test_temporal_adapter_rejects_nonfinite_normalization(self):
        fake_ort = SimpleNamespace(InferenceSession=lambda *_args, **_kwargs: object())
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder, patch.dict('sys.modules', {'onnxruntime': fake_ort}):
            folder = Path(folder)
            (folder / 'evaluation.json').write_text(json.dumps({'model': 'cnn', 'feature_version': FEATURE_VERSION,
                'labels': ['good', 'depth']}), encoding='utf-8')
            np.savez(folder / 'normalization.npz', mean=np.full(91, np.nan), std=np.ones(91))
            with self.assertRaisesRegex(ValueError, 'Invalid model normalization'):
                OnnxFormClassifier(folder, require_validation=False)

    def test_dataset_audit_coverage_and_invalid_geometry(self):
        records = [record(person, label) for person in ['a', 'b', 'c', 'd'] for label in ['good', 'depth']]
        result = audit_records(records, 'squat')
        self.assertTrue(result['training_ready'])
        self.assertFalse(set(result['split']['train_people']) & set(result['split']['test_people']))
        records[0]['keypoints'] = []
        result = audit_records(records, 'squat')
        self.assertFalse(result['training_ready'])
        self.assertEqual(len(result['errors']), 1)
        self.assertFalse(audit_records([record()], 'squat')['training_ready'])

    def test_unusable_data_excluded_and_duplicate_exports_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            source = Path(folder) / 'reps.json'
            source.write_text(json.dumps([record(label='unusable'), record(label='unobservable'), record()]), encoding='utf-8')
            self.assertEqual(len(list(load_records(source))), 1)
            duplicated = dict(record(), id='same-rep')
            source.write_text(json.dumps([duplicated, duplicated]), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate recording'):
                list(load_records(source))


if __name__ == '__main__':
    unittest.main()
