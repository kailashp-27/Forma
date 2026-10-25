"""Local HTTP and WebSocket application: python -m uvicorn backend.app:app."""
import asyncio
import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from .config import CONFIGS, ROOT
from .engine import CoachEngine, demo_pose
from .pose import ESTIMATOR
from .store import Store
from .runtime import ALLOWED_ORIGINS
from .calibration import propose, calibrated_config
from .readiness import prepare_dataset
from .training import TrainingRuns

logger=logging.getLogger(__name__)
app=FastAPI(title='Forma Movement Coach',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=sorted(ALLOWED_ORIGINS),allow_methods=['GET','POST','PATCH'],allow_headers=['Content-Type'])
store=Store()
training_runs=TrainingRuns(os.getenv('COACH_TRAINING_DIR',str(store.path.parent/'experiments')))
app.add_event_handler('shutdown',training_runs.close)
active_sessions=set()
form_classifier=None
form_classifier_error=None
try:
    form_min_confidence=float(os.getenv('COACH_FORM_MIN_CONFIDENCE','0.8'))
    if not 0 <= form_min_confidence <= 1: raise ValueError('Confidence must be between zero and one')
except ValueError:
    form_min_confidence=0.8
model_directory=os.getenv('COACH_FORM_MODEL_DIR')
if model_directory:
    try:
        from ml.inference import OnnxFormClassifier
        form_classifier=OnnxFormClassifier(model_directory)
    except Exception as error:
        form_classifier_error=f'{type(error).__name__}: {error}'
        logger.warning('Optional form model unavailable; using rules: %s',form_classifier_error)

MODEL_CUES={'good':'Good rep. Keep that control','depth':'Use a fuller controlled range of motion',
    'torso_lean':'Keep your chest lifted','body_alignment':'Keep shoulders hips and ankles in one line',
    'torso_swing':'Reduce body swing and move with control'}

def classify_rep(rep, exercise):
    """A trained model adds an experimental label; rule score remains explicit."""
    if form_classifier is None: return None
    try:
        prediction=form_classifier.predict_record(dict(rep,exercise=exercise))
        prediction['accepted']=prediction['confidence']>=form_min_confidence and prediction['label'] in MODEL_CUES
        return prediction
    except Exception as error:
        logger.warning('Form model prediction failed; using rules: %s',error)
        return {'accepted':False,'experimental':True,'error':'Classifier unavailable for this rep'}

class SessionCreate(BaseModel):
    exercise: Literal['squat','pushup','plank','pullup']='squat'
    participant_id: str=Field(default='local-user',min_length=1,max_length=80)
    variation: str=Field(default='',max_length=80)
    view: Literal['side']='side'

    @model_validator(mode='after')
    def known_variation(self):
        if self.variation and self.variation not in CONFIGS[self.exercise]['ladder']:
            raise ValueError('Variation must match this exercise\'s progression ladder')
        return self

class LabelUpdate(BaseModel):
    label: Literal['good','depth','torso_lean','body_alignment','torso_swing','unusable','unobservable'] | None=None
    participant_id: str | None=Field(default=None,min_length=1,max_length=80)

class CalibrationCreate(SessionCreate):
    variation: str=Field(min_length=1,max_length=80)
    record_ids: list[str]=Field(min_length=3,max_length=20)

class TrainingCreate(BaseModel):
    model_config={'extra':'forbid'}
    exercise: Literal['squat','pushup','pullup']
    model: Literal['baseline','cnn','gru']='baseline'
    feature_set: Literal['full','angles','keypoints']='full'
    epochs: int=Field(default=40,ge=1,le=200)
    augment: bool=False
    export_onnx: bool=False

    @model_validator(mode='after')
    def supported_features(self):
        if self.model!='baseline' and self.feature_set!='full':raise ValueError('Temporal models use full features')
        return self

@app.get('/api/dataset/readiness')
def dataset_readiness(exercise:Literal['squat','pushup','plank','pullup']='squat'):
    return prepare_dataset(store.training_records(exercise),exercise)[1]

@app.get('/api/training/runs')
def list_training_runs():
    return training_runs.list()

