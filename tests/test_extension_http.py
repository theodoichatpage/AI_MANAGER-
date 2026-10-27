import json, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
import server

class ExtensionHTTPTest(unittest.TestCase):
 def test_readonly_heartbeat_rejects_other_session(self):
  with server.STUDIO.lock:
   old_code,old_data=server.STUDIO.code,server.STUDIO.data
   server.STUDIO.code='a'*16;server.STUDIO.data={'active_job_id':'j1'}
  http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
  def post(body):
   req=urllib.request.Request('http://127.0.0.1:%d/api/ext/heartbeat'%http.server_port,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':'chrome-extension://test'},method='POST')
   try:
    with urllib.request.urlopen(req) as r:return r.status,json.load(r)
   except urllib.error.HTTPError as e:return e.code,json.load(e)
  try:
   self.assertEqual(post({'pairCode':'wrong','activeJobId':'j1'})[0],403)
   self.assertEqual(post({'pairCode':'a'*16,'activeJobId':'wrong'})[0],403)
   status,body=post({'pairCode':'a'*16,'activeJobId':'j1','chatTabId':4,'lastHeartbeatAt':1,'identityVersion':1})
   self.assertEqual(status,200);self.assertEqual(body['commands'],[])
  finally:
   http.shutdown();http.server_close();thread.join()
   with server.STUDIO.lock:server.STUDIO.code,server.STUDIO.data=old_code,old_data
