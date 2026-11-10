import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from automation_agent.studio_workflow import atomic


class AtomicCheckpointTests(unittest.TestCase):
    def test_checkpoint_round_trip_and_no_temp_files(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "analysis" / "checkpoint.json"
            atomic(target, {"text": "Tiếng Việt"})
            self.assertEqual(json.loads(target.read_text(encoding="utf8")), {"text": "Tiếng Việt"})
            self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_permission_error_does_not_leave_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "checkpoint.json"
            with patch("automation_agent.studio_workflow.fsutil.replace_retry",
                       side_effect=PermissionError(13, "Access denied")):
                with self.assertRaises(PermissionError):
                    atomic(target, {"value": 1})
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_parallel_writers_do_not_share_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "checkpoint.json"
            errors = []

            def write(index):
                try:
                    atomic(target, {"index": index})
                except Exception as exc:
                    errors.append(exc)

            workers = [threading.Thread(target=write, args=(index,)) for index in range(40)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            self.assertFalse(errors)
            self.assertIn("index", json.loads(target.read_text(encoding="utf8")))
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
