import json, tempfile, unittest
from pathlib import Path
from recovery_monitor import RecoveryMonitor

class RecoveryMonitorTest(unittest.TestCase):
 def test_rejects_mismatched_session_without_writing(self):
  with tempfile.TemporaryDirectory() as d:
   m=RecoveryMonitor(Path(d),soft=5,hard=10)
   self.assertFalse(m.receive('correct',{'pairCode':'wrong','activeJobId':'j','tabAlive':True,'fp':{}},0))
   self.assertFalse((Path(d)/'recovery.log').exists())
 def test_dry_run_logs_warning_and_never_returns_commands(self):
  with tempfile.TemporaryDirectory() as d:
   m=RecoveryMonitor(Path(d),soft=5,hard=10)
   signal={'pairCode':'correct','activeJobId':'j','tabAlive':True,'fp':{'generating':False,'msgCount':2,'lastLen':30,'captcha':False,'jobId':'j'}}
   self.assertEqual(m.receive('correct',signal,0),[])
   self.assertEqual(m.receive('correct',signal,11),[])
   lines=(Path(d)/'recovery.log').read_text().splitlines()
   self.assertEqual(json.loads(lines[-1])['decision'],'would_reload')
 def test_captcha_never_prompts_reload(self):
  with tempfile.TemporaryDirectory() as d:
   m=RecoveryMonitor(Path(d),soft=5,hard=10)
   s={'pairCode':'correct','activeJobId':'j','tabAlive':True,'fp':{'captcha':True}}
   m.receive('correct',s,0);m.receive('correct',s,20)
   self.assertEqual(json.loads((Path(d)/'recovery.log').read_text().splitlines()[-1])['decision'],'blocked')
 def test_rate_limit_and_stale_heartbeat(self):
  with tempfile.TemporaryDirectory() as d:
   m=RecoveryMonitor(Path(d),soft=5,hard=10)
   s={'pairCode':'correct','activeJobId':'j','tabAlive':True,'fp':{'rateLimit':True}}
   m.receive('correct',s,0);m.receive('correct',s,20)
   self.assertEqual(m.snapshot(30)['decision'],'blocked')
   self.assertFalse(m.snapshot(111)['responding'])
 def test_wrong_content_script_job_never_requests_reload(self):
  with tempfile.TemporaryDirectory() as d:
   m=RecoveryMonitor(Path(d),soft=5,hard=10)
   s={'pairCode':'correct','activeJobId':'j','tabAlive':True,'fp':{'jobId':'other','msgCount':0,'lastLen':0}}
   m.receive('correct',s,0);m.receive('correct',s,20)
   self.assertEqual(m.snapshot(20)['decision'],'blocked')
