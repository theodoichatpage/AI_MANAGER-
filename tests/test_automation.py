import tempfile, unittest
from pathlib import Path
from automation_agent.task_store import TaskStore

class TaskStoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'agent.sqlite3';self.s=TaskStore(self.path)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def add(self):return self.s.submit([{'action':'WAIT','seconds':0},{'action':'WAIT','seconds':0}],project='p1')
 def test_checkpoint_only_advances_after_success(self):
  t=self.add();self.s.claim(t);self.s.complete_action(t,0,{'success':True,'action':'WAIT'})
  self.assertEqual(self.s.get(t)['next_action'],1)
 def test_restart_pauses_running_without_resetting_progress(self):
  t=self.add();self.s.claim(t);self.s.complete_action(t,0,{'success':True});self.s.close();self.s=TaskStore(self.path)
  self.assertEqual((self.s.get(t)['status'],self.s.get(t)['next_action']),('paused',1))
 def test_stop_all_blocks_pending_and_current(self):
  t=self.add();u=self.add();self.s.claim(t);self.s.stop_all();self.assertEqual(self.s.get(t)['status'],'stopped');self.assertEqual(self.s.get(u)['status'],'stopped')
 def test_stopped_task_cannot_advance(self):
  t=self.add();self.s.claim(t);self.s.stop_all();self.s.complete_action(t,0,{'success':True});self.assertEqual(self.s.get(t)['next_action'],0)
 def test_only_one_running(self):
  t=self.add();u=self.add();self.s.claim(t)
  with self.assertRaises(ValueError):self.s.claim(u)
 def test_ambiguous_action_requires_manual_review(self):
  t=self.s.submit([{'action':'CLICK','target_app':'chrome'}]);self.s.claim(t);self.s.mark_action(t,0);self.s.close();self.s=TaskStore(self.path)
  self.assertEqual(self.s.get(t)['status'],'needs_review')
 def test_wrong_action_schema_rejected(self):
  with self.assertRaises(ValueError):self.s.submit([{'action':'SHELL','command':'anything'}])

class ExecutorTests(unittest.TestCase):
 def test_wait_action_executes_in_real_subprocess(self):
  from automation_agent.action_executor import ActionExecutor
  import threading
  with tempfile.TemporaryDirectory() as td:
   result=ActionExecutor(Path(td)).run('task',{'action':'WAIT','seconds':.01,'timeout':2},{},threading.Event())
   self.assertTrue(result['success']);self.assertEqual(result['action'],'WAIT')
 def test_cancel_stops_subprocess_and_returns_cancelled(self):
  from automation_agent.action_executor import ActionExecutor
  import threading,time
  with tempfile.TemporaryDirectory() as td:
   e=ActionExecutor(Path(td));stop=threading.Event();out=[]
   t=threading.Thread(target=lambda:out.append(e.run('task',{'action':'WAIT','seconds':20,'timeout':30},{},stop)));t.start();time.sleep(.2);stop.set();e.cancel();t.join(3)
   self.assertFalse(t.is_alive());self.assertEqual(out[0]['status'],'stopped')
 def test_timeout_terminates_worker(self):
  from automation_agent.action_executor import ActionExecutor
  import threading
  with tempfile.TemporaryDirectory() as td:
   result=ActionExecutor(Path(td)).run('task',{'action':'WAIT','seconds':3,'timeout':.1},{},threading.Event())
   self.assertEqual(result['status'],'timeout')
 def test_nonwindows_does_not_fake_success(self):
  import sys,threading
  if sys.platform=='win32':self.skipTest('Linux-only unsupported check')
  from automation_agent.action_executor import ActionExecutor
  with tempfile.TemporaryDirectory() as td:
   result=ActionExecutor(Path(td)).run('task',{'action':'LIST_WINDOWS','timeout':2},{},threading.Event())
   self.assertFalse(result['success']);self.assertIn('Windows',result['error'])

class QueueAutomationTests(unittest.TestCase):
 def test_real_action_progress_does_not_create_fake_scenes(self):
  from queue_manager import QueueManager
  with tempfile.TemporaryDirectory() as td:
   q=QueueManager(Path(td));q.add({'id':'p','name':'P','folder':td});q.attach_automation('p','t');q.start_all();q.automation_update('p',1,3,'SCREENSHOT','running')
   p=q.get('p');self.assertEqual(p['execution_mode'],'automation');self.assertEqual(p['completed_scenes'],0);self.assertEqual(p['sim_done'],0);q.close()

class RuntimeTests(unittest.TestCase):
 def test_sequential_workflow_runs_actual_wait_children(self):
  import time
  from automation_agent.runtime import AgentRuntime
  with tempfile.TemporaryDirectory() as td:
   r=AgentRuntime(Path(td))
   try:
    tid=r.store.submit([{'action':'WAIT','seconds':.01,'timeout':2},{'action':'WAIT','seconds':.01,'timeout':2}]);r.start()
    end=time.monotonic()+5
    while r.store.get(tid)['status']!='completed' and time.monotonic()<end:time.sleep(.02)
    self.assertEqual(r.store.get(tid)['next_action'],2);self.assertEqual(len(r.store.get(tid)['results']),2)
   finally:r.close()
 def test_stop_prevents_next_action(self):
  import time
  from automation_agent.runtime import AgentRuntime
  with tempfile.TemporaryDirectory() as td:
   r=AgentRuntime(Path(td))
   try:
    tid=r.store.submit([{'action':'WAIT','seconds':20,'timeout':30},{'action':'WAIT','seconds':.01,'timeout':2}]);r.start()
    end=time.monotonic()+3
    while not r.store.get(tid).get('in_flight') and time.monotonic()<end:time.sleep(.01)
    r.stop();time.sleep(.2);self.assertEqual(r.store.get(tid)['next_action'],0);self.assertFalse(r.enabled)
   finally:r.close()

