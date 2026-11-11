import os
import tempfile
import unittest
from pathlib import Path

import test_guard
from queue_manager import QueueManager


class TestGuardTests(unittest.TestCase):
    def test_this_run_is_recognised_as_a_test_with_a_private_home(self):
        self.assertTrue(test_guard.under_test())
        test_guard.isolate()
        home = Path(os.environ['AI_MANAGER_HOME']).resolve()
        self.assertNotIn(home, test_guard.production_paths())

    def test_real_home_and_projects_root_are_refused(self):
        for path in (Path.home() / '.ai_manager', Path.home() / 'VIDEO_PROJECTS'):
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, 'TEST_WOULD_USE_PRODUCTION_DATA'):
                QueueManager(path)

    def test_a_temporary_root_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            q = QueueManager(td)
            q.close()

    def test_server_default_root_is_inside_the_test_home(self):
        import server
        self.assertNotIn(Path(server.config()['root']).resolve(), test_guard.production_paths())
        self.assertNotIn(server.BASE.resolve(), test_guard.production_paths())


if __name__ == '__main__':
    unittest.main()
