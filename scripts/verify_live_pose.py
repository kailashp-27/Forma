"""Send a test image through the local live-coach socket; remove only the created fixture session."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


async def check(base, image):
    import httpx
    import websockets
    from backend.store import Store
    participant = '__pose_verification_' + uuid4().hex
    session_id = None
    report = {'purpose':'Local transport and inference smoke test on a test image, not exercise accuracy'}
    with httpx.Client(base_url=base,timeout=15,trust_env=False) as client:
        before = client.get('/api/health'); before.raise_for_status()
        assert before.json()['ultralytics_installed'] and before.json()['model_weights_present']
        try:
            response = client.post('/api/sessions',json={'exercise':'squat','participant_id':participant})
            response.raise_for_status(); session_id=response.json()['id']
            socket_url = base.replace('http://','ws://',1) + '/ws/coach'
            async with websockets.connect(socket_url,origin=base,open_timeout=10,max_size=2_000_000) as socket:
                await socket.send(json.dumps({'type':'start','exercise':'squat','session_id':session_id}))
                started=json.loads(await asyncio.wait_for(socket.recv(),15))
                assert started['type']=='started',started
                began=time.perf_counter()
                await socket.send(image.read_bytes())
                frame=json.loads(await asyncio.wait_for(socket.recv(),90))
                assert frame['type']=='frame',frame
                assert frame['tracking'] and len(frame['keypoints'])==17,frame
                report.update(tracking=True,keypoint_count=len(frame['keypoints']),
                              roundtrip_ms=round((time.perf_counter()-began)*1000,1),
                              server_latency_ms=frame['latency_ms'])
                await socket.send(json.dumps({'type':'stop'}))
                assert json.loads(await asyncio.wait_for(socket.recv(),10))['type']=='stopped'
            response=client.post(f'/api/sessions/{session_id}/finish'); response.raise_for_status()
            after=client.get('/api/health'); after.raise_for_status()
            report['pose_model_loaded']=after.json()['pose_model_loaded']
            assert report['pose_model_loaded']
        finally:
            if session_id:
                store=Store()
                with store.connect() as database:
                    row=database.execute('SELECT participant_id FROM sessions WHERE id=?',(session_id,)).fetchone()
                    if row and row['participant_id']==participant:
                        database.execute('DELETE FROM reps WHERE session_id=?',(session_id,))
                        database.execute('DELETE FROM sets WHERE session_id=?',(session_id,))
                        database.execute('DELETE FROM sessions WHERE id=?',(session_id,))
                        report['fixture_cleanup']='removed only this verification session'
    output=ROOT/'artifacts'/'live-pose-smoke.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://localhost:8765')
    parser.add_argument('--image',required=True,type=Path)
    args=parser.parse_args()
    url=args.url.rstrip('/')
    parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in {'localhost','127.0.0.1'} or parsed.path:
        parser.error('Use the local HTTP app origin only')
    asyncio.run(check(url,args.image))


if __name__=='__main__':
    main()
