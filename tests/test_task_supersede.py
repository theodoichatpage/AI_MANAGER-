"""A new Studio workflow retires the project's old unfinished task (2026-11-15, project 035 ran two tasks)."""
import tempfile,unittest
from pathlib import Path
from automation_agent.task_store import TaskStore

class Supersede(unittest.TestCase):
 def setUp(self):
  self.td=tempfile.TemporaryDirectory();self.s=TaskStore(Path(self.td.name)/'t.sqlite3')
 def tearDown(self):self.s.close();self.td.cleanup()
 def task(self,status):
  tid=self.s.submit([{'action':'WAIT','seconds':0}],'p1','Studio',{'studio_project_id':'x'})
  with self.s.db:
   t=self.s.get(tid);t['status']=status;self.s.save(t)
  return tid
 def test_stopped_task_can_never_run_again(self):
  tid=self.task('stopped');self.s.supersede(tid,'new')
  self.assertEqual(self.s.get(tid)['status'],'superseded')
  with self.assertRaises(ValueError):self.s.claim(tid)
  with self.assertRaises(ValueError):self.s.resume(tid)
 def test_running_or_waiting_task_is_refused(self):
  for status in ('running','waiting'):
   tid=self.task(status)
   with self.assertRaises(ValueError):self.s.supersede(tid,'new')
   self.assertEqual(self.s.get(tid)['status'],status)
 def test_completed_task_is_left_alone(self):
  tid=self.task('completed');self.s.supersede(tid,'new');self.assertEqual(self.s.get(tid)['status'],'completed')

if __name__=='__main__':unittest.main()
