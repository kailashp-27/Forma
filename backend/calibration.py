"""Counting calibration from human-reviewed repetitions; form rules stay unchanged."""
from copy import deepcopy
import math
import statistics
import numpy as np
from .pose import extract_features


def propose(config, records):
    if config['id'] == 'plank':
        raise ValueError('Plank uses alignment and hold time, not repetition range calibration')
    if not 3 <= len(records) <= 20 or len({r['id'] for r in records}) != len(records):
        raise ValueError('Select 3–20 distinct, human-reviewed good repetitions')
    lows, highs, evidence = [], [], []
    for record in records:
        if record.get('label') != 'good' or record.get('view') != 'side':
            raise ValueError('Every example must have a human good label and side view')
        aspect = record.get('aspect_ratio')
        if not isinstance(aspect, (int, float)) or not math.isfinite(aspect) or not .2 <= aspect <= 5:
            raise ValueError('Each example needs a valid saved camera aspect ratio')
        points = record.get('keypoints', [])
        if not 8 <= len(points) <= 600:
            raise ValueError('Each example needs 8–600 saved pose frames')
        angles = []
        side = None
        for frame in points:
            features, side = extract_features(frame, config['required_joints'], aspect, 1, preferred_side=side)
            if features and features.get(config['metric']) is not None:
                angles.append(features[config['metric']])
        if len(angles) < max(8, len(points) * .8):
            raise ValueError('An example has too few observable frames; review its tracking')
        low, high = (float(np.percentile(angles, p)) for p in (10, 95))
        if high - low < 35:
            raise ValueError('Each example needs at least 35 degrees of observable movement')
        lows.append(low); highs.append(high)
        evidence.append({'record_id': record['id'], 'low_angle': round(low, 1), 'high_angle': round(high, 1), 'frames': len(angles)})
    if max(highs) - min(highs) > 20 or max(lows) - min(lows) > 25:
        raise ValueError('Examples vary too much; select reps with a consistent camera and range')
    extended = round(statistics.median(highs) - 3)
    contracted = round(statistics.median(lows) + 8)
    if not 130 <= extended <= 177 or not 40 <= contracted <= 145 or extended - contracted < 25:
        raise ValueError('Observed angles do not support stable counting thresholds; keep defaults and review the examples')
    return {'version': 1, 'metric': config['metric'], 'extended': extended, 'contracted': contracted,
            'defaults': {'extended': config['extended'], 'contracted': config['contracted']},
            'examples': evidence, 'note': 'Experimental counting calibration. Depth targets, alignment rules and quality scoring are unchanged.'}


def calibrated_config(config, profile):
    result = deepcopy(config)
    if profile:
        settings = profile['settings']
        if settings.get('version') != 1 or settings.get('metric') != config['metric']:
            raise ValueError('Incompatible calibration profile')
        extended, contracted = settings['extended'], settings['contracted']
        if not 130 <= extended <= 177 or not 40 <= contracted <= 145 or extended - contracted < 25:
            raise ValueError('Invalid calibration thresholds')
        result.update(extended=extended, contracted=contracted, calibration_id=profile['id'])
    return result
