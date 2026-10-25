import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from backend import app as api
from backend.readiness import prepare_dataset
from backend.training import TrainingRuns
from backend.store import Store
from tests.ml.test_validation import record


def examples():
    return [dict(record(person,label),id=f'{person}-{label}',session_finished_at='2026-10-24',view='side',rule_label=label)
            for person in ['a','b','c','d'] for label in ['good','depth']]


def settings(**values):
    return dict(exercise='squat',model='baseline',feature_set='full',epochs=1,augment=False,export_onnx=False,**values)


class ModelLabTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent/'tmp')
        self.runner=TrainingRuns(Path(self.temp.name)/'experiments')

    def tearDown(self):
        self.runner.close();self.temp.cleanup()

    def wait_finished(self,run_id):
        deadline=time.monotonic()+60
        while self.runner.has_active() and time.monotonic()<deadline:time.sleep(.05)
        result=self.runner.get(run_id)
        self.assertNotIn(result['status'],['queued','running','cancelling'],result)
        return result

    def test_readiness_gaps_exclusions_and_valid_split(self):
        data=examples()+[dict(record(),id='unlabeled',label=None,session_finished_at='done',view='side'),
                         dict(record(),id='bad',label='unusable',session_finished_at='done',view='side'),
                         dict(record(),id='open',session_finished_at=None,view='side')]
        eligible,report=prepare_dataset(data,'squat')
        self.assertTrue(report['training_ready'])
        self.assertEqual(len(eligible),8)
        self.assertEqual(report['excluded'],{'unlabeled':1,'unusable':1,'unfinished_session':1})
        self.assertEqual(report['coverage'][0]['missing_samples'],146)
        self.assertEqual(report['coverage'][-1]['samples'],0)
        self.assertFalse(set(report['audit']['split']['train_people'])&set(report['audit']['split']['test_people']))

    def test_invalid_geometry_and_unseen_test_classes_block_training(self):
        data=examples();data[0]['keypoints']=[]
        self.assertFalse(prepare_dataset(data,'squat')[1]['training_ready'])
        data=examples();report=prepare_dataset(data,'squat')[1]
        test_person=report['audit']['split']['test_people'][0]
        for item in data:
            if item['participant_id']==test_person and item['label']=='depth':item['label']='torso_lean'
        report=prepare_dataset(data,'squat')[1]
        self.assertFalse(report['training_ready'])
        self.assertTrue(any('Held-out-only' in b for b in report['blockers']))
        self.assertFalse(prepare_dataset([],'plank')[1]['training_ready'])

    def test_actual_baseline_subprocess_saves_snapshot_metrics_and_parity(self):
        records,audit=prepare_dataset(examples(),'squat')
        options=settings();options['export_onnx']=True
        run=self.runner.create(options,records,audit)
        options['model']='changed-after-creation'
        result=self.wait_finished(run['id'])
        self.assertEqual(result['status'],'succeeded',result.get('log_tail'))
        self.assertEqual(result['settings']['model'],'baseline')
        self.assertEqual(result['validation']['status'],'passed')
        self.assertEqual(result['evaluation']['rule_baseline']['macro_f1'],1)
        self.assertTrue((Path(result['output_directory'])/'baseline.onnx').is_file())
        snapshot=json.loads((self.runner.root/run['id']/'dataset.json').read_text(encoding='utf-8'))
        self.assertEqual(len(snapshot),8)
        with patch.object(api,'training_runs',self.runner):
            response=api.training_report(run['id'])
            self.assertIn('attachment;',response.headers['content-disposition'])
            exported=json.loads(response.body)
            self.assertNotIn('log_tail',exported)
            self.assertNotIn('keypoints',json.dumps(exported))
        reloaded=TrainingRuns(self.runner.root)
        try:self.assertEqual(reloaded.get(run['id'])['status'],'succeeded')
        finally:reloaded.close()

    def test_single_job_cancellation_and_unknown_ids(self):
        entered=threading.Event();release=threading.Event()
        def controlled(*args):entered.set();release.wait(5);return False
        records,audit=prepare_dataset(examples(),'squat')
        with patch.object(self.runner,'_execute',controlled):
            run=self.runner.create(settings(),records,audit)
            self.assertTrue(entered.wait(2))
            try:
                with self.assertRaises(RuntimeError):self.runner.create(settings(),records,audit)
                self.runner.cancel(run['id'])
            finally:release.set()
            self.assertEqual(self.wait_finished(run['id'])['status'],'cancelled')
        self.assertIsNone(self.runner.get('../../README.md'))
        with self.assertRaises(KeyError):self.runner.cancel('missing')
        with self.assertRaises(RuntimeError):self.runner.cancel(run['id'])

    def test_failure_and_restart_interruption_are_persisted(self):
        records,audit=prepare_dataset(examples(),'squat')
        with patch.object(self.runner,'_execute',side_effect=RuntimeError('Controlled stage failure')):
            run=self.runner.create(settings(),records,audit)
            result=self.wait_finished(run['id'])
            self.assertEqual(result['status'],'failed')
            self.assertIn('Controlled stage failure',result['error'])
        path=self.runner.root/run['id']/'run.json'
        manifest=json.loads(path.read_text());manifest['status']='running';path.write_text(json.dumps(manifest))
        restarted=TrainingRuns(self.runner.root)
        try:self.assertEqual(restarted.get(run['id'])['status'],'interrupted')
        finally:restarted.close()

    def test_api_rejects_insufficient_data_and_unbounded_options(self):
        with patch.object(api,'store',Store(Path(self.temp.name)/'empty.sqlite3')),patch.object(api,'training_runs',self.runner):
            with self.assertRaises(HTTPException) as error:api.start_training(api.TrainingCreate(exercise='squat'))
            self.assertEqual(error.exception.status_code,422)
            with self.assertRaises(HTTPException):api.training_run('missing')
        for options in [dict(exercise='plank'),dict(exercise='squat',epochs=201),dict(exercise='squat',model='cnn',feature_set='angles'),dict(exercise='squat',command='anything')]:
            with self.assertRaises(ValidationError):api.TrainingCreate(**options)


if __name__=='__main__':unittest.main()
