import math
import unittest
import numpy as np
from backend.config import CONFIGS
from backend.engine import CoachEngine, demo_pose
from backend.pose import angle, extract_features

class IdentityFilter:
    def __call__(self, values, now): return values.copy()
    def reset(self): pass

def squat_with_angle(degrees, side=0):
    points=demo_pose('squat',0)
    bend=math.radians(180-degrees)
    knee=np.asarray(points[13][:2])
    hip=knee+[-math.sin(bend)*.24,-math.cos(bend)*.24]
    for idx in (11,12): points[idx][:2]=hip.tolist()
    for idx in (5,6): points[idx][:2]=(hip+[0,-.24]).tolist()
    for left,right in ((5,6),(7,8),(9,10),(11,12),(13,14),(15,16)):
        points[left][2]=.95 if side==0 else .8
        points[right][2]=.95 if side==1 else .8
    return points

class EngineTests(unittest.TestCase):
    def test_depth_and_extension_debounce_require_consecutive_observations(self):
        engine=CoachEngine(CONFIGS['squat']); engine.filter=IdentityFilter()
        sequence=[170,170,140,124,126,124,126]
        for i,value in enumerate(sequence): engine.process(squat_with_angle(value),640,640,i*.1)
        self.assertEqual(engine.state,'descending')
        engine.process(squat_with_angle(124),640,640,.7)
        engine.process(squat_with_angle(124),640,640,.8)
        self.assertEqual(engine.state,'bottom')
        for i,value in enumerate([140,161,159,161,159,161]):
            response=engine.process(squat_with_angle(value),640,640,.9+i*.1)
            self.assertNotIn('rep_completed',response)
        response=engine.process(squat_with_angle(161),640,640,1.5)
        self.assertEqual(engine.reps,1)
        self.assertEqual(response['quality'],response['rep_completed']['quality'])
        self.assertEqual(response['quality'],80)
        self.assertEqual(response['flags'],response['rep_completed']['flags'])

    def test_switching_visible_side_cancels_cycle_and_resets_smoothing(self):
        engine=CoachEngine(CONFIGS['squat'])
        for i,value in enumerate([170,170,140,130,130,130]):
            engine.process(squat_with_angle(value,0),640,640,i*.1)
        self.assertIn(engine.state,('descending','bottom'))
        switched=squat_with_angle(90,1)
        for idx in (5,7,9,11,13,15): switched[idx][2]=.1
        response=engine.process(switched,640,640,.6)
        self.assertEqual(engine.state,'waiting')
        self.assertEqual(engine.tracked_side,1)
        self.assertAlmostEqual(response['features']['knee_angle'],90,places=3)
        self.assertEqual(engine.reps,0)
        self.assertIsNone(engine.rep_started)

    def test_small_left_right_confidence_changes_keep_tracking_side_and_reps(self):
        engine=CoachEngine(CONFIGS['squat'])
        for i in range(30*20):
            points=demo_pose('squat',i/30)
            for left,right in ((5,6),(7,8),(9,10),(11,12),(13,14),(15,16)):
                points[left][2]=.85
                points[right][2]=.86 if i%2 else .84
            engine.process(points,640,640,i/30)
            self.assertEqual(engine.tracked_side,0)
        self.assertEqual(engine.reps,5)

    def test_plank_recovery_requires_two_aligned_samples(self):
        engine=CoachEngine(CONFIGS['plank']); engine.filter=IdentityFilter()
        good=demo_pose('plank',0)
        bad=demo_pose('plank',0)
        for idx in (11,12): bad[idx][1]-=.25
        engine.process(good,640,640,0)
        engine.process(good,640,640,.1)
        self.assertAlmostEqual(engine.hold_seconds,.1)
        engine.process(bad,640,640,.2)
        engine.process(good,640,640,.3)
        self.assertAlmostEqual(engine.hold_seconds,.1)
        engine.process(good,640,640,.4)
        self.assertAlmostEqual(engine.hold_seconds,.2)
    def run_motion(self, exercise, seconds=84):
        engine=CoachEngine(CONFIGS[exercise]); records=[]
        for i in range(int(seconds*30)):
            response=engine.process(demo_pose(exercise,i/30),640,640,i/30)
            if 'rep_completed' in response: records.append(response['rep_completed'])
        return engine,records

    def test_twenty_squats_count_without_duplicate(self):
        engine,records=self.run_motion('squat',80)
        self.assertEqual(engine.reps,20)
        self.assertEqual(len(records),20)
        self.assertTrue(all(r['quality']==100 for r in records))
        self.assertTrue(all(len(r['keypoints'])==len(r['timestamps']) for r in records))

    def test_other_dynamic_movements(self):
        for exercise in ('pushup','pullup'):
            with self.subTest(exercise=exercise):
                engine,records=self.run_motion(exercise,20)
                self.assertEqual(engine.reps,5)

    def test_stationary_pose_does_not_count(self):
        engine=CoachEngine(CONFIGS['squat'])
        for i in range(200): engine.process(demo_pose('squat',0),640,640,i/30)
        self.assertEqual(engine.reps,0)

    def test_shallow_attempts_are_recorded_and_flagged_for_labeling(self):
        engine=CoachEngine(CONFIGS['squat']); records=[]
        for i in range(30*8):
            elapsed=i/30
            points=demo_pose('squat',elapsed)
            phase=(1-math.cos(elapsed*math.pi/2))/2
            bend=math.radians(180-(175-60*phase))
            knee=np.asarray(points[13][:2])
            hip=knee+[-math.sin(bend)*.24,-math.cos(bend)*.24]
            for idx in (11,12): points[idx][:2]=hip.tolist()
            for idx in (5,6): points[idx][:2]=(hip+[-.04,-.24]).tolist()
            response=engine.process(points,640,640,elapsed)
            if 'rep_completed' in response: records.append(response['rep_completed'])
        self.assertEqual(len(records),2)
        self.assertTrue(all(rep['rule_label']=='depth' for rep in records))
        self.assertTrue(all(rep['quality']==80 for rep in records))

    def test_low_confidence_and_dropouts_cancel_cycle(self):
        engine=CoachEngine(CONFIGS['squat'])
        for i in range(60): engine.process(demo_pose('squat',i/30),640,640,i/30)
        points=demo_pose('squat',2)
        for point in points: point[2]=0.1
        result=engine.process(points,640,640,2)
        self.assertFalse(result['tracking'])
        self.assertIsNone(result['quality'])
        for i in range(61,120): engine.process(demo_pose('squat',i/30),640,640,i/30)
        self.assertEqual(engine.reps,0)

    def test_jitter_cannot_count(self):
        engine=CoachEngine(CONFIGS['squat'])
        for i in range(600):
            points=demo_pose('squat',0)
            points[13][0]+=0.002*math.sin(i)
            engine.process(points,640,640,i/30)
        self.assertEqual(engine.reps,0)

    def test_plank_only_counts_aligned_visible_time(self):
        engine=CoachEngine(CONFIGS['plank'])
        for i in range(31): engine.process(demo_pose('plank',0),640,640,i/30)
        self.assertAlmostEqual(engine.hold_seconds,1,places=2)
        engine.process([],640,640,1.1)
        engine.process(demo_pose('plank',0),640,640,1.2)
        self.assertAlmostEqual(engine.hold_seconds,1,places=2)
        engine.process(demo_pose('plank',0),640,640,10)
        self.assertAlmostEqual(engine.hold_seconds,1,places=2)

    def test_standing_is_not_a_plank(self):
        engine=CoachEngine(CONFIGS['plank'])
        for i in range(100): engine.process(demo_pose('squat',0),640,640,i/30)
        self.assertEqual(engine.hold_seconds,0)

    def test_degenerate_and_nonfinite_pose_rejected(self):
        self.assertIsNone(angle([0,0],[0,0],[1,1]))
        pose=demo_pose('squat',0); pose[5][0]=float('nan')
        self.assertEqual(extract_features(pose,['shoulder','hip'])[0],None)

    def test_aspect_ratio_correct_angles(self):
        p=demo_pose('squat',1)
        original=extract_features(p,CONFIGS['squat']['required_joints'],640,640)[0]
        for point in p: point[0]/=2
        scaled=extract_features(p,CONFIGS['squat']['required_joints'],1280,640)[0]
        self.assertAlmostEqual(original['knee_angle'],scaled['knee_angle'])

if __name__=='__main__': unittest.main()
