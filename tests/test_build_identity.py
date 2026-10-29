import unittest
from pathlib import Path
from automation_agent.build_identity import identity,fingerprint,VERSION
class IdentityTests(unittest.TestCase):
 def test_actual_pid_version_and_source_are_reported(self):
  import os
  data=identity();self.assertEqual(data['pid'],os.getpid());self.assertEqual(data['version'],VERSION)
  self.assertTrue(Path(data['source_file']).is_file());self.assertEqual(data['source_sha256'],fingerprint())
  self.assertIn('pywin32_version',data);self.assertIn('commit',data)
