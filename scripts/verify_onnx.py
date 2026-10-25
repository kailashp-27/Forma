"""Test ONNX conversion on disposable synthetic fixtures, not real model accuracy."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import numpy as np
    from ml.train import main as baseline_train
    from ml.train_temporal import main as temporal_train
    from ml.validate_onnx import main as validate
    from ml.inference import OnnxFormClassifier
    records=[]
    for person in ['test-a','test-b','test-c','test-d']:
        for label in ['good','depth']:
            points=np.zeros((8,17,3))
            points[:,:,0]=np.linspace(.2,.8,17)
            points[:,:,1]=np.linspace(.1,.9,17)
            points[:,:,2]=.9
            if label=='depth':
                points[:,13:15,0]+=.04
            records.append(dict(participant_id=person,exercise='squat',label=label,keypoints=points.tolist(),rule_label=label))
    report={'purpose':'Conversion/code-path smoke tests on synthetic fixtures only; no accuracy claim','models':{}}
    (ROOT/'artifacts').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='onnx-smoke-',dir=ROOT/'artifacts') as folder:
        folder=Path(folder); source=folder/'reps.json'
        source.write_text(json.dumps(records),encoding='utf-8')
        for kind in ['baseline','cnn','gru']:
            began=time.perf_counter(); output=folder/kind
            argv=['verify','--data',str(source),'--exercise','squat','--output',str(output),'--export-onnx']
            if kind!='baseline':
                argv += ['--model',kind,'--epochs','1']
            with patch('sys.argv',argv), contextlib.redirect_stdout(io.StringIO()):
                (baseline_train if kind=='baseline' else temporal_train)()
            with patch('sys.argv',['validate','--model-dir',str(output),'--data',str(source)]), contextlib.redirect_stdout(io.StringIO()):
                validate()
            validation=json.loads((output/'onnx-validation.json').read_text(encoding='utf-8'))
            assert validation['status']=='passed'
            prediction=OnnxFormClassifier(output).predict_record(records[0])
            report['models'][kind]=dict(status='passed',samples=validation['samples'],
                max_probability_error=validation['max_probability_error'],
                adapter_label_valid=prediction['label'] in {'good','depth'},
                seconds=round(time.perf_counter()-began,2))
            print(f'{kind}: ONNX export, Python parity and live adapter PASS',flush=True)
    (ROOT/'artifacts'/'onnx-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