class AgentAPITests(unittest.TestCase):
 def test_authentication_and_real_wait_task(self):
  import threading,time,json,urllib.request,urllib.error
  from automation_agent.agent_server import AgentServer
  with tempfile.TemporaryDirectory() as td:
   s=AgentServer(0,'secret',Path(td));t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
   def call(path,data=None,token='secret'):
    request=urllib.request.Request('http://127.0.0.1:%d%s'%(s.server_port,path),None if data is None else json.dumps(data).encode(),{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=2) as res:return json.load(res)
   try:
    with self.assertRaises(urllib.error.HTTPError):call('/state',token='wrong')
    tid=call('/submit',{'actions':[{'action':'WAIT','seconds':.01,'timeout':2}]})['task_id'];call('/start',{})
    end=time.monotonic()+4
    while s.runtime.store.get(tid)['status']!='completed' and time.monotonic()<end:time.sleep(.02)
    self.assertEqual(s.runtime.store.get(tid)['status'],'completed');self.assertTrue(call('/state')['online'])
   finally:s.shutdown();s.runtime.close();s.server_close();t.join()

class RecoveryPolicyTests(unittest.TestCase):
 def test_no_recovery_for_ambiguous_input(self):
  from automation_agent.runtime import may_recover
  self.assertFalse(may_recover({'action':'TYPE_TEXT'},{'error_code':'WINDOW_LOST'},0))
 def test_recovery_is_bounded_and_requires_lost_window(self):
  from automation_agent.runtime import may_recover
  self.assertTrue(may_recover({'action':'SCREENSHOT'},{'error_code':'WINDOW_LOST'},0))
  self.assertFalse(may_recover({'action':'SCREENSHOT'},{'error_code':'WINDOW_LOST'},3))
  self.assertFalse(may_recover({'action':'SCREENSHOT'},{'error_code':'UNKNOWN'},0))

class ReviewRegressionTests(unittest.TestCase):
 def test_held_task_is_never_exposed_as_waiting(self):
  with tempfile.TemporaryDirectory() as td:
   s=TaskStore(Path(td)/'a.sqlite3')
   try:
    tid=s.submit([{'action':'WAIT'}],initial_status='held');self.assertEqual(s.get(tid)['status'],'held')
   finally:s.close()
 def test_explicit_hwnd_uses_checkpoint_identity(self):
  from unittest.mock import patch
  from automation_agent.action_worker import dispatch
  wm_module='automation_agent.action_worker.wm.'
  context={'target_app':'chrome','hwnd':7,'pid':99,'process_started':123}
  with patch(wm_module+'validate_target',return_value=7) as validate,patch(wm_module+'windows',return_value=[]) as listing:
   result=dispatch({'action':'FIND_WINDOW','target_app':'chrome','hwnd':7},context,Path('.'),{})
   self.assertEqual(result['context']['pid'],99);validate.assert_called_once();listing.assert_not_called()
 def test_test_window_does_not_inherit_action_pipes(self):
  from unittest.mock import patch
  import subprocess
  from automation_agent.action_worker import dispatch
  with patch('automation_agent.action_worker.wm.require_windows'),patch('automation_agent.action_worker.wm.windows',return_value=[]),patch('automation_agent.action_worker.subprocess.Popen') as spawn:
   dispatch({'action':'OPEN_TEST_WINDOW'},{},Path('.'),{})
   self.assertEqual(spawn.call_args.kwargs.get('stdout'),subprocess.DEVNULL)
   self.assertEqual(spawn.call_args.kwargs.get('stderr'),subprocess.DEVNULL)

class BridgeSafetyTests(unittest.TestCase):
 def test_stop_waits_for_inflight_release_and_never_releases_after_stop(self):
  import threading,time
  from queue_manager import QueueManager
  from automation_agent.queue_bridge import QueueBridge
  entered=threading.Event();allow=threading.Event();stopped=threading.Event();late=[]
  class Agent:
   def snapshot(self):return {'online':True,'tasks':[{'id':'t','status':'held'}]}
   def request(self,*args,**kw):
    entered.set();allow.wait(2)
    if stopped.is_set():late.append(True)
  with tempfile.TemporaryDirectory() as td:
   q=QueueManager(Path(td));q.add({'id':'p','name':'P','folder':td});q.attach_automation('p','t');q.start_all();b=QueueBridge(q,Agent())
   try:
    self.assertTrue(entered.wait(2))
    def stop():q.stop_all();stopped.set()
    t=threading.Thread(target=stop);t.start();time.sleep(.05);self.assertFalse(stopped.is_set());allow.set();t.join(2);self.assertTrue(stopped.is_set());time.sleep(.6);self.assertEqual(late,[])
   finally:allow.set();b.close();q.close()
 def test_root_reset_discards_old_bridge(self):
  from unittest.mock import patch,Mock
  from automation_agent.manager_service import AutomationService
  with tempfile.TemporaryDirectory() as td,patch('automation_agent.manager_service.AgentClient'):
   service=AutomationService(Path(td),lambda:None);old=Mock();service.bridge=old;service.reset_bridge();old.close.assert_called_once();self.assertIsNone(service.bridge)
