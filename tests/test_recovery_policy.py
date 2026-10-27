import unittest
from recovery_policy import RecoveryPolicy

class RecoveryPolicyTests(unittest.TestCase):
 def test_progress_resets_stall_without_false_refresh(self):
  p=RecoveryPolicy(soft=5,hard=10,max_attempts=2)
  self.assertEqual(p.observe('job',('stream',1),0),'observing')
  self.assertEqual(p.observe('job',('stream',2),9),'observing')
  self.assertEqual(p.observe('job',('stream',2),15),'warning')
  self.assertEqual(p.observe('job',('stream',2),20),'would_reload')
 def test_blockers_and_missing_heartbeat_do_not_refresh(self):
  p=RecoveryPolicy(soft=5,hard=10,max_attempts=2)
  p.observe('job',('idle',1),0)
  self.assertEqual(p.observe('job',('idle',1),20,blocked='captcha'),'blocked')
  self.assertEqual(p.observe('job',('idle',1),21,heartbeat=False),'disconnected')
 def test_attempt_limit_and_reset_after_real_progress(self):
  p=RecoveryPolicy(soft=5,hard=10,max_attempts=2)
  p.observe('job',('idle',1),0)
  self.assertEqual(p.observe('job',('idle',1),10),'would_reload')
  self.assertEqual(p.observe('job',('idle',1),20),'would_reload')
  self.assertEqual(p.observe('job',('idle',1),30),'failed')
  self.assertEqual(p.observe('job',('idle',2),31),'observing')
  self.assertEqual(p.observe('job',('idle',2),41),'would_reload')
 def test_resume_after_disconnect_or_block_does_not_trigger_immediately(self):
  p=RecoveryPolicy(soft=5,hard=10,max_attempts=2)
  p.observe('job',('idle',1),0)
  self.assertEqual(p.observe('job',('idle',1),20,heartbeat=False),'disconnected')
  self.assertEqual(p.observe('job',('idle',1),21),'observing')
  self.assertEqual(p.observe('job',('idle',1),40,blocked='captcha'),'blocked')
  self.assertEqual(p.observe('job',('idle',1),41),'observing')
