"""Inspect a reviewed dataset before training: python -m ml.audit --help."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from ml.preprocess import load_records, record_features, grouped_split


def audit_records(records, exercise):
    records = [r for r in records if r['exercise'] == exercise]
    classes = Counter(r['label'] for r in records)
    participants = defaultdict(Counter)
    errors = []
    valid = []
    for index, record in enumerate(records):
        participants[record['participant_id']][record['label']] += 1
        try:
            record_features(record)
            valid.append(record)
        except (ValueError, TypeError, KeyError) as error:
            errors.append({'record': record.get('id', index), 'reason': str(error)})
    warnings = []
    split = None
    if len(participants) < 3:
        warnings.append('Collect at least three participants; more are needed for meaningful generalization.')
    if len(classes) < 2:
        warnings.append('Collect at least two usable form classes before classification training.')
    rare = [name for name in classes if sum(counts[name] > 0 for counts in participants.values()) < 3]
    if rare:
        warnings.append('Classes represented by fewer than three people: ' + ', '.join(sorted(rare)))
    if len({r['participant_id'] for r in valid}) >= 3:
        train, test = grouped_split([r['participant_id'] for r in valid])
        train_labels = {valid[i]['label'] for i in train}
        unseen = sorted({valid[i]['label'] for i in test} - train_labels)
        if unseen:
            warnings.append('Held-out classes absent from training people: ' + ', '.join(unseen))
        split = {'train_people': sorted({valid[i]['participant_id'] for i in train}),
                 'test_people': sorted({valid[i]['participant_id'] for i in test}),
                 'train_samples': len(train), 'test_samples': len(test)}
    return {'exercise': exercise, 'samples': len(records), 'valid_samples': len(valid),
            'class_counts': dict(classes), 'participant_counts': {p: dict(c) for p, c in participants.items()},
            'errors': errors, 'warnings': warnings, 'split': split,
            'training_ready': bool(split and not errors and len(classes) >= 2 and
                                   len({r['label'] for i, r in enumerate(valid) if i in set(train)}) >= 2),
            'note': 'Readiness checks data structure and minimal coverage, not clinical or exercise validity.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True)
    parser.add_argument('--exercise', choices=['squat', 'pushup', 'plank', 'pullup'], default='squat')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        result = audit_records(list(load_records(args.data)), args.exercise)
    except (ValueError, OSError, TypeError) as error:
        parser.error(str(error))
    contents = json.dumps(result, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contents, encoding='utf-8')
    print(contents)
    if not result['training_ready']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
