import json,tempfile,threading,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
import server
from queue_manager import QueueManager
class StudioImportTests(unittest.TestCase):
 def test_legacy_duplicate_import_preserves_finished_project_and_folders(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'config',return_value={'root':tmp}):
   q=QueueManager(tmp);presence=server.StudioPresence();sid='a'*32;origin='https://video-image-studio.vercel.app'
   old=server.create_project('Old completed','script');duplicate=server.create_project('Empty duplicate','')
   old.update(studio_project_id=sid,studio_url=origin+'/',browser='edge',browser_profile='Default')
   duplicate.update(studio_source={'id':sid,'origin':origin,'browser':'edge','profile':'Default'},studio_import_id=sid,browser='edge',browser_profile='Default')
   for p in (old,duplicate):server.atomic(Path(p['folder'])/'project.json',p);q.add(p);q.stop(p['id'])
   with q.lock,q.db:q._set(old['id'],status='completed',execution_mode='automation',automation_task_id='completed-job',action_done=9)
   presence.update({'sessionId':sid,'tabId':'t','origin':origin,'projects':[{'id':sid,'name':'Renamed Studio'}]})
   http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   try:
    with patch.object(server,'MANAGER',q),patch.object(server,'PRESENCE',presence),patch('automation_agent.edge_profiles.require_profile',return_value={}):
     req=urllib.request.Request('http://127.0.0.1:'+str(http.server_address[1])+'/api/studio-import',json.dumps({'studio_project_id':sid,'studio_url':origin,'browser_profile':'Default'}).encode(),{'Origin':'http://127.0.0.1:8765','Content-Type':'application/json'})
     for _ in range(2):
      with urllib.request.urlopen(req) as r:self.assertEqual(json.load(r)['id'],old['id'])
     self.assertEqual(len(server.projects()),1);self.assertEqual(len(server.projects(include_duplicates=True)),2);self.assertEqual(q.get(old['id'])['status'],'completed');self.assertTrue(Path(duplicate['folder']).exists());self.assertEqual(json.loads((Path(duplicate['folder'])/'project.json').read_text())['studio_duplicate_of'],old['id'])
   finally:http.shutdown();http.server_close();thread.join();q.close()
