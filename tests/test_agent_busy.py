import tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from automation_agent.runtime import AgentRuntime
class BusyTests(unittest.TestCase):
 def test_enqueue_while_running_does_not_reject_start(self):
  with tempfile.TemporaryDirectory() as td:
   r=AgentRuntime(Path(td))
   try:
    a=r.store.submit([{'action':'WAIT','seconds':.4,'timeout':3}]);r.start()
    end=time.monotonic()+2
    while not r.current and time.monotonic()<end:time.sleep(.01)
    b=r.store.submit([{'action':'WAIT','seconds':.01,'timeout':3}]);r.start()
    end=time.monotonic()+4
    while r.store.get(b)['status']!='completed' and time.monotonic()<end:time.sleep(.02)
    self.assertEqual(r.store.get(a)['status'],'completed');self.assertEqual(r.store.get(b)['status'],'completed')
   finally:r.close()
 def test_ambiguous_wait_does_not_spend_timeout_retrying(self):
  from automation_agent.action_worker import dispatch
  from automation_agent.window_manager import WindowChoiceRequired
  with patch('automation_agent.action_worker.wm.find_window',side_effect=WindowChoiceRequired('Chọn cửa sổ')):
   start=time.monotonic()
   with self.assertRaises(WindowChoiceRequired):dispatch({'action':'WAIT_WINDOW','target_app':'chrome','timeout':30},{},Path('.'),{})
   self.assertLess(time.monotonic()-start,.5)

class InspectionTests(unittest.TestCase):
 def test_readonly_inspection_does_not_wait_behind_active_task(self):
  import json,urllib.request,urllib.error,sys
  from automation_agent.agent_server import AgentServer
  with tempfile.TemporaryDirectory() as td:
   server=AgentServer(0,'token',Path(td));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   def post(body):
    req=urllib.request.Request('http://127.0.0.1:%d/inspect'%server.server_port,json.dumps(body).encode(),{'Authorization':'Bearer token','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=2) as response:return json.load(response)
   try:
    tid=server.runtime.store.submit([{'action':'WAIT','seconds':20,'timeout':30}]);server.runtime.start()
    end=time.monotonic()+2
    while not server.runtime.current and time.monotonic()<end:time.sleep(.01)
    with self.assertRaises(urllib.error.HTTPError):post({'action':'HOTKEY','keys':'ENTER'})
    if sys.platform!='win32':
     begin=time.monotonic();result=post({'action':'LIST_WINDOWS'});self.assertLess(time.monotonic()-begin,2)
     self.assertFalse(result['success']);self.assertEqual(server.runtime.store.get(tid)['status'],'running')
   finally:server.runtime.stop();server.shutdown();server.runtime.close();server.server_close();thread.join()
