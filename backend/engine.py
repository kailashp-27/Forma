import math
import time
import numpy as np
from .pose import OneEuro, extract_features

class CoachEngine:
    def __init__(self, config):
        self.config = config
        self.filter = OneEuro()
        self.reps = 0
        self.hold_seconds = 0.0
        self.state = 'waiting'
        self.last_time = None
        self.rep_started = None
        self.rep_frames = []
        self.rep_times = []
        self.rep_annotations = []
        self.rep_min_time = None
        self.rep_flags = {}
        self.rep_min = 180.0
        self.last_cue = 'Position your full body in the frame'
        self.last_features = None
        self.debounce = 0
        self.was_tracking = False
        self.tracked_side = None
        self.was_aligned = False

    def _clear_cycle(self):
        self.state = 'waiting'
        self.rep_started = None
        self.rep_frames, self.rep_times = [], []
        self.rep_annotations = []
        self.rep_min_time = None
        self.rep_flags = {}
        self.rep_min = 180.0
        self.debounce = 0

    def _reset_tracking(self):
        self._clear_cycle()
        self.filter.reset()
        self.last_features = None
        self.was_tracking = False
        self.tracked_side = None
        self.was_aligned = False

    def _threshold_frames(self, condition):
        """Count consecutive qualifying observations, never separated hits."""
        self.debounce = self.debounce + 1 if condition else 0
        return self.debounce >= 2

    def process(self, points, width=640, height=480, now=None):
        now = time.monotonic() if now is None else now
        dt = min(max(now - self.last_time, 0), 0.25) if self.last_time is not None else 0
        gap = self.last_time is not None and now - self.last_time > 0.5
        self.last_time = now
        if gap:
            self._reset_tracking()
        raw_features, side = extract_features(points, self.config['required_joints'], width, height, preferred_side=self.tracked_side)
        if raw_features is None:
            self._reset_tracking()
            return self._response([], None, False, 'Move into view; keep the whole body visible')
        if self.tracked_side is not None and side != self.tracked_side:
            self._reset_tracking()
        if not self.was_tracking:
            dt = 0
        self.was_tracking = True
        self.tracked_side = side
        p = np.asarray(points, dtype=float)
        smoothed = p.copy()
        smoothed[:,:2] = self.filter(p[:,:2], now)
        features, _ = extract_features(smoothed, self.config['required_joints'], width, height, preferred_side=side)
        if features is None:
            self._reset_tracking()
            return self._response([], None, False, 'Hold a clear camera position')
        metric = features.get(self.config['metric'])
        if metric is None:
            self._reset_tracking()
            return self._response(smoothed.tolist(), features, False, 'Keep the working joints visible')
        if self.last_features and dt > 0:
            for key in ('knee_angle', 'elbow_angle', 'body_angle'):
                value, previous = features.get(key), self.last_features.get(key)
                features[key + '_velocity'] = (value-previous)/dt if value is not None and previous is not None else 0
        self.last_features = features.copy()
        flags = self.check_rules(features)
        completed = None
        if self.config['id'] == 'plank':
            horizontal = features['torso_lean'] >= 55
            if not horizontal:
                flags.append({'flag':'camera_position', 'cue':'Take a horizontal plank position', 'severity':3})
            aligned = not flags
            self.state = 'holding' if aligned else 'adjusting'
            if aligned and self.was_aligned and not gap:
                self.hold_seconds += dt
            self.was_aligned = aligned
            self.last_cue = flags[0]['cue'] if flags else 'Steady hold. Keep breathing'
        else:
            extended, contracted = self.config['extended'], self.config['contracted']
            if self.state == 'waiting':
                if self._threshold_frames(metric >= extended):
                    self.state = 'ready'
                    self.debounce = 0
                self.last_cue = 'Begin from full extension'
            elif self.state == 'ready':
                self.last_cue = 'Ready. Move with control'
                if metric < extended - 12:
                    self.state, self.rep_started = 'descending', now
                    self.rep_frames, self.rep_times, self.rep_flags = [], [], {}
                    self.rep_annotations = []
                    self.rep_min_time = now
                    self.rep_min = metric
            if self.rep_started is not None:
                # Bounded memory; retain a uniformly thinning sequence for unusually slow reps.
                if len(self.rep_frames) >= 600:
                    self.rep_frames = self.rep_frames[::2]
                    self.rep_times = self.rep_times[::2]
                    self.rep_annotations = self.rep_annotations[::2]
                self.rep_frames.append(p.tolist())
                self.rep_times.append(now)
                self.rep_annotations.append({'features':{k:v for k,v in features.items() if not k.endswith('_velocity')},
                                             'flags':[dict(flag) for flag in flags], 'state':self.state})
                if metric < self.rep_min: self.rep_min_time = now
                self.rep_min = min(self.rep_min, metric)
                for flag in flags: self.rep_flags[flag['flag']] = flag
                if now - self.rep_started > 30:
                    self._clear_cycle()
                    self.last_cue = 'Movement timed out. Return to full extension'
                elif self.state == 'descending':
                    if self._threshold_frames(metric <= contracted):
                        self.state = 'bottom'
                        self.debounce = 0
                    elif metric >= extended:
                        self._clear_cycle()
                        self.last_cue = 'Use a fuller range of motion'
                elif self.state == 'bottom' and metric > contracted + 10:
                    self.state = 'ascending'
                elif self.state == 'ascending':
                    if self._threshold_frames(metric >= extended):
                        duration = now - self.rep_started
                        if duration >= self.config['min_rep_seconds']:
                            self.reps += 1
                            if self.rep_min > self.config.get('depth_target',contracted):
                                self.rep_flags['depth']={'flag':'depth','cue':'Use a fuller controlled range of motion','severity':2}
                            rep_flags = sorted(self.rep_flags.values(), key=lambda f: -f['severity'])
                            score = max(0, 100 - sum(f['severity']*10 for f in rep_flags))
                            completed = {'rep_number':self.reps, 'duration':round(duration,3),
                                'quality':score, 'flags':rep_flags, 'min_angle':self.rep_min,
                                'keypoints':self.rep_frames, 'timestamps':self.rep_times,
                                'frame_annotations':self.rep_annotations,
                                'depth_marker_time':self.rep_min_time if 'depth' in self.rep_flags else None,
                                'assessment_config':{k:self.config[k] for k in ('metric','extended','contracted','depth_target','rules') if k in self.config},
                                'calibration_id':self.config.get('calibration_id'),
                                'aspect_ratio':width/height,
                                'rule_label':rep_flags[0]['flag'] if rep_flags else 'good'}
                            self.last_cue = rep_flags[0]['cue'] if rep_flags else 'Good rep. Keep that control'
                        else:
                            self.last_cue = 'Slow down and move with control'
                        cue = self.last_cue
                        self._clear_cycle()
                        self.state, self.last_cue = 'ready', cue
                else:
                    self.debounce = 0
        response = self._response(smoothed.tolist(), features, True, self.last_cue, flags)
        if completed:
            response['rep_completed'] = completed
            response['quality'] = completed['quality']
            response['flags'] = completed['flags']
        return response

    def check_rules(self, features):
        flags = []
        for rule in self.config.get('rules', []):
            value = features.get(rule['feature'])
            if value is None: continue
            violates = value > rule['threshold'] if rule['operator'] == 'max' else value < rule['threshold']
            if violates:
                flags.append({k:rule[k] for k in ('flag','cue','severity')})
        return sorted(flags, key=lambda f:-f['severity'])

    def _response(self, points, features, tracking, cue, flags=None):
        flags = flags or []
        return {'type':'frame', 'keypoints':points, 'features':features or {}, 'state':self.state,
            'reps':self.reps, 'hold_seconds':round(self.hold_seconds,2),
            'quality':max(0,100-sum(f['severity']*10 for f in flags)) if tracking else None,
            'cue':cue, 'flags':flags, 'tracking':tracking}

