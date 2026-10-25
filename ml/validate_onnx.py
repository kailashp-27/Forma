"""Validate your own local training outputs: python -m ml.validate_onnx --help.

Reference .joblib/.pt files must come from your own trusted training run.
Parity establishes conversion consistency, not accuracy or coaching validity.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from ml.artifacts import artifact_hashes, sha256
from ml.preprocess import FEATURE_VERSION, load_records, record_features, tabular_features


def compare_predictions(reference, converted, tolerance=.001):
    if not reference or len(reference) != len(converted):
        raise ValueError('Parity requires matching non-empty prediction sets')
    if not np.isfinite(tolerance) or not 0 < tolerance <= .01:
        raise ValueError('Use a positive confidence tolerance no larger than 0.01')
    agreements = 0
    errors = []
    probability_errors = []
    for expected, actual in zip(reference, converted):
        for item in (expected, actual):
            confidence = item.get('confidence')
            if not isinstance(confidence, (int, float)) or not np.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError('Predictions must have finite probabilities between zero and one')
        agreements += expected['label'] == actual['label']
        errors.append(abs(expected['confidence'] - actual['confidence']))
        if 'probabilities' in expected or 'probabilities' in actual:
            a, b = expected.get('probabilities', {}), actual.get('probabilities', {})
            if not a or a.keys() != b.keys():
                raise ValueError('Reference and ONNX probability labels differ')
            for label in a:
                if not np.isfinite(a[label]) or not np.isfinite(b[label]) or not 0 <= a[label] <= 1 or not 0 <= b[label] <= 1:
                    raise ValueError('Invalid class probability')
                probability_errors.append(abs(a[label] - b[label]))
    max_probability_error = max(probability_errors, default=max(errors))
    return {'status': 'passed' if agreements == len(reference) and max(errors) <= tolerance and max_probability_error <= tolerance else 'failed',
            'samples': len(reference), 'label_agreement': agreements / len(reference),
            'max_confidence_error': max(errors), 'max_probability_error': max_probability_error,
            'confidence_tolerance': tolerance}


def reference_predictions(directory, report, records):
    kind = report.get('model', 'baseline')
    if kind == 'baseline':
        import joblib
        model = joblib.load(directory / 'baseline.joblib')
        x = np.stack([tabular_features(record_features(r, report.get('feature_set', 'full'))) for r in records])
        labels = model.predict(x)
        probabilities = model.predict_proba(x)
        return [{'label': str(label), 'confidence': float(np.max(p)),
                 'probabilities': {str(name): float(value) for name, value in zip(model.classes_, p)}} for label, p in zip(labels, probabilities)]
    import torch
    from ml.train_temporal import make_model
    model = make_model(kind, 91, len(report['labels']))
    model.load_state_dict(torch.load(directory / f'{kind}.pt', map_location='cpu', weights_only=True))
    model.eval()
    with np.load(directory / 'normalization.npz', allow_pickle=False) as norm:
        x = ((np.stack([record_features(r) for r in records]) - norm['mean']) / norm['std']).transpose(0, 2, 1)
    with torch.no_grad():
        probabilities = torch.softmax(model(torch.tensor(x, dtype=torch.float32)), dim=1).numpy()
    return [{'label': report['labels'][int(np.argmax(p))], 'confidence': float(np.max(p)),
             'probabilities': {str(name): float(value) for name, value in zip(report['labels'], p)}} for p in probabilities]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--tolerance', type=float, default=.001)
    args = parser.parse_args()
    directory = Path(args.model_dir)
    report = json.loads((directory / 'evaluation.json').read_text(encoding='utf-8'))
    held_out = set(report.get('test_people', []))
    if not held_out:
        parser.error('The training report must identify held-out participants')
    records = [r for r in load_records(args.data)
               if r['exercise'] == report['exercise'] and r['participant_id'] in held_out]
    if not records:
        parser.error('Supply reviewed recordings from the report\'s held-out participants')
    from ml.inference import OnnxFormClassifier
    converted = OnnxFormClassifier(directory, require_validation=False)
    reference = reference_predictions(directory, report, records)
    result = compare_predictions(reference, [converted.predict_record(r) for r in records], args.tolerance)
    result.update(feature_version=FEATURE_VERSION, artifact_sha256=artifact_hashes(directory, converted.kind),
                  reference_sha256=sha256(directory / f'{converted.kind}.{"joblib" if converted.kind == "baseline" else "pt"}'),
                  participants=sorted({r['participant_id'] for r in records}),
                  purpose='Conversion parity only; does not validate exercise form accuracy')
    (directory / 'onnx-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
