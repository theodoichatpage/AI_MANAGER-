import unittest
from extension_monitor import ExtensionMonitor

class IdentityTests(unittest.TestCase):
 def setUp(self): self.monitor=ExtensionMonitor()
 def signal(self, tab=1, job='job1', stamp=100000):
  return {'pairCode':'pair1','activeJobId':job,'chatTabId':tab,'conversationUrl':'https://chatgpt.com/c/abc','lastHeartbeatAt':stamp,'version':'0.4.22','identityVersion':1}
 def test_missing_fields_is_legacy(self):
  self.monitor.receive('pair1',{'pairCode':'pair1','version':'0.4.21'},100)
  self.assertEqual(self.monitor.snapshot('pair1',100)['status'],'legacy')
 def test_change_tab_same_identity(self):
  self.monitor.receive('pair1',self.signal(),100)
  self.monitor.receive('pair1',self.signal(2,stamp=101000),101)
  s=self.monitor.snapshot('pair1',101)
  self.assertEqual((s['status'],s['chatTabId'],s['activeJobId']),('responding',2,'job1'))
 def test_wrong_pair_is_ignored(self):
  self.assertFalse(self.monitor.receive('wrong',self.signal(),100))
 def test_wrong_job_is_ignored(self):
  self.assertFalse(self.monitor.receive('pair1',self.signal(job='other'),100,expected_job='job1'))
 def test_stale_heartbeat_and_extension(self):
  self.monitor.receive('pair1',self.signal(),100)
  self.assertEqual(self.monitor.snapshot('pair1',160)['status'],'heartbeat_stopped')
  self.assertEqual(self.monitor.snapshot('pair1',200)['status'],'extension_lost')
 def test_missing_job_does_not_claim_active_task(self):
  sig=self.signal(job=None)
  self.monitor.receive('pair1',sig,100)
  self.assertIsNone(self.monitor.snapshot('pair1',100)['activeJobId'])
