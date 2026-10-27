import json, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import server
from studio_catalog import StudioCatalog

class CatalogHTTPTests(unittest.TestCase):
 def test_only_matching_session_can_update_catalog(self):
  with tempfile.TemporaryDirectory() as tmp, patch.object(server,'BASE',Path(tmp)):
   server.STUDIO.configure('session1234567890')
   http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
   thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   url=f'http://127.0.0.1:{http.server_port}/api/studio-presence'
   def send(payload,origin='https://video-image-studio-git-phase3-manager-presence-image-studio1.vercel.app'):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'text/plain','Origin':origin},method='POST')
    try:
     with urllib.request.urlopen(req) as response:return response.status
    except urllib.error.HTTPError as e:return e.code
   payload={'sessionId':'session1234567890','activeProjectId':'session1234567890','tabId':'t','studioInstance':'instance1234567890','chatReady':True,'projects':[{'id':'id1','name':'Dự án','updatedAt':1}]}
   try:
    self.assertEqual(send(payload,origin='https://evil.example'),403)
    self.assertEqual(send({**payload,'activeProjectId':'wrong'}),400)
    self.assertEqual(send(payload),200)
    rows=StudioCatalog(Path(tmp)/'studio_catalog.sqlite3').list('https://video-image-studio-git-phase3-manager-presence-image-studio1.vercel.app','instance1234567890')
    self.assertEqual(rows[0]['name'],'Dự án')
   finally:http.shutdown();http.server_close();thread.join();server.STUDIO.disconnect()
