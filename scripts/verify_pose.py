"""Exercise the real local pose pipeline without opening a webcam."""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', action='store_true', help='Also check the official public Ultralytics bus photograph')
    args = parser.parse_args()
    import cv2
    import numpy as np
    from backend.pose import ESTIMATOR
    from backend.engine import CoachEngine
    from backend.config import CONFIGS
    report = {'purpose': 'Dependency and inference smoke test only; not exercise accuracy evidence'}
    blank = np.zeros((480,640,3), dtype=np.uint8)
    success, encoded = cv2.imencode('.jpg', blank)
    assert success
    began = time.perf_counter()
    points, width, height = ESTIMATOR.infer(encoded.tobytes())
    assert (width,height) == (640,480)
    assert points == [], 'A blank frame must not yield a person'
    report.update(model_loaded=ESTIMATOR.model is not None, blank_frame_passed=True,
                  initial_load_and_inference_ms=round((time.perf_counter()-began)*1000,1))
    if args.sample:
        import ultralytics
        sample = Path(ultralytics.__file__).parent / 'assets' / 'bus.jpg'
        if not sample.is_file():
            sample = ROOT / 'artifacts' / 'verification' / 'bus.jpg'
            sample.parent.mkdir(parents=True,exist_ok=True)
            if not sample.is_file():
                with urlopen('https://ultralytics.com/images/bus.jpg', timeout=30) as response:
                    sample.write_bytes(response.read())
        image = cv2.imread(str(sample))
        assert image is not None
        result = ESTIMATOR.model.predict(image, imgsz=640, verbose=False, device='cpu')[0]
        boxes = result.boxes.xyxy.cpu().numpy()
        report['public_sample_people_detected'] = len(boxes)
        assert len(boxes) > 0, 'Public fixture must contain detectable people'
        report['single_person_tracking_passed'] = False
        for box in boxes:
            x1,y1,x2,y2 = box.astype(int)
            crop = image[max(0,y1):min(image.shape[0],y2),max(0,x1):min(image.shape[1],x2)]
            if not crop.size:
                continue
            success,encoded = cv2.imencode('.jpg',crop)
            if not success:
                continue
            began = time.perf_counter()
            points,width,height = ESTIMATOR.infer(encoded.tobytes())
            if len(points) != 17:
                continue
            frame = CoachEngine(CONFIGS['squat']).process(points,width,height)
            if frame['tracking']:
                fixture = ROOT / 'artifacts' / 'verification' / 'single-person.jpg'
                fixture.parent.mkdir(parents=True,exist_ok=True)
                fixture.write_bytes(encoded.tobytes())
                report.update(single_person_tracking_passed=True, keypoint_count=len(points),
                              pose_frame_ms=round((time.perf_counter()-began)*1000,1),
                              fixture=str(fixture))
                break
        assert report['single_person_tracking_passed'], 'No public sample crop produced usable full-body tracking'
    output = ROOT / 'artifacts' / 'pose-smoke.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
