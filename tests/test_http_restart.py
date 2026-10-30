import json, os, subprocess, sys, tempfile, time, unittest, urllib.request
from pathlib import Path
class ProcessTest(unittest.TestCase):
 def test_process_restart(self):
  # This test drives a server on the fixed port 8765. If the real AI MANAGER is running there, every
  # request (change project folder, start/stop queue) would hit it, so skip instead.
  try:
   urllib.request.urlopen('http://127.0.0.1:8765/api/state',timeout=1).close()
   self.skipTest('AI MANAGER đang chạy ở cổng 8765; không chạy thử để tránh đổi dữ liệu thật')
  except OSError:pass
  with tempfile.TemporaryDirectory() as td:
   env=dict(os.environ,AI_MANAGER_HOME=td+'/config'); port='http://127.0.0.1:8765'; p=None
   def start():
    proc=subprocess.Popen([sys.executable,'server.py','--no-browser'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(100):
     try: get(); return proc
     except OSError: time.sleep(.05)
    raise RuntimeError('server did not start')
   def get():
    with urllib.request.urlopen(port+'/api/state',timeout=2) as r:return json.load(r)
   def post(path,obj):
    req=urllib.request.Request(port+path,json.dumps(obj).encode(),{'Content-Type':'application/json','Origin':port})
    with urllib.request.urlopen(req,timeout=2) as r:return json.load(r)
   try:
    p=start(); post('/api/root',{'root':td+'/projects'})
    created=post('/api/test-projects',{}); self.assertEqual(len(created['projects']),3)
    again=post('/api/test-projects',{}); self.assertEqual([p['id'] for p in created['projects']],[p['id'] for p in again['projects']]); self.assertEqual(len(get()['projects']),3)
    post('/api/queue',{'action':'start'}); a,b,c=get()['queue']; self.assertEqual([x['status'] for x in (a,b,c)],['running','waiting','waiting'])
    post('/api/queue',{'action':'pause','id':a['id']}); before=get()['queue'][0]['sim_done']; time.sleep(3.2); self.assertEqual(get()['queue'][0]['sim_done'],before)
    post('/api/queue',{'action':'resume','id':a['id']}); post('/api/queue',{'action':'simulate_complete','id':a['id']}); self.assertEqual(get()['queue'][1]['status'],'running')
    post('/api/queue',{'action':'simulate_fail','id':b['id']}); self.assertEqual(get()['queue'][2]['status'],'running')
    post('/api/queue',{'action':'retry','id':b['id']}); self.assertEqual(get()['queue'][1]['status'],'waiting')
    post('/api/queue',{'action':'stop_all'}); self.assertEqual([x['status'] for x in get()['queue']],['completed','stopped','stopped'])
    post('/api/queue',{'action':'start'}); time.sleep(3.2); before=get(); self.assertEqual(before['queue'][1]['status'],'running'); self.assertGreater(before['queue'][1]['sim_done'],0)
    p.kill();p.wait();p=start(); after=get();self.assertEqual(after['queue'][1]['status'],'paused');self.assertEqual(after['queue'][1]['sim_done'],before['queue'][1]['sim_done']);self.assertEqual([x['id'] for x in after['queue']],[x['id'] for x in before['queue']]);self.assertGreaterEqual(len(after['logs']),len(before['logs'])); self.assertTrue(any('Tiếp tục' in x['message'] for x in after['logs'])); self.assertTrue(any('Lỗi mô phỏng' in x['message'] for x in after['logs']));self.assertEqual(after['queue'][0]['status'],'completed')
   finally:
    if p and p.poll() is None: p.terminate();p.wait()
if __name__=='__main__':unittest.main()
