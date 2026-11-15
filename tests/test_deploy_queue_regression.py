"""Exercise the real Studio-deploy handler and SQLite queue; external Agent/Studio are fixtures."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from queue_manager import QueueManager
import server

class DeployQueueRegression(unittest.TestCase):
 def test_new_project_deploys_when_an_unrelated_catalog_project_is_waiting(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);q=QueueManager(root);opened=[]
   q.add({'id':'catalog-old','name':'Catalog old','folder':str(root/'old')})
   def atomic(path,value):Path(path).write_text(json.dumps(value),encoding='utf8')
   def create(name,script):
    folder=root/'new';folder.mkdir();p={'id':'new-id','name':name,'folder':str(folder),'script':script};atomic(folder/'project.json',p);return p
   class Agent:
    def snapshot(self):return {'online':True}
    def control(self,command):q.attach_automation(command['project'],'fixture-task');opened.append(command)
    def ensure_bridge(self):pass
    def resume_studio(self,ids):pass
   class API:
    def create(self,sid):pass
    def request(self,*args,**kw):pass
   try:
    with patch.multiple(server,manager=lambda:q,automation=lambda:Agent(),create_project=create,atomic=atomic), patch('automation_agent.studio_workflow.StudioAPI',API):
     result=server.studio_deploy({'name':'New project','youtube_url':'https://www.youtube.com/watch?v=WziSfyGZsUY','browser':'edge'})
    self.assertEqual(result['project'],'new-id')
    self.assertEqual(q.get('new-id')['status'],'running')
    self.assertEqual(q.get('catalog-old')['status'],'waiting')
    self.assertEqual(len(opened),1)
    self.assertIn('analysis',opened[0]['work_config']['tasks'])
   finally:q.close()
