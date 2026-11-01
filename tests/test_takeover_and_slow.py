"""A re-deployed run takes its own project's Studio lock; one slow Studio round is retried, not a stop."""
import tempfile,unittest
from automation_agent.resource_lock import StudioResource
from automation_agent.runtime import slow_round
from automation_agent.studio_workflow import StudioReviewRequired

def ctx(run,project,sid='s'*32):return {'studio_run_id':run,'manager_project_id':project,'studio_project_id':sid}

class Lock(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.lock=StudioResource(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_same_project_takes_over_other_project_is_refused(self):
  self.lock.acquire(ctx('old','p1'),'STUDIO_PARALLEL')
  self.lock.acquire(ctx('new','p1'),'STUDIO_OPEN')  # re-deploy of the same project
  with self.assertRaises(StudioReviewRequired):self.lock.acquire(ctx('other','p2'),'STUDIO_OPEN')
  self.lock.release(ctx('old','p1'))  # the replaced run cannot free the new owner's lock
  with self.assertRaises(StudioReviewRequired):self.lock.acquire(ctx('other','p2'),'STUDIO_OPEN')
  self.lock.release(ctx('new','p1'));self.lock.acquire(ctx('other','p2'),'STUDIO_OPEN')

class Slow(unittest.TestCase):
 def test_only_timed_out_studio_rounds(self):
  task={'context':{'studio_project_id':'s'*32}}
  self.assertTrue(slow_round({'action':'STUDIO_PARALLEL'},{'status':'timeout'},task))
  self.assertFalse(slow_round({'action':'STUDIO_PARALLEL'},{'status':'failed'},task))
  self.assertFalse(slow_round({'action':'STUDIO_OPEN'},{'status':'timeout'},task),'opening the browser is not repeated blindly')
  self.assertFalse(slow_round({'action':'CLICK'},{'status':'timeout'},task))
  self.assertFalse(slow_round({'action':'STUDIO_PARALLEL'},{'status':'timeout'},{'context':{}}))
if __name__=='__main__':unittest.main()
