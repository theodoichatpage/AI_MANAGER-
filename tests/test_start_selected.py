"""Deploying one project must not be blocked by idle queue entries or start a different one."""
import tempfile, unittest
from pathlib import Path
from queue_manager import QueueManager

class StartSelected(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.q=QueueManager(Path(self.tmp.name))
  for pid in ('older','selected','later'):
   self.q.add({'id':pid,'name':pid,'folder':str(Path(self.tmp.name)/pid)})
   self.q.attach_automation(pid,'task-'+pid)
 def tearDown(self):self.q.close();self.tmp.cleanup()
 def test_waiting_older_project_does_not_block_or_steal_the_selected_run(self):
  self.q.start_selected('selected')
  self.assertEqual(self.q.get('selected')['status'],'running')
  self.assertEqual(self.q.get('older')['status'],'waiting')
  self.assertEqual(self.q.get('later')['status'],'waiting')
  self.q.automation_update('selected',1,1,'done','completed')
  self.assertEqual(self.q.get('older')['status'],'waiting','single-project run must not continue the whole queue')
  self.assertFalse(self.q._enabled())
 def test_pause_resume_does_not_expand_a_single_project_run(self):
  self.q.start_selected('selected');self.q.pause('selected');self.q.resume('selected')
  self.q.automation_update('selected',1,1,'done','completed')
  self.assertEqual(self.q.get('older')['status'],'waiting')
  self.assertEqual(self.q.get('later')['status'],'waiting')
  self.assertFalse(self.q._enabled())
 def test_start_all_explicitly_releases_the_single_project_scope(self):
  self.q.start_selected('selected');self.q.stop_all();self.q.start_all()
  self.assertEqual(self.q.get('older')['status'],'running')
 def test_stop_all_delete_then_new_project_can_run(self):
  self.q.start_all();self.q.stop_all();self.q.remove('older')
  self.q.add({'id':'new','name':'new','folder':str(Path(self.tmp.name)/'new')})
  self.q.attach_automation('new','task-new')
  # A catalog-imported item can be waiting again, without being an active task.
  self.q.add({'id':'catalog','name':'catalog','folder':str(Path(self.tmp.name)/'catalog')})
  self.q.start_selected('new')
  self.assertEqual(self.q.get('new')['status'],'running')
  self.assertEqual(self.q.get('catalog')['status'],'waiting')
  self.assertEqual(self.q.get('selected')['status'],'stopped')
 def test_real_running_and_paused_projects_still_block(self):
  self.q.start_all()
  with self.assertRaisesRegex(ValueError,'older'):self.q.start_selected('selected')
  self.q.pause('older')
  with self.assertRaisesRegex(ValueError,'older'):self.q.start_selected('selected')
  self.assertEqual(self.q.get('selected')['status'],'waiting')
 def test_failed_selected_project_can_retry_without_starting_others(self):
  self.q.start_selected('selected')
  self.q.automation_update('selected',0,1,'error','failed','fixture error')
  self.q.retry_errors('selected')
  self.assertEqual(self.q.get('selected')['status'],'running')
  self.assertEqual(self.q.get('older')['status'],'waiting')
  self.assertEqual(self.q.get('later')['status'],'waiting')
 def test_selected_project_must_have_a_workflow(self):
  self.q.add({'id':'unprepared','name':'unprepared','folder':str(Path(self.tmp.name)/'unprepared')})
  with self.assertRaises(ValueError):self.q.start_selected('unprepared')
if __name__=='__main__':unittest.main()
