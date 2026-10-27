import json,os,subprocess,sys,tempfile,time,unittest,urllib.request,urllib.error
class PresenceHTTPTest(unittest.TestCase):
 def test_only_allowed_origin_and_matching_session(self):
  with tempfile.TemporaryDirectory() as td:
   proc=subprocess.Popen([sys.executable,'server.py','--no-browser'],env=dict(os.environ,AI_MANAGER_HOME=td),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   base='http://127.0.0.1:8765'
   def post(path,data,origin):
    req=urllib.request.Request(base+path,json.dumps(data).encode(),{'Origin':origin,'Content-Type':'text/plain'})
    with urllib.request.urlopen(req,timeout=2) as r:return r.status
   try:
    for _ in range(60):
     try:
      with urllib.request.urlopen(base+'/api/state',timeout=1):break
     except OSError:time.sleep(.05)
    preview='https://video-image-studio-git-phase3-manager-presence-image-studio1.vercel.app'
    req=urllib.request.Request(base+'/api/studio-presence',method='OPTIONS',headers={'Origin':preview,'Access-Control-Request-Method':'POST','Access-Control-Request-Private-Network':'true'})
    with urllib.request.urlopen(req,timeout=2) as response:
     self.assertEqual(response.headers['Access-Control-Allow-Origin'],preview);self.assertEqual(response.headers['Access-Control-Allow-Private-Network'],'true')
    code='abcdefghijklmnop'
    self.assertEqual(post('/api/studio',{'action':'connect','code':code},base),200)
    with self.assertRaises(urllib.error.HTTPError) as bad:post('/api/studio-presence',{'sessionId':code,'chatReady':True},'https://evil.example')
    self.assertEqual(bad.exception.code,403)
    with self.assertRaises(urllib.error.HTTPError):post('/api/studio-presence',{'sessionId':'wrongwrongwrong123','chatReady':True},'https://video-image-studio.vercel.app')
    self.assertEqual(post('/api/studio-presence',{'sessionId':code,'chatReady':True},'https://video-image-studio.vercel.app'),204)
    self.assertEqual(post('/api/studio-presence',{'sessionId':code,'chatReady':True},'https://video-image-studio-git-phase3-manager-presence-image-studio1.vercel.app'),204)
    with urllib.request.urlopen(base+'/api/state',timeout=2) as r:state=json.load(r)
    self.assertEqual(state['studio']['tab_status'],'connected');self.assertEqual(state['studio']['chat_status'],'connected')
   finally:proc.terminate();proc.wait(timeout=5)
if __name__=='__main__':unittest.main()
