import unittest
import numpy as np
from ml.preprocess import resample, temporal_features, grouped_split, augment


def pose():
    p = np.zeros((10, 17, 3), dtype=np.float32)
    p[:, :, 2] = .9
    p[:, :, 0] = np.linspace(.2, .8, 17)
    p[:, :, 1] = np.linspace(.1, .9, 17)
    return p


class PreprocessingTests(unittest.TestCase):
    def test_resampling_retains_endpoints(self):
        data = np.arange(9).reshape(3,3)
        result = resample(data)
        self.assertEqual(result.shape, (32,3))
        np.testing.assert_array_equal(result[[0,-1]], data[[0,-1]])

    def test_groups_do_not_leak(self):
        groups = np.array(["a"]*4+["b"]*4+["c"]*4+["d"]*4)
        train, test = grouped_split(groups)
        self.assertFalse(set(groups[train]) & set(groups[test]))
        self.assertEqual(len(train)+len(test), len(groups))

    def test_small_participant_count_rejected(self):
        with self.assertRaises(ValueError):
            grouped_split(["a", "b"])

    def test_translation_scale_invariance(self):
        first = pose()
        second = first.copy()
        second[:,:,:2] = second[:,:,:2]*2 + .2
        np.testing.assert_allclose(temporal_features(first), temporal_features(second), atol=.0002)

    def test_missing_torso_rejected(self):
        points = pose()
        points[:,5,2] = 0
        with self.assertRaises(ValueError):
            temporal_features(points)

    def test_augmentation_preserves_shape(self):
        result = augment(pose(), np.random.default_rng(42))
        self.assertEqual(result.shape, (10,17,3))
        self.assertTrue(np.isfinite(result).all())

    def test_aspect_ratio_corrects_normalized_coordinates(self):
        first = pose()
        wider_image = first.copy()
        wider_image[:,:,0] /= 2
        np.testing.assert_allclose(temporal_features(first, aspect_ratio=1), temporal_features(wider_image, aspect_ratio=2), atol=.0002)

    def test_invalid_aspect_ratio_rejected(self):
        with self.assertRaises(ValueError):
            temporal_features(pose(), aspect_ratio=0)

    def test_time_order_rejected(self):
        with self.assertRaises(ValueError):
            resample(np.ones((3,2)), timestamps=[0,1,.5])


if __name__ == "__main__":
    unittest.main()
