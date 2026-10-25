"""Verify real local setup inference without requesting a webcam or saving a session."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse


async def check(base, image):
    import httpx
    import websockets
    async with httpx.AsyncClient(base_url=base, timeout=15, trust_env=False) as client:
        before = await client.get('/api/sessions')
        before.raise_for_status()
        async with websockets.connect(base.replace('http://', 'ws://', 1) + '/ws/coach', origin=base, open_timeout=15) as socket:
            await socket.send(json.dumps({'type': 'setup', 'exercise': 'squat'}))
            started = json.loads(await asyncio.wait_for(socket.recv(), 15))
            assert started['type'] == 'started' and started['setup'] and started['set_id'] is None, started
            await socket.send(image.read_bytes())
            frame = json.loads(await asyncio.wait_for(socket.recv(), 90))
            assert frame['type'] == 'frame' and frame['setup'], frame
            assert frame['tracking'] and len(frame['keypoints']) == 17, frame
            assert frame['reps'] == 0 and frame['hold_seconds'] == 0 and frame['quality'] is None, frame
            assert 'rep_completed' not in frame, frame
            await socket.send(json.dumps({'type': 'stop'}))
            assert json.loads(await asyncio.wait_for(socket.recv(), 15))['type'] == 'stopped'
        after = await client.get('/api/sessions')
        after.raise_for_status()
        assert before.json() == after.json(), 'Session data changed during this setup check'
        print(json.dumps({'setup_tracking': True, 'keypoints': 17, 'session_data_unchanged': True,
                          'server_latency_ms': frame['latency_ms'], 'note': 'Image fixture only; not physical webcam acceptance'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8765')
    parser.add_argument('--image', required=True, type=Path)
    args = parser.parse_args()
    base = args.url.rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1'} or parsed.path:
        parser.error('Use the local HTTP app origin only')
    asyncio.run(check(base, args.image))