def demo_pose(exercise, elapsed):
    """Deterministic illustrated motion, never presented as camera/model evidence."""
    p = np.zeros((17,3), dtype=float)
    p[:,2] = 0.95
    phase = (1 - math.cos(elapsed * math.pi / 2)) / 2
    if exercise == 'squat':
        knee_angle = 175 - 90 * phase
        bend = math.radians(180-knee_angle)
        ankle=np.array([0.57,0.89]); knee=np.array([0.57,0.65])
        hip=knee+np.array([-math.sin(bend)*0.18,-math.cos(bend)*0.24])
        shoulder=hip+np.array([-0.04,-0.24])
        elbow=shoulder+[0.10,0.08]; wrist=elbow+[0.12,0.01]
    elif exercise in ('pushup','plank'):
        elbow_angle = 175-95*phase if exercise == 'pushup' else 90
        shoulder=np.array([0.27,0.47+0.08*phase]); hip=np.array([0.52,0.56+0.04*phase])
        ankle=np.array([0.85,0.68]); knee=(hip+ankle)/2
        elbow=shoulder+[0.03,0.14]
        rad=math.radians(elbow_angle)
        a=(shoulder-elbow); a=a/np.linalg.norm(a)
        rotated=np.array([a[0]*math.cos(rad)-a[1]*math.sin(rad), a[0]*math.sin(rad)+a[1]*math.cos(rad)])
        wrist=elbow+rotated*0.14
    else:
        elbow_angle=175-125*phase
        wrist=np.array([0.50,0.15]); elbow=np.array([0.50,0.34])
        rad=math.radians(elbow_angle)
        shoulder=elbow+np.array([math.sin(rad)*0.19,-math.cos(rad)*0.19])
        hip=shoulder+[0.0,0.25]; knee=hip+[0.0,0.15]; ankle=knee+[0.0,0.14]
    for name, point in [('shoulder',shoulder),('elbow',elbow),('wrist',wrist),('hip',hip),('knee',knee),('ankle',ankle)]:
        from .pose import JOINTS
        for idx in JOINTS[name]: p[idx,:2]=point
    p[0,:2]=shoulder+[0,-0.09]
    for i in range(1,5): p[i,:2]=p[0,:2]+[(i%2-.5)*.03,0]
    return p.tolist()