@app.post('/api/training/runs',status_code=202)
def start_training(body:TrainingCreate):
    if active_sessions:raise HTTPException(409,'End the live camera set before starting training')
    records,report=prepare_dataset(store.training_records(body.exercise),body.exercise)
    if not report['training_ready']:raise HTTPException(422,{'message':'Dataset is not ready for training','blockers':report['blockers']})
    if active_sessions:raise HTTPException(409,'End the live camera set before starting training')
    try:return training_runs.create(body.model_dump(),records,report)
    except RuntimeError as error:raise HTTPException(409,str(error)) from error

@app.get('/api/training/runs/{run_id}')
def training_run(run_id:str):
    result=training_runs.get(run_id)
    if result is None:raise HTTPException(404,'Experiment not found')
    return result

@app.get('/api/training/runs/{run_id}/report')
def training_report(run_id:str):
    result=training_run(run_id)
    result.pop('log_tail',None)
    return JSONResponse(result,headers={'Content-Disposition':f'attachment; filename="forma-experiment-{run_id}.json"'})

@app.post('/api/training/runs/{run_id}/cancel')
def cancel_training(run_id:str):
    try:return training_runs.cancel(run_id)
    except KeyError as error:raise HTTPException(404,'Experiment not found') from error
    except RuntimeError as error:raise HTTPException(409,str(error)) from error

def calibration_evidence(body):
    rows={r['id']:r for r in store.calibration_candidates(body.participant_id,body.exercise,body.variation,full=True)}
    if len(set(body.record_ids))!=len(body.record_ids) or any(i not in rows for i in body.record_ids):
        raise HTTPException(422,'Select distinct good-labeled reps from completed sessions for this participant and variation')
    try:
        return propose(CONFIGS[body.exercise],[rows[i] for i in body.record_ids])
    except (ValueError,TypeError,KeyError) as error:
        raise HTTPException(422,str(error)) from error

@app.get('/api/calibrations')
def calibrations(participant_id:str,exercise:Literal['squat','pushup','plank','pullup'],variation:str):
    return {'profiles':store.calibrations(participant_id,exercise,variation),
            'candidates':store.calibration_candidates(participant_id,exercise,variation)}

@app.post('/api/calibrations/preview')
def preview_calibration(body:CalibrationCreate):
    return calibration_evidence(body)

@app.post('/api/calibrations',status_code=201)
def save_calibration(body:CalibrationCreate):
    return store.save_calibration(body.participant_id,body.exercise,body.variation,calibration_evidence(body))

@app.post('/api/calibrations/{calibration_id}/disable')
def disable_calibration(calibration_id:str):
    if not store.disable_calibration(calibration_id): raise HTTPException(404,'Calibration not found')
    return {'id':calibration_id,'enabled':False}

@app.get('/api/health')
def health():
    import importlib.util
    return {'status':'ok','pose_model_loaded':ESTIMATOR.model is not None,'model':'yolo11n-pose',
            'training_active':training_runs.has_active(),
            'classifier':'rules+experimental_onnx' if form_classifier else 'rules_only',
            'classifier_error':form_classifier_error,'classifier_confidence_threshold':form_min_confidence,
            'ultralytics_installed':importlib.util.find_spec('ultralytics') is not None,
            'model_weights_present':(ROOT/'models'/'yolo11n-pose.pt').exists(),
            'privacy':'Frames are processed locally and never stored; keypoints are stored for completed repetitions.'}

@app.get('/api/exercises')
def exercises(): return list(CONFIGS.values())

@app.get('/api/sessions')
def sessions(): return store.sessions()

@app.post('/api/sessions',status_code=201)
def create_session(body:SessionCreate):
    variation=body.variation or CONFIGS[body.exercise]['ladder'][1]
    profiles=store.calibrations(body.participant_id,body.exercise,variation)
    profile=next((p for p in profiles if p['enabled']),None)
    return store.create_session(body.exercise,body.participant_id,variation,calibration=profile)

@app.get('/api/sessions/{session_id}')
def session(session_id:str):
    value=store.session(session_id)
    if value is None: raise HTTPException(404,'Session not found')
    return value

@app.post('/api/sessions/{session_id}/finish')
def finish(session_id:str):
    if session_id in active_sessions: raise HTTPException(409,'Stop the live set before finishing this session')
    session(session_id)
    return store.finish_session(session_id)

