"""Synthetic fixtures test code paths only; never presented as model evidence."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from ml.train import main, metrics


class TrainingTests(unittest.TestCase):
    def test_unknown_rule_predictions_are_not_hidden(self):
        result = metrics(["good", "good"], ["good", "abstain"], ["good"])
        self.assertEqual(result["unknown_prediction_count"], 1)
        self.assertEqual(sum(map(sum, result["confusion_matrix"])), 2)
        self.assertLess(result["macro_f1"], 1)

    def test_training_report_holds_out_people(self):
        points = np.zeros((8,17,3),dtype=float)
        points[:,:,0] = np.linspace(.2,.8,17)
        points[:,:,1] = np.linspace(.1,.9,17)
        points[:,:,2] = .9
        records = []
        for person in ["a", "b", "c", "d"]:
            for label in ["good", "depth"]:
                records.append({"participant_id":person,"exercise":"squat","label":label,"keypoints":points.tolist(),"rule_label":label,"aspect_ratio":4/3})
        with tempfile.TemporaryDirectory(prefix="training-smoke-", dir=Path(__file__).resolve().parent) as directory:
            source = Path(directory)/"reps.json"
            source.write_text(json.dumps(records), encoding="utf-8")
            output = Path(directory)/"model"
            with patch("sys.argv", ["train", "--data", str(source), "--exercise", "squat", "--output",str(output)]), contextlib.redirect_stdout(io.StringIO()):
                main()
            result = json.loads((output/"evaluation.json").read_text(encoding="utf-8"))
            self.assertFalse(set(result["train_people"]) & set(result["test_people"]))
            self.assertEqual(len(result["leave_one_person_out"]), 4)
            self.assertEqual(result["rule_baseline"]["macro_f1"], 1)
            self.assertTrue((output/"baseline.joblib").exists())


if __name__ == "__main__":
    unittest.main()
