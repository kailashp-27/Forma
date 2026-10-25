"""Contract and persistence checks without OS loopback sockets."""
import json
import tempfile
import unittest
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError
from backend import app as module
from backend.store import Store

class FakeSocket:
    headers={}
    def __init__(self,commands):
        self.commands=[{'type':'websocket.receive','text':json.dumps(c)} for c in commands]
        self.commands.append({'type':'websocket.disconnect'})
        self.messages=[]
    async def accept(self): pass
    async def receive(self): return self.commands.pop(0)
    async def send_json(self,value): self.messages.append(value)
    async def close(self,code): self.messages.append({'closed':code})

def run_inline(coroutine):
    try: coroutine.send(None)
    except StopIteration: return
    finally: coroutine.close()
    raise AssertionError('Unexpected real async I/O in offline test')

class ApiTests(unittest.TestCase):
    def test_setup_analyzes_frames_without_saving_or_counting(self):
        from unittest.mock import patch
        from backend.engine import demo_pose
        async def infer_inline(function, *args):
            return function(*args)
        socket=FakeSocket([{'type':'setup','exercise':'squat'},{'type':'stop'}])
        socket.commands.insert(1,{'type':'websocket.receive','bytes':b'test-frame'})
        with patch.object(module.ESTIMATOR,'infer',return_value=(demo_pose('squat',0),640,640)), patch.object(module.asyncio,'to_thread',infer_inline):
            run_inline(module.coach(socket))
        self.assertTrue(socket.messages[0]['setup'])
        frame=next(m for m in socket.messages if m.get('type')=='frame')
        self.assertTrue(frame['setup'])
        self.assertEqual(len(frame['keypoints']),17)
        self.assertEqual(frame['reps'],0)
        self.assertEqual(frame['hold_seconds'],0)
        self.assertIsNone(frame['quality'])
        self.assertNotIn('rep_completed',frame)
        self.assertEqual(module.sessions(),[])
        self.assertEqual(module.records(),[])
        self.assertEqual(module.active_sessions,set())

    def setUp(self):
        temp_root=Path(__file__).resolve().parent/'tmp'
        temp_root.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=temp_root)
        self.old=module.store
        module.store=Store(Path(self.temp.name)/'test.sqlite3')
        module.active_sessions.clear()
    def tearDown(self):
        module.store=self.old
        module.active_sessions.clear()
        self.temp.cleanup()
    def create(self,exercise='squat'):
        return module.create_session(module.SessionCreate(exercise=exercise,participant_id='alice'))

    def test_session_and_record_roundtrip(self):
        session=self.create(); set_id=module.store.create_set(session['id'],'squat')
        record_id=module.store.add_rep(session['id'],set_id,'squat',{'quality':90,'flags':[],
            'keypoints':[[[0.1,0.2,0.9]]*17]*32,'timestamps':list(range(32)),
            'rule_label':'good','aspect_ratio':4/3})
        module.store.finish_set(set_id)
        self.assertEqual(module.records()[0]['id'],record_id)
        self.assertEqual(module.dataset(),[])
        module.label_record(record_id,module.LabelUpdate(label='good'))
        self.assertEqual(module.dataset()[0]['participant_id'],'alice')
        self.assertEqual(module.dataset()[0]['aspect_ratio'],4/3)
        result=module.finish(session['id'])
        self.assertEqual(result['total_reps'],1)
        self.assertIsNotNone(result['finished_at'])

    def test_invalid_session_and_labels(self):
        with self.assertRaises(HTTPException): module.session('missing')
        with self.assertRaises(ValidationError): module.SessionCreate(exercise='unknown')
        with self.assertRaises(HTTPException): module.label_record('missing',module.LabelUpdate(label='good'))
        with self.assertRaises(ValidationError): module.LabelUpdate(label='invented')
        with self.assertRaises(ValidationError): module.SessionCreate(exercise='squat',variation='Standard push-up')
        self.assertEqual(module.SessionCreate(exercise='squat',variation='Bodyweight squat').variation,'Bodyweight squat')

    def test_record_and_export_filters_are_combined(self):
        alice=self.create(); squat_set=module.store.create_set(alice['id'],'squat')
        first=module.store.add_rep(alice['id'],squat_set,'squat',{'quality':90})
        second=module.store.add_rep(alice['id'],squat_set,'squat',{'quality':80})
        bob=module.store.create_session('pushup','bob','Incline push-up')
        pushup_set=module.store.create_set(bob['id'],'pushup')
        third=module.store.add_rep(bob['id'],pushup_set,'pushup',{'quality':100})
        module.label_record(first,module.LabelUpdate(label='good'))
        module.label_record(third,module.LabelUpdate(label='good'))
        self.assertEqual(len(module.records()),3)
        self.assertEqual([r['id'] for r in module.records(participant_id='alice',label_status='unlabeled')],[second])
        self.assertEqual([r['id'] for r in module.records(exercise='pushup',label_status='labeled')],[third])
        self.assertEqual([r['id'] for r in module.dataset(exercise='squat',participant_id='alice')],[first])
        self.assertEqual(len(module.dataset(label_status='all')),3)
        self.assertEqual(module.records(participant_id=''),[])
        self.assertEqual(module.dataset(exercise='plank'),[])

    def test_lightweight_record_list_and_selected_detail_preserve_sequence(self):
        session=self.create(); set_id=module.store.create_set(session['id'],'squat')
        points=[[[.1,.2,.95] for _ in range(17)] for _ in range(32)]
        timestamps=[i/30 for i in range(32)]
        first=module.store.add_rep(session['id'],set_id,'squat',{'quality':80,'duration':1.2,
            'keypoints':points,'timestamps':timestamps,'flags':[{'flag':'depth'}],'rule_label':'depth'})
        module.store.add_rep(session['id'],set_id,'squat',{'quality':100,'keypoints':points[:16],'timestamps':timestamps[:16]})
        summaries=module.records(exercise='squat',participant_id='alice',include_keypoints=False)
        self.assertEqual([r['frame_count'] for r in summaries],[32,16])
        self.assertTrue(all('keypoints' not in r and 'timestamps' not in r for r in summaries))
        self.assertEqual(summaries[0]['quality'],80)
        self.assertEqual(summaries[0]['rule_label'],'depth')
        self.assertEqual(summaries[0]['participant_id'],'alice')
        detail=module.record(first)
        self.assertEqual(detail['keypoints'],points)
        self.assertEqual(detail['timestamps'],timestamps)
        self.assertEqual(detail['frame_count'],32)
        self.assertEqual(module.records()[0]['keypoints'],points)
        with self.assertRaises(HTTPException) as raised: module.record('missing')
        self.assertEqual(raised.exception.status_code,404)

    def test_analytics_observed_quality_tempo_and_participant_isolation(self):
        alice=self.create(); set_id=module.store.create_set(alice['id'],'squat')
        for number,(quality,duration) in enumerate([(100,2),(90,3),(80,4)],1):
            module.store.add_rep(alice['id'],set_id,'squat',{'quality':quality,'duration':duration,'rep_number':number})
        module.store.finish_set(set_id)
        empty_set=module.store.create_set(alice['id'],'squat'); module.store.finish_set(empty_set)
        plank=module.store.create_session('plank','alice','Forearm plank')
        hold=module.store.create_set(plank['id'],'plank'); module.store.finish_set(hold,30)
        bob=module.store.create_session('squat','bob','Bodyweight squat')
        bob_set=module.store.create_set(bob['id'],'squat')
        module.store.add_rep(bob['id'],bob_set,'squat',{'quality':0,'duration':100})
        result=module.analytics('alice')
        self.assertEqual(result['summary'],{'sessions':2,'total_reps':3,'total_hold_seconds':30,'average_quality':90})
        squat=next(s for s in result['sessions'] if s['id']==alice['id'])
        self.assertEqual(squat['quality'],90)
        self.assertEqual(squat['mean_rep_seconds'],3)
        observed=next(s for s in squat['sets'] if s['id']==set_id)
        self.assertEqual(observed['quality_slope_per_rep'],-10)
        self.assertEqual(observed['fatigue_heuristic'],'declining_quality')
        self.assertEqual(observed['rep_qualities'],[100,90,80])
        empty=next(s for s in squat['sets'] if s['id']==empty_set)
        self.assertIsNone(empty['quality_slope_per_rep'])
        self.assertIsNone(empty['quality'])
        trend=next(e for e in result['exercises'] if e['exercise']=='squat')['quality_trend']
        self.assertEqual(len(trend),1)
        self.assertEqual(trend[0]['quality'],90)
        no_data=module.analytics('new-person')
        self.assertEqual(no_data['sessions'],[])
        self.assertEqual(no_data['summary']['total_reps'],0)
        self.assertIsNone(no_data['summary']['average_quality'])

    def test_single_rep_analytics_has_no_fatigue_slope(self):
        alice=self.create(); set_id=module.store.create_set(alice['id'],'squat')
        module.store.add_rep(alice['id'],set_id,'squat',{'quality':90,'duration':2})
        result=module.analytics('alice')['sessions'][0]['sets'][0]
        self.assertIsNone(result['quality_slope_per_rep'])
        self.assertEqual(result['fatigue_heuristic'],'insufficient_data')

    def test_demo_never_writes_training_or_session_data(self):
        socket=FakeSocket([{'type':'demo','exercise':'squat'},*({'type':'tick'} for _ in range(3)),{'type':'stop'}])
        run_inline(module.coach(socket))
        self.assertEqual(socket.messages[0]['type'],'started')
        for frame in socket.messages[1:4]:
            self.assertTrue(frame['demo'])
            self.assertEqual(len(frame['keypoints']),17)
        self.assertEqual(socket.messages[-1]['type'],'stopped')
        self.assertEqual(module.sessions(),[])
        self.assertEqual(module.records(),[])

    def test_set_lifecycle_and_finish_conflict(self):
        session=self.create(); module.active_sessions.add(session['id'])
        with self.assertRaises(HTTPException) as raised: module.finish(session['id'])
        self.assertEqual(raised.exception.status_code,409)
        module.active_sessions.clear()
        socket=FakeSocket([{'type':'start','exercise':'squat','session_id':session['id']},{'type':'stop'}])
        run_inline(module.coach(socket))
        self.assertEqual(socket.messages[0]['type'],'started')
        self.assertEqual(socket.messages[-1]['type'],'stopped')
        self.assertEqual(module.active_sessions,set())
        self.assertIsNotNone(module.finish(session['id'])['finished_at'])
        self.assertIsNotNone(module.session(session['id'])['sets'][0]['finished_at'])

    def test_progression_separates_people(self):
        for _ in range(3):
            session=self.create(); set_id=module.store.create_set(session['id'],'squat')
            for rep in range(10): module.store.add_rep(session['id'],set_id,'squat',{'quality':100,'flags':[]})
            module.store.finish_set(set_id)
        self.assertTrue(next(p for p in module.progression('alice') if p['exercise']=='squat')['ready'])
        self.assertFalse(next(p for p in module.progression('local-user') if p['exercise']=='squat')['ready'])

    def test_disconnect_closes_active_set(self):
        session=self.create()
        socket=FakeSocket([{'type':'start','exercise':'squat','session_id':session['id']}])
        run_inline(module.coach(socket))
        self.assertIsNotNone(module.session(session['id'])['sets'][0]['finished_at'])
        self.assertEqual(module.active_sessions,set())

    def test_untrusted_websocket_origin_rejected(self):
        socket=FakeSocket([]); socket.headers={'origin':'https://untrusted.invalid'}
        run_inline(module.coach(socket))
        self.assertEqual(socket.messages,[{'closed':1008}])

    def test_optional_model_uncertainty_and_failure_fall_back(self):
        original=module.form_classifier
        class Stub:
            def predict_record(self,record): return {'label':'depth','confidence':0.3,'experimental':True}
        try:
            module.form_classifier=Stub()
            self.assertFalse(module.classify_rep({'keypoints':[]},'squat')['accepted'])
            module.form_classifier.predict_record=lambda _: {'label':'depth','confidence':0.95,'experimental':True}
            self.assertTrue(module.classify_rep({'keypoints':[]},'squat')['accepted'])
            def broken(_): raise ValueError('Incompatible exercise')
            module.form_classifier.predict_record=broken
            self.assertFalse(module.classify_rep({'keypoints':[]},'squat')['accepted'])
        finally:
            module.form_classifier=original

if __name__=='__main__': unittest.main()