@app.get('/api/records')
def records(exercise:Literal['squat','pushup','plank','pullup'] | None=None,
            participant_id:str | None=None,
            label_status:Literal['all','labeled','unlabeled']='all',
            include_keypoints:bool=True):
    return store.records(exercise=exercise,participant_id=participant_id,label_status=label_status,include_keypoints=include_keypoints)

@app.get('/api/records/{record_id}')
def record(record_id:str):
    value=store.record(record_id)
    if value is None: raise HTTPException(404,'Record not found')
    return value

@app.patch('/api/records/{record_id}/label')
def label_record(record_id:str,body:LabelUpdate):
    label=body.label.strip() if body.label else None
    if not store.label(record_id,label or None,body.participant_id): raise HTTPException(404,'Record not found')
    return {'id':record_id,'label':label}

@app.get('/api/dataset/export')
def dataset(exercise:Literal['squat','pushup','plank','pullup'] | None=None,
            participant_id:str | None=None,
            label_status:Literal['all','labeled','unlabeled']='labeled'):
    return store.records(exercise=exercise,participant_id=participant_id,label_status=label_status)

@app.get('/api/analytics')
def analytics(participant_id:str='local-user'):
    return store.analytics(participant_id)

@app.get('/api/progression')
def progression(participant_id: str='local-user'):
    result=[]
    with store.connect() as db:
        for exercise, config in CONFIGS.items():
            sets=db.execute('''SELECT t.*,s.variation FROM sets t JOIN sessions s ON s.id=t.session_id
                WHERE t.exercise=? AND s.participant_id=? AND t.finished_at IS NOT NULL ORDER BY t.started_at DESC LIMIT 3''',(exercise,participant_id)).fetchall()
            qualified=0
            for item in sets:
                payloads=[json.loads(row[0]) for row in db.execute('SELECT payload FROM reps WHERE set_id=?',(item['id'],))]
                if exercise=='plank':
                    ok=item['hold_seconds']>=config['target_hold_seconds']
                else:
                    ok=len(payloads)>=config['target_reps'] and all(p['quality']>=85 for p in payloads)
                qualified+=int(ok)
            current=sets[0]['variation'] if sets else config['ladder'][1]
            index=config['ladder'].index(current) if current in config['ladder'] else 1
            ready=qualified>=3 and len({s['variation'] for s in sets})==1
            result.append({'exercise':exercise,'name':config['name'],'ladder':config['ladder'],
                'current_variation':current,'next_variation':config['ladder'][min(index+1,len(config['ladder'])-1)],
                'qualifying_sets':qualified,'required_sets':3,'ready':ready,
                'rule':'3 completed sets at the same variation, meeting the target with every rep scoring at least 85. Plank uses aligned hold time.',
                'note':'Readiness is a coaching suggestion; scores are heuristic and not validated measurements.'})
    return result

