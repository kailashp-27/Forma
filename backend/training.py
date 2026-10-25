"""Bounded, local experiment runner; no commands or model activation from callers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid
from .config import ROOT

ACTIVE={'queued','running','cancelling'}
def now(): return datetime.now(timezone.utc).isoformat()


class TrainingRuns:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='forma-training')
        self.runs={};self.processes={};self.closed=False
        for path in self.root.glob('*/run.json'):
            if not re.fullmatch('[a-f0-9]{32}',path.parent.name): continue
            try:
                run=json.loads(path.read_text(encoding='utf-8'))
                if run['id']!=path.parent.name: continue
                if run['status'] in ACTIVE:
                    run.update(status='interrupted',finished_at=now(),error='App stopped before this experiment finished. Start a new run to retry.')
                    self._write(run)
                self.runs[run['id']]=run
            except (OSError,ValueError,KeyError): continue

    def _write(self,run):
        folder=self.root/run['id'];folder.mkdir(exist_ok=True)
        temporary=folder/'run.json.tmp';temporary.write_text(json.dumps(run,indent=2),encoding='utf-8');temporary.replace(folder/'run.json')

    def _update(self,run_id,**values):
        with self.lock:
            self.runs[run_id].update(values);self._write(self.runs[run_id])

    def list(self):
        with self.lock:return deepcopy(sorted(self.runs.values(),key=lambda r:r['created_at'],reverse=True))

    def has_active(self):
        with self.lock:return any(r['status'] in ACTIVE for r in self.runs.values())

    def get(self,run_id):
        with self.lock:
            if run_id not in self.runs: return None
            result=deepcopy(self.runs[run_id])
        folder=self.root/run_id
        for key,path in [('audit',folder/'audit.json'),('evaluation',folder/'model'/'evaluation.json'),('validation',folder/'model'/'onnx-validation.json')]:
            try:result[key]=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):result[key]=None
        try:
            with (folder/'training.log').open('rb') as log:
                log.seek(0,2);log.seek(max(0,log.tell()-12000));result['log_tail']=log.read().decode('utf-8',errors='replace')
        except OSError:result['log_tail']=''
        return result

    def create(self,settings,records,audit):
        if not audit.get('training_ready'):raise ValueError('Dataset must pass readiness checks before training')
        with self.lock:
            if self.closed or any(r['status'] in ACTIVE for r in self.runs.values()): raise RuntimeError('An experiment is already active or the runner is shutting down')
            run_id=uuid.uuid4().hex;folder=self.root/run_id;folder.mkdir()
            contents=json.dumps(records,ensure_ascii=False).encode('utf-8');(folder/'dataset.json').write_bytes(contents)
            (folder/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
            run={'id':run_id,'created_at':now(),'finished_at':None,'status':'queued','stage':'queued','settings':deepcopy(settings),
                 'samples':len(records),'dataset_sha256':hashlib.sha256(contents).hexdigest(),'error':None,'output_directory':str(folder/'model')}
            self.runs[run_id]=run;self._write(run)
            self.executor.submit(self._work,run_id)
            return deepcopy(run)

    def _execute(self,run_id,arguments,stage):
        folder=self.root/run_id
        environment=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',LOKY_MAX_CPU_COUNT='1',PYTHONUNBUFFERED='1')
        with (folder/'training.log').open('ab') as log:
            with self.lock:
                if self.runs[run_id]['status']=='cancelling': return False
                self._update(run_id,status='running',stage=stage)
                process=subprocess.Popen([sys.executable,'-m',*arguments],cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.processes[run_id]=process
            began=time.monotonic()
            try:
                while True:
                    with self.lock:cancelled=self.runs[run_id]['status']=='cancelling'
                    timed_out=time.monotonic()-began>1800
                    if cancelled or timed_out:
                        process.terminate()
                        try:process.wait(timeout=5)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                        if timed_out:raise RuntimeError('Experiment stage exceeded the 30 minute time limit')
                        return False
                    try:code=process.wait(timeout=.25);break
                    except subprocess.TimeoutExpired:pass
                if code:raise RuntimeError(f'{stage} exited with code {code}. Check the experiment log.')
                return True
            finally:
                with self.lock:self.processes.pop(run_id,None)

    def _work(self,run_id):
        try:
            with self.lock:settings=dict(self.runs[run_id]['settings'])
            folder=self.root/run_id;kind=settings['model'];output=folder/'model'
            args=['ml.train' if kind=='baseline' else 'ml.train_temporal','--data',str(folder/'dataset.json'),'--exercise',settings['exercise'],'--output',str(output)]
            if kind=='baseline':args+=['--feature-set',settings['feature_set']]
            else:
                args+=['--model',kind,'--epochs',str(settings['epochs'])]
                if settings['augment']:args+=['--augment']
            if settings['export_onnx']:args+=['--export-onnx']
            success=self._execute(run_id,args,'training')
            if success and settings['export_onnx']:
                if not (output/f'{kind}.onnx').is_file():raise RuntimeError('ONNX export was requested but no artifact was produced. Check installed export dependencies.')
                success=self._execute(run_id,['ml.validate_onnx','--model-dir',str(output),'--data',str(folder/'dataset.json')],'validation')
            with self.lock:
                cancelled=self.runs[run_id]['status']=='cancelling' or not success
                self._update(run_id,status='cancelled' if cancelled else 'succeeded',stage='finished',finished_at=now())
        except Exception as error:
            with self.lock:
                cancelled=self.runs[run_id]['status']=='cancelling'
                self._update(run_id,status='cancelled' if cancelled else 'failed',finished_at=now(),error=None if cancelled else str(error))

    def cancel(self,run_id):
        with self.lock:
            if run_id not in self.runs:raise KeyError(run_id)
            if self.runs[run_id]['status'] not in ACTIVE:raise RuntimeError('Only active experiments can be cancelled')
            self._update(run_id,status='cancelling')
            return deepcopy(self.runs[run_id])

    def close(self):
        with self.lock:
            self.closed=True
            for run in list(self.runs.values()):
                if run['status'] in ACTIVE:self._update(run['id'],status='cancelling')
        self.executor.shutdown(wait=True)
