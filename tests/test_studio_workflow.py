import copy,tempfile,unittest
from pathlib import Path
from automation_agent.studio_workflow import StudioStep,StudioReviewRequired,workflow
SID='a'*32
class FakeAPI:
 def __init__(self,s):self.s=s;self.posts=[]
 def request(self,sid,route='',body=None):
  if body is not None:
   self.posts.append(route);self.s['activeJob']={'id':'job'+str(len(self.posts)),'type':'script_structure' if route=='/analysis' else 'part_analysis','partId':route.split('/')[2] if route.startswith('/parts/') else None}
  return copy.deepcopy(self.s)
class StudioWorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.c={'studio_project_id':SID,'studio_run_id':'run','studio_origin':'https://video-image-studio.vercel.app','studio_folder':self.tmp.name,'studio_script':'Script'}
  self.presence=lambda:{'studio_tab_open':True,'chat_connected':True,'session_id':SID,'manager_run_id':'run','origin':self.c['studio_origin']}
 def tearDown(self):self.tmp.cleanup()
 def step(self,api):return StudioStep(self.c,api,self.presence)
 def test_structure_then_parts_sequential_and_checkpoint(self):
  api=FakeAPI({'id':SID,'parts':[],'script':'Script'})
  self.assertTrue(self.step(api).step('STUDIO_ANALYZE')['waiting']);self.step(api).step('STUDIO_ANALYZE');self.assertEqual(api.posts,['/analysis'])
  api.s.update(activeJob=None,parts=[{'id':'p1','status':'ready','scenes':[]},{'id':'p2','status':'ready','scenes':[]}])
  self.step(api).step('STUDIO_ANALYZE');self.step(api).step('STUDIO_SCENES');self.step(api).step('STUDIO_SCENES');self.assertEqual(api.posts,['/analysis','/parts/p1/analysis'])
  api.s['parts'][0].update(status='complete',scenes=[{'prompt':'real'}]);api.s['activeJob']=None
  self.step(api).step('STUDIO_SCENES');self.assertEqual(api.posts[-1],'/parts/p2/analysis');self.assertTrue(Path(self.tmp.name,'scenes/p1.json').exists())
  api.s['parts'][1].update(status='complete',scenes=[{'prompt':'real2'}]);api.s['activeJob']=None
  result=self.step(api).step('STUDIO_SCENES');self.assertNotIn('waiting',result);self.assertEqual(result['context']['studio_total_scenes'],2)
 def test_uncertain_post_is_not_repeated_after_restart(self):
  api=FakeAPI({'id':SID,'parts':[]});original=api.request
  def broken(*a,**kw):
   if len(a)>2 and a[2] is not None:raise TimeoutError()
   return original(*a,**kw)
  api.request=broken
  with self.assertRaises(StudioReviewRequired):self.step(api).step('STUDIO_ANALYZE')
  api.request=original
  with self.assertRaises(StudioReviewRequired):self.step(api).step('STUDIO_ANALYZE')
  self.assertEqual(api.posts,[])
 def test_completed_parts_not_restarted(self):
  api=FakeAPI({'id':SID,'parts':[{'id':'p1','status':'complete','scenes':[]}]})
  self.step(api).step('STUDIO_ANALYZE');self.step(api).step('STUDIO_SCENES');self.assertEqual(api.posts,[])
 def test_wrong_presence_never_posts(self):
  api=FakeAPI({'id':SID,'parts':[]});obj=self.step(api);obj.presence=lambda:{'studio_tab_open':True,'chat_connected':True,'session_id':'wrong'}
  self.assertTrue(obj.step('STUDIO_ANALYZE')['waiting']);self.assertEqual(api.posts,[])
 def test_external_job_is_not_adopted(self):
  api=FakeAPI({'id':SID,'parts':[],'activeJob':{'id':'external'}})
  with self.assertRaises(StudioReviewRequired):self.step(api).step('STUDIO_ANALYZE')
 def test_launch_binds_nonce_to_existing_project(self):
  actions,c=workflow(SID,'https://video-image-studio.vercel.app','edge','Default',self.tmp.name,'Script')
  self.assertIn('managerProject='+SID,actions[3]['url']);self.assertIn(c['studio_run_id'],actions[3]['url']);self.assertEqual(actions[-1]['action'],'STUDIO_SCENES')
 def test_pending_step_preserves_same_action_checkpoint(self):
  from automation_agent.task_store import TaskStore
  store=TaskStore(Path(self.tmp.name)/'task.sqlite3');tid=store.submit([{'action':'STUDIO_SCENES'}]);store.claim(tid);store.mark_action(tid,0)
  store.pending_action(tid,0,{'result':{'context':{'studio_completed_parts':1}}})
  store.close();store=TaskStore(Path(self.tmp.name)/'task.sqlite3');task=store.get(tid)
  self.assertEqual(task['next_action'],0);self.assertEqual(task['status'],'paused');self.assertEqual(task['context']['studio_completed_parts'],1);store.close()
 def test_stage_watchdog_is_bounded(self):
  api=FakeAPI({'id':SID,'parts':[]});obj=self.step(api);obj.presence=lambda:{};obj.clock=lambda:0
  self.assertTrue(obj.step('STUDIO_READY')['waiting']);obj.clock=lambda:121
  with self.assertRaises(TimeoutError):obj.step('STUDIO_READY')
 def test_mapping_is_by_id_unique_and_persists(self):
  from queue_manager import QueueManager
  q=QueueManager(self.tmp.name);q.add({'id':'a','name':'Same name','folder':self.tmp.name});q.add({'id':'b','name':'Same name','folder':self.tmp.name})
  q.bind_studio('a',SID,self.c['studio_origin'],'edge','Default')
  with self.assertRaises(ValueError):q.bind_studio('b',SID,self.c['studio_origin'],'edge','Default')
  q.close();q=QueueManager(self.tmp.name)
  self.assertEqual(q.db.execute('SELECT profile FROM studio_links WHERE project_id=?',('a',)).fetchone()[0],'Default');q.close()
 def test_http_transport_rejects_wrong_session(self):
  import threading,json
  from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
  from unittest.mock import patch
  from automation_agent import studio_workflow as sw
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_GET(self):
    self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'session':{'id':'wrong'}}).encode())
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with patch.object(sw,'API','http://127.0.0.1:'+str(server.server_address[1])):
    with self.assertRaisesRegex(RuntimeError,'sai project ID'):sw.StudioAPI().request(SID)
  finally:server.shutdown();server.server_close();thread.join()
 def test_explicit_retry_only_retries_unfinished_part(self):
  api=FakeAPI({'id':SID,'parts':[{'id':'p1','status':'complete','scenes':[{'prompt':'done'}]},{'id':'p2','status':'ready','scenes':[]}]})
  self.step(api).step('STUDIO_SCENES');api.s['activeJob']=None;api.s['parts'][1]['status']='error'
  with self.assertRaises(RuntimeError):self.step(api).step('STUDIO_SCENES')
  self.c['studio_retry_epoch']=1;self.step(api).step('STUDIO_SCENES');self.step(api).step('STUDIO_SCENES')
  self.assertEqual(api.posts,['/parts/p2/analysis','/parts/p2/analysis'])