@app.websocket('/ws/coach')
async def coach(socket:WebSocket):
    origin=socket.headers.get('origin')
    if origin and origin not in ALLOWED_ORIGINS:
        await socket.close(code=1008); return
    await socket.accept()
    engine=None
    current_session=set_id=None
    demo=False
    setup=False
    demo_start=time.monotonic()
    frame_times=deque(maxlen=30)

    def stop_set():
        nonlocal current_session,set_id,engine
        if set_id:
            store.finish_set(set_id,engine.hold_seconds if engine else 0)
        if current_session: active_sessions.discard(current_session)
        current_session=set_id=None

    try:
        while True:
            message=await socket.receive()
            if message['type']=='websocket.disconnect': break
            command=None
            if message.get('text') is not None:
                try: command=json.loads(message['text'])
                except (ValueError,TypeError):
                    await socket.send_json({'type':'error','message':'Send a valid JSON command'}); continue
                if not isinstance(command,dict):
                    await socket.send_json({'type':'error','message':'Command must be an object'}); continue
                kind=command.get('type')
                if kind=='stop':
                    stop_set(); engine=None
                    await socket.send_json({'type':'stopped'}); continue
                if kind in ('start','demo','setup'):
                    if kind!='demo' and training_runs.has_active():
                        await socket.send_json({'type':'error','message':'Wait for the training experiment to finish, or cancel it before using the camera'}); continue
                    stop_set()
                    engine=None
                    exercise=command.get('exercise','squat')
                    if not isinstance(exercise,str) or exercise not in CONFIGS:
                        await socket.send_json({'type':'error','message':'Unknown exercise'}); continue
                    if command.get('view','side')!='side':
                        await socket.send_json({'type':'error','message':'Current exercise configs support side view only'}); continue
                    demo=kind=='demo'
                    setup=kind=='setup'
                    requested=command.get('session_id')
                    config=CONFIGS[exercise]
                    if not demo and not setup:
                        record=store.session(requested) if isinstance(requested,str) else None
                        if not record or record['finished_at'] or record['exercise']!=exercise:
                            await socket.send_json({'type':'error','message':'Create an open session matching this exercise first'}); continue
                        if requested in active_sessions:
                            await socket.send_json({'type':'error','message':'This session already has a live set'}); continue
                        try:
                            config=calibrated_config(config,record.get('calibration'))
                        except (ValueError,KeyError,TypeError):
                            await socket.send_json({'type':'error','message':'Session calibration is incompatible; disable the profile and create a new session'}); continue
                        current_session=requested
                        active_sessions.add(current_session)
                        set_id=store.create_set(current_session,exercise)
                    engine=CoachEngine(config); demo_start=time.monotonic()
                    frame_times.clear()
                    await socket.send_json({'type':'started','exercise':exercise,'demo':demo,'setup':setup,'set_id':set_id,'calibration_id':config.get('calibration_id')}); continue
                if kind!='tick':
                    await socket.send_json({'type':'error','message':'Unknown command'}); continue
            if engine is None:
                await socket.send_json({'type':'error','message':'Start a session before sending frames'}); continue
            started=time.perf_counter()
            try:
                if demo:
                    elapsed=time.monotonic()-demo_start
                    points=demo_pose(engine.config['id'],elapsed)
                    width=height=640
                else:
                    jpeg=message.get('bytes')
                    if jpeg is None: continue
                    if len(jpeg)>2_000_000:
                        await socket.send_json({'type':'error','message':'Camera frames must be under 2 MB'}); continue
                    points,width,height=await asyncio.to_thread(ESTIMATOR.infer,jpeg)
                response=engine.process(points,width,height)
                if setup:
                    response.pop('rep_completed',None)
                    response.update(reps=0,hold_seconds=0,quality=None,flags=[],state='camera_setup',cue='Position your full body side-on before starting the set')
                if response.get('rep_completed'):
                    rep=response['rep_completed']
                    if form_classifier is not None and not demo:
                        prediction=await asyncio.to_thread(classify_rep,rep,engine.config['id'])
                        if prediction:
                            rep['ml_prediction']=prediction
                            if prediction.get('accepted') and not rep['flags']:
                                response['cue']=MODEL_CUES[prediction['label']]
                                response['cue_source']='experimental_ml'
                    if current_session:
                        rep['id']=store.add_rep(current_session,set_id,engine.config['id'],rep)
                    # Dataset sequences remain in local SQLite, not every UI message.
                    response['rep_completed']={k:v for k,v in rep.items() if k not in ('keypoints','timestamps','frame_annotations')}
                latency=(time.perf_counter()-started)*1000
                frame_times.append(time.perf_counter())
                fps=(len(frame_times)-1)/(frame_times[-1]-frame_times[0]) if len(frame_times)>1 else 0
                response.update(width=width,height=height,latency_ms=round(latency,1),fps=round(fps,1),demo=demo,setup=setup)
                await socket.send_json(response)
            except ImportError:
                await socket.send_json({'type':'error','message':'Pose dependencies are not installed. Run the setup script, or use demo mode.'})
            except Exception as error:
                logger.exception('Pose frame processing failed')
                await socket.send_json({'type':'error','message':f'Pose processing failed ({type(error).__name__}). Check the backend terminal and model download.'})
    except WebSocketDisconnect:
        pass
    finally:
        stop_set()

# Built UI shares the local origin. Development uses Vite proxy instead.
if (ROOT/'frontend'/'dist').is_dir():
    app.mount('/',StaticFiles(directory=ROOT/'frontend'/'dist',html=True),name='frontend')
