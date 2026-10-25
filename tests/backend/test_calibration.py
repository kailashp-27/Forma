import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from fastapi import HTTPException
from backend import app as api
from backend.calibration import propose, calibrated_config
from backend.config import CONFIGS
from backend.engine import CoachEngine
from backend.store import Store
from tests.backend.test_engine import squat_with_angle, IdentityFilter


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'tmp')
        self.old=api.store
        api.store=Store(Path(self.temp.name)/'calibration.sqlite3')

    def tearDown(self):
        api.store=self.old
        self.temp.cleanup()

    def examples(self, participant='alice', variation='Bodyweight squat', finished=True):
        session=api.store.create_session('squat',participant,variation)
        set_id=api.store.create_set(session['id'],'squat')
        ids=[]
        for number in range(3):
            payload={'quality':100,'duration':2,'rep_number':number+1,'flags':[],'rule_label':'good',
                     'aspect_ratio':1,'keypoints':[squat_with_angle(a) for a in [170,170,150,120,90,90,90,100,120,150,170,170]],
                     'timestamps':[i*.1 for i in range(12)]}
            record_id=api.store.add_rep(session['id'],set_id,'squat',payload)
            api.store.label(record_id,'good')
            ids.append(record_id)
        if finished: api.store.finish_set(set_id);api.store.finish_session(session['id'])
        return ids

    def body(self, ids, **kwargs):
        return api.CalibrationCreate(exercise='squat',participant_id='alice',variation='Bodyweight squat',record_ids=ids,**kwargs)

    def test_calibration_is_scoped_snapshot_and_disable_only_affects_new_sessions(self):
        ids=self.examples()
        result=api.preview_calibration(self.body(ids))
        self.assertEqual(result['extended'],167)
        self.assertEqual(result['contracted'],98)
        profile=api.save_calibration(self.body(ids))
        session=api.create_session(api.SessionCreate(exercise='squat',participant_id='alice'))
        self.assertEqual(session['calibration']['id'],profile['id'])
        for participant,variation in [('bob','Bodyweight squat'),('alice','Supported squat')]:
            other=api.create_session(api.SessionCreate(exercise='squat',participant_id=participant,variation=variation))
            self.assertIsNone(other['calibration'])
        changed=calibrated_config(CONFIGS['squat'],profile)
        self.assertEqual(changed['extended'],167)
        self.assertEqual(changed['depth_target'],CONFIGS['squat']['depth_target'])
        self.assertEqual(changed['rules'],CONFIGS['squat']['rules'])
        self.assertEqual(CONFIGS['squat']['extended'],160)
        api.disable_calibration(profile['id'])
        self.assertIsNone(api.create_session(api.SessionCreate(exercise='squat',participant_id='alice'))['calibration'])
        self.assertEqual(api.store.session(session['id'])['calibration']['id'],profile['id'])
        reopened=Store(api.store.path)
        self.assertEqual(reopened.calibrations('alice','squat','Bodyweight squat')[0]['settings'],result)

    def test_replaced_profile_is_disabled_and_evidence_is_rechecked(self):
        ids=self.examples()
        first=api.save_calibration(self.body(ids));second=api.save_calibration(self.body(ids))
        enabled=[p for p in api.calibrations('alice','squat','Bodyweight squat')['profiles'] if p['enabled']]
        self.assertEqual([p['id'] for p in enabled],[second['id']])
        api.store.label(ids[0],'depth')
        with self.assertRaises(HTTPException): api.save_calibration(self.body(ids))
        self.assertNotEqual(first['id'],second['id'])

    def test_live_start_uses_session_snapshot_after_profile_is_disabled(self):
        from unittest.mock import patch
        from tests.backend.test_api import FakeSocket, run_inline
        profile=api.save_calibration(self.body(self.examples()))
        session=api.create_session(api.SessionCreate(exercise='squat',participant_id='alice'))
        api.disable_calibration(profile['id'])
        captured=[]
        def make_engine(config):
            captured.append(config)
            return CoachEngine(config)
        socket=FakeSocket([{'type':'start','exercise':'squat','session_id':session['id']},{'type':'stop'}])
        with patch.object(api,'CoachEngine',make_engine): run_inline(api.coach(socket))
        self.assertEqual(captured[0]['extended'],167)
        self.assertEqual(socket.messages[0]['calibration_id'],profile['id'])
        self.assertEqual(api.active_sessions,set())

    def test_calibration_rejects_cross_person_duplicates_and_unfinished_examples(self):
        ids=self.examples('bob')
        for selected in [ids,[ids[0]]*3,self.examples(finished=False)]:
            with self.assertRaises(HTTPException): api.preview_calibration(self.body(selected))

    def test_invalid_tracking_range_and_aspect_are_rejected(self):
        ids=self.examples()
        records=[api.store.record(i) for i in ids]
        for mutate in [lambda r:r.update(aspect_ratio=float('nan')),
                       lambda r:r.update(keypoints=[squat_with_angle(170)]*12),
                       lambda r:r.update(label='unusable')]:
            altered=copy.deepcopy(records);mutate(altered[0])
            with self.assertRaises(ValueError): propose(CONFIGS['squat'],altered)
        with self.assertRaises(ValueError): propose(CONFIGS['plank'],records)

    def test_new_rep_annotations_align_with_frames_and_survive_summary_loading(self):
        engine=CoachEngine(CONFIGS['squat']);engine.filter=IdentityFilter()
        result=None
        for i,a in enumerate([170,170,140,120,115,115,130,140,165,165]):
            result=engine.process(squat_with_angle(a),640,640,i*.15)
        rep=result['rep_completed']
        self.assertEqual(len(rep['frame_annotations']),len(rep['keypoints']))
        self.assertEqual(len(rep['timestamps']),len(rep['keypoints']))
        self.assertIsNotNone(rep['depth_marker_time'])
        self.assertEqual(rep['assessment_config']['depth_target'],100)
        session=api.store.create_session('squat','alice','Bodyweight squat')
        set_id=api.store.create_set(session['id'],'squat')
        record_id=api.store.add_rep(session['id'],set_id,'squat',rep)
        self.assertEqual(api.store.record(record_id)['frame_annotations'],rep['frame_annotations'])
        summary=api.store.records(include_keypoints=False)[0]
        self.assertNotIn('frame_annotations',summary)
        self.assertNotIn('keypoints',summary)

    def test_existing_database_migration_preserves_sessions(self):
        path=Path(self.temp.name)/'old.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY,exercise TEXT,participant_id TEXT,variation TEXT,started_at TEXT,finished_at TEXT)')
            db.execute("INSERT INTO sessions VALUES ('old','squat','alice','Bodyweight squat','2026-10-24',NULL)")
        db.close()
        migrated=Store(path)
        self.assertEqual(migrated.session('old')['participant_id'],'alice')
        self.assertIsNone(migrated.session('old')['calibration'])
        self.assertIsNone(migrated.create_session('squat','bob','Bodyweight squat')['calibration'])


if __name__=='__main__': unittest.main()
