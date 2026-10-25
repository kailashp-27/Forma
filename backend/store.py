"""SQLite persistence. Camera frames are never written to disk."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .config import ROOT

def utcnow(): return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('COACH_DB_PATH', str(ROOT / 'data' / 'coach.sqlite3')))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY, exercise TEXT NOT NULL, participant_id TEXT NOT NULL,
              variation TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT);
            CREATE TABLE IF NOT EXISTS sets (
              id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
              exercise TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
              hold_seconds REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS reps (
              id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
              set_id TEXT NOT NULL REFERENCES sets(id), exercise TEXT NOT NULL,
              participant_id TEXT NOT NULL, view TEXT NOT NULL, label TEXT,
              created_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calibrations (
              id TEXT PRIMARY KEY, participant_id TEXT NOT NULL, exercise TEXT NOT NULL,
              variation TEXT NOT NULL, created_at TEXT NOT NULL, enabled INTEGER NOT NULL,
              settings TEXT NOT NULL);
            ''')
            if 'calibration' not in {r['name'] for r in db.execute('PRAGMA table_info(sessions)')}:
                db.execute('ALTER TABLE sessions ADD COLUMN calibration TEXT')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_session(self, exercise, participant_id, variation, calibration=None):
        record = dict(id=uuid.uuid4().hex, exercise=exercise, participant_id=participant_id,
                      variation=variation, started_at=utcnow(), finished_at=None)
        with self.connect() as db:
            db.execute('INSERT INTO sessions (id,exercise,participant_id,variation,started_at,finished_at,calibration) VALUES (:id,:exercise,:participant_id,:variation,:started_at,:finished_at,:calibration)', dict(record,calibration=json.dumps(calibration) if calibration else None))
        record['calibration'] = calibration
        return record

    def session(self, session_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone()
            if row is None: return None
            result = dict(row)
            result['calibration'] = json.loads(result['calibration']) if result['calibration'] else None
            result['sets'] = [dict(r) for r in db.execute('SELECT * FROM sets WHERE session_id=? ORDER BY started_at',(session_id,))]
            result['reps'] = self.records(session_id=session_id)
            result['total_reps'] = len(result['reps'])
            result['quality'] = round(sum(r['quality'] for r in result['reps'])/len(result['reps'])) if result['reps'] else None
            result['hold_seconds'] = sum(s['hold_seconds'] for s in result['sets'])
            return result

    def sessions(self):
        with self.connect() as db:
            rows = [dict(r) for r in db.execute('SELECT * FROM sessions ORDER BY started_at DESC LIMIT 200')]
            for row in rows:
                row['calibration'] = json.loads(row['calibration']) if row['calibration'] else None
                reps = db.execute('SELECT payload FROM reps WHERE session_id=?',(row['id'],)).fetchall()
                payloads = [json.loads(r['payload']) for r in reps]
                row['total_reps'] = row['reps'] = len(payloads)
                row['quality'] = round(sum(r['quality'] for r in payloads)/len(payloads)) if payloads else None
                row['hold_seconds'] = db.execute('SELECT COALESCE(SUM(hold_seconds),0) FROM sets WHERE session_id=?',(row['id'],)).fetchone()[0]
            return rows

    def finish_session(self, session_id):
        with self.connect() as db:
            db.execute('UPDATE sessions SET finished_at=COALESCE(finished_at,?) WHERE id=?',(utcnow(),session_id))
        return self.session(session_id)

    def create_set(self, session_id, exercise):
        set_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO sets (id,session_id,exercise,started_at) VALUES (?,?,?,?)',(set_id,session_id,exercise,utcnow()))
        return set_id

    def finish_set(self, set_id, hold_seconds=0):
        with self.connect() as db:
            db.execute('UPDATE sets SET finished_at=?,hold_seconds=? WHERE id=?',(utcnow(),hold_seconds,set_id))

    def add_rep(self, session_id, set_id, exercise, payload):
        record_id = uuid.uuid4().hex
        with self.connect() as db:
            session = db.execute('SELECT participant_id FROM sessions WHERE id=?',(session_id,)).fetchone()
            db.execute('INSERT INTO reps VALUES (?,?,?,?,?,?,?,?,?)',
                (record_id,session_id,set_id,exercise,session['participant_id'],'side',None,utcnow(),json.dumps(payload)))
        return record_id

    @staticmethod
    def _decode_record(row, include_keypoints=True):
        data=dict(row)
        payload=json.loads(data.pop('payload'))
        points=payload.get('keypoints',[])
        payload['frame_count']=len(points) if isinstance(points,list) else 0
        if not include_keypoints:
            payload.pop('keypoints',None)
            payload.pop('timestamps',None)
            payload.pop('frame_annotations',None)
        data.update(payload)
        return data

    def record(self, record_id):
        with self.connect() as db:
            row=db.execute('SELECT * FROM reps WHERE id=?',(record_id,)).fetchone()
            return self._decode_record(row) if row else None

    def records(self, session_id=None, labeled_only=False, exercise=None, participant_id=None, label_status='all', include_keypoints=True):
        clauses, args = [], []
        if session_id: clauses.append('session_id=?'); args.append(session_id)
        if exercise: clauses.append('exercise=?'); args.append(exercise)
        if participant_id is not None: clauses.append('participant_id=?'); args.append(participant_id)
        if labeled_only or label_status=='labeled': clauses.append('label IS NOT NULL')
        if label_status=='unlabeled': clauses.append('label IS NULL')
        query = 'SELECT * FROM reps' + (' WHERE '+' AND '.join(clauses) if clauses else '') + ' ORDER BY created_at'
        result = []
        with self.connect() as db:
            # Decode each cursor row and discard sequence arrays immediately in summary mode.
            for row in db.execute(query,args):
                result.append(self._decode_record(row,include_keypoints))
        return result

    def calibration_candidates(self, participant_id, exercise, variation, full=False):
        with self.connect() as db:
            rows=db.execute('''SELECT r.* FROM reps r JOIN sessions s ON s.id=r.session_id
                WHERE r.participant_id=? AND s.participant_id=? AND r.exercise=? AND s.variation=?
                AND r.label='good' AND r.view='side' AND s.finished_at IS NOT NULL
                ORDER BY r.created_at DESC LIMIT 200''',(participant_id,participant_id,exercise,variation)).fetchall()
            return [self._decode_record(row,include_keypoints=full) for row in rows]

    def training_records(self, exercise):
        with self.connect() as db:
            rows=db.execute('''SELECT r.*,s.finished_at AS session_finished_at FROM reps r
                JOIN sessions s ON s.id=r.session_id WHERE r.exercise=? ORDER BY r.created_at,r.id''',(exercise,)).fetchall()
            return [self._decode_record(row) for row in rows]

    def calibrations(self, participant_id, exercise, variation):
        with self.connect() as db:
            return [dict(dict(row),enabled=bool(row['enabled']),settings=json.loads(row['settings'])) for row in db.execute(
                'SELECT * FROM calibrations WHERE participant_id=? AND exercise=? AND variation=? ORDER BY created_at DESC,id',
                (participant_id,exercise,variation))]

    def save_calibration(self, participant_id, exercise, variation, settings):
        record=dict(id=uuid.uuid4().hex,participant_id=participant_id,exercise=exercise,variation=variation,
                    created_at=utcnow(),enabled=True,settings=settings)
        with self.connect() as db:
            db.execute('UPDATE calibrations SET enabled=0 WHERE participant_id=? AND exercise=? AND variation=?',(participant_id,exercise,variation))
            db.execute('INSERT INTO calibrations VALUES (?,?,?,?,?,?,?)',(record['id'],participant_id,exercise,variation,record['created_at'],1,json.dumps(settings)))
        return record

    def disable_calibration(self, calibration_id):
        with self.connect() as db:
            return db.execute('UPDATE calibrations SET enabled=0 WHERE id=?',(calibration_id,)).rowcount > 0

    def label(self, record_id, label, participant_id=None):
        with self.connect() as db:
            cursor=db.execute('UPDATE reps SET label=?, participant_id=COALESCE(?,participant_id) WHERE id=?',(label,participant_id,record_id))
            return cursor.rowcount > 0

    def analytics(self, participant_id):
        """Observed quality/tempo summaries; decline is a heuristic, not fatigue diagnosis."""
        def average(values):
            values=[float(v) for v in values if isinstance(v,(int,float))]
            return round(sum(values)/len(values),3) if values else None
        with self.connect() as db:
            sessions=[dict(r) for r in db.execute('SELECT * FROM sessions WHERE participant_id=? ORDER BY started_at,id',(participant_id,))]
            sets=[dict(r) for r in db.execute('''SELECT t.* FROM sets t JOIN sessions s ON s.id=t.session_id
                WHERE s.participant_id=? ORDER BY t.started_at,t.id''',(participant_id,))]
            rows=db.execute('''SELECT r.set_id,r.payload FROM reps r JOIN sessions s ON s.id=r.session_id
                WHERE s.participant_id=? ORDER BY r.created_at,r.id''',(participant_id,)).fetchall()
        by_set={}
        for row in rows: by_set.setdefault(row['set_id'],[]).append(json.loads(row['payload']))
        sets_by_session={}
        all_qualities=[]
        for item in sets:
            reps=by_set.get(item['id'],[])
            qualities=[r.get('quality') for r in reps]
            durations=[r.get('duration') for r in reps]
            observed=[(i,float(q)) for i,q in enumerate(qualities) if isinstance(q,(int,float))]
            slope=None
            if len(observed)>=2:
                mx=sum(i for i,q in observed)/len(observed)
                my=sum(q for i,q in observed)/len(observed)
                slope=round(sum((i-mx)*(q-my) for i,q in observed)/sum((i-mx)**2 for i,q in observed),3)
            item.update(total_reps=len(reps),quality=average(qualities),mean_rep_seconds=average(durations),
                quality_slope_per_rep=slope,
                fatigue_heuristic='insufficient_data' if slope is None else 'declining_quality' if slope < -2 else 'stable_or_improving',
                rep_qualities=qualities,rep_durations=durations)
            sets_by_session.setdefault(item['session_id'],[]).append(item)
            all_qualities.extend(qualities)
        for session in sessions:
            session['calibration']=json.loads(session['calibration']) if session['calibration'] else None
            session_sets=sets_by_session.get(session['id'],[])
            qualities=[q for item in session_sets for q in item['rep_qualities']]
            durations=[d for item in session_sets for d in item['rep_durations']]
            session.update(sets=session_sets,total_reps=sum(s['total_reps'] for s in session_sets),
                hold_seconds=round(sum(s['hold_seconds'] for s in session_sets),2),
                quality=average(qualities),mean_rep_seconds=average(durations))
        from .config import CONFIGS
        exercises=[]
        for exercise, config in CONFIGS.items():
            matching=[s for s in sessions if s['exercise']==exercise]
            qualities=[q for s in matching for item in s['sets'] for q in item['rep_qualities']]
            exercises.append(dict(exercise=exercise,name=config['name'],total_reps=sum(s['total_reps'] for s in matching),
                total_hold_seconds=round(sum(s['hold_seconds'] for s in matching),2),average_quality=average(qualities),
                quality_trend=[dict(session_id=s['id'],started_at=s['started_at'],quality=s['quality'],total_reps=s['total_reps'],hold_seconds=s['hold_seconds']) for s in matching]))
        return dict(participant_id=participant_id,summary=dict(sessions=len(sessions),total_reps=sum(s['total_reps'] for s in sessions),
            total_hold_seconds=round(sum(s['hold_seconds'] for s in sessions),2),average_quality=average(all_qualities)),
            exercises=exercises,sessions=sessions,note='Quality is a rule-based heuristic. Quality slope is an ordinary least-squares change in score per rep; slopes below -2 are labeled declining quality and do not establish physiological fatigue. Empty and single-rep sets have no slope. Unfinished sets include completed reps but hold time is saved when the set stops.')
