import json, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import server
from recovery_monitor import RecoveryMonitor

class RecoveryHTTPTest(unittest.TestCase):
 def test_heartbeat_validates_session_and_never_sends_commands(self):
  with tempfile.TemporaryDirectory() as tmp, patch.object(server,'RECOVERY',RecoveryMonitor(Path(tmp),soft=1,hard=2)):
   server.STUDIO.configure('session1234567890');server.STUDIO.data={'active_job_id':'j'};http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   def post(body):
    req=urllib.request.Request(f'http://127.0.0.1:{http.server_port}/api/ext/heartbeat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':'chrome-extension://test'},method='POST')
    try:
     with urllib.request.urlopen(req) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,{}
   try:
    self.assertEqual(post({'pairCode':'wrong'})[0],403)
    self.assertEqual(post({'pairCode':'session1234567890','activeJobId':'other'})[0],409)
    status,body=post({'pairCode':'session1234567890','activeJobId':'j','tabAlive':True,'fp':{'msgCount':0,'lastLen':0}})
    self.assertEqual(status,200);self.assertEqual(body['commands'],[])
   finally:http.shutdown();http.server_close();thread.join();server.STUDIO.disconnect()
