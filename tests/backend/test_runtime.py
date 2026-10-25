import os
import unittest
from unittest.mock import patch
from backend.runtime import configured_port
from backend import app as module
from tests.backend.test_api import FakeSocket, run_inline


class RuntimeTests(unittest.TestCase):
    def test_configurable_local_port_and_invalid_values(self):
        with patch.dict(os.environ, {'COACH_PORT':'8787'}):
            self.assertEqual(configured_port(),8787)
        for value in ['invalid','0','80','65536']:
            with self.subTest(value=value), patch.dict(os.environ, {'COACH_PORT':value}):
                with self.assertRaises(ValueError):
                    configured_port()

    def test_new_default_origin_accepts_synthetic_coach_socket(self):
        socket=FakeSocket([{'type':'demo','exercise':'squat'},{'type':'tick'},{'type':'stop'}])
        socket.headers={'origin':'http://localhost:8765'}
        run_inline(module.coach(socket))
        self.assertEqual(socket.messages[0]['type'],'started')
        self.assertTrue(socket.messages[1]['demo'])
        self.assertEqual(socket.messages[-1]['type'],'stopped')
