import copy,io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from automation_agent.work_config import normalize,in_scope
from automation_agent.work_ledger import WorkLedger
from automation_agent.resource_lock import StudioResource
from automation_agent.studio_workflow import StudioStep,StudioReviewRequired,workflow
from automation_agent.studio_images import save_image
from queue_manager import QueueManager
SID='a'*32
class API:
 def __init__(self):self.posts=[];self.s={'id':SID,'stylePrompt':'Existing style','parts':[{'id':'p1','status':'complete','scenes':[{'prompt':'s1','imageStatus':'waiting'},{'prompt':'s2','imageStatus':'error'},{'prompt':'s3','imageStatus':'waiting'}]}]}
 def request(self,sid,route='',body=None):
  if body is not None:
   if self.s.get('activeJob'):raise AssertionError('overlap')
   self.posts.append(copy.deepcopy(body));key=body['sceneKeys'][0];self.s['activeJob']={'id':'job'+str(len(self.posts)),'sceneKey':key,'type':'image_generation'};self.s['parts'][0]['scenes'][int(key.split(':')[-1])]['imageStatus']='generating'
  return copy.deepcopy(self.s)
 def finish(self,ok=True):
  job=self.s.pop('activeJob');scene=self.s['parts'][0]['scenes'][int(job['sceneKey'].split(':')[-1])];self.s['lastJob']=job
  scene['imageStatus']='complete' if ok else 'error'
  if ok:scene['imageResults']=[{'url':'https://fixture','jobId':job['id']}]
class WorkTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.clock=[100.0];self.api=API();self.c={'studio_project_id':SID,'studio_run_id':'c'*32,'studio_origin':'https://video-image-studio.vercel.app','studio_folder':self.tmp.name,'manager_project_id':'manager','browser':'edge','browser_profile':'Default','work_config':normalize({'tasks':['images','sync'],'scopes':{'images':{'mode':'range','from':2,'to':3},'sync':{'mode':'range','from':2,'to':3}},'retry_limit':1})}
  out=io.BytesIO();Image.new('RGB',(2,2)).save(out,'PNG');self.bytes=out.getvalue();self.save=patch('automation_agent.scoped_images.save_image',side_effect=lambda *a,**k:save_image(*a,**dict(k,fetch=lambda u:self.bytes)));self.save.start()
 def tearDown(self):self.save.stop();self.tmp.cleanup()
 def w(self):return StudioStep(self.c,self.api,lambda:{'studio_tab_open':True,'chat_connected':True,'session_id':SID,'manager_run_id':self.c['studio_run_id'],'origin':self.c['studio_origin']},clock=lambda:self.clock[0])
 def run_step(self):return self.w().step('STUDIO_IMAGES')
 def test_scope_save_checkpoint_then_next_and_reconcile(self):
  self.run_step();self.assertEqual(self.api.posts[0]['sceneKeys'],['p1:1']);self.assertIn('operation_id',self.api.posts[0]);self.api.finish();self.run_step()
  ledger=self.w().ledger.data;self.assertEqual(ledger['tasks']['images']['subtasks']['p1:1']['status'],'COMPLETED');self.assertTrue(Path(ledger['tasks']['images']['subtasks']['p1:1']['result_path']).exists())
  self.run_step();self.assertEqual(self.api.posts[1]['sceneKeys'],['p1:2']);self.api.finish();self.run_step();r=self.run_step();self.assertNotIn('waiting',r);self.assertEqual(len(self.api.posts),2)
 def test_retry_known_error_once_then_continue_to_next_scene(self):
  self.run_step();self.api.finish(False);r=self.run_step();self.assertEqual(r['context']['work_status'],'RETRYING');self.run_step();self.assertEqual(len(self.api.posts),1)
  self.clock[0]+=10;self.run_step();self.assertEqual(len(self.api.posts),2);self.api.finish(False);self.run_step();self.assertEqual(self.api.posts[-1]['sceneKeys'],['p1:2']);self.api.finish();self.run_step()
  with self.assertRaisesRegex(RuntimeError,'subtask'):self.run_step()
  self.assertEqual(self.w().ledger.get('images','p1:1')['status'],'ERROR')
 def test_sync_only_does_not_generate(self):
  self.c['work_config']=normalize({'tasks':['sync'],'scopes':{'sync':{'mode':'range','from':1,'to':1}}})
  with self.assertRaises(RuntimeError):self.run_step()
  self.assertEqual(self.api.posts,[])
 def test_changed_prompt_blocks_resume(self):
  self.run_step();self.api.s['parts'][0]['scenes'][1]['prompt']='changed'
  with self.assertRaises(StudioReviewRequired):self.run_step()
 def test_lost_output_becomes_error_without_resending(self):
  self.run_step();self.api.finish();self.run_step();path=self.w().ledger.get('images','p1:1')['result_path'];Path(path).unlink();self.run_step();self.assertEqual(self.w().ledger.get('images','p1:1')['status'],'ERROR')
 def test_uncertain_post_does_not_retry(self):
  original=self.api.request
  def bad(sid,route='',body=None):
   if body is not None:raise TimeoutError()
   return original(sid,route,body)
  self.api.request=bad
  with self.assertRaises(StudioReviewRequired):self.run_step()
  self.api.request=original
  with self.assertRaises(StudioReviewRequired):self.run_step()
  self.assertEqual(self.api.posts,[])
 def test_resource_lock_survives_restart_and_other_owner_cannot_release(self):
  lock=StudioResource(self.tmp.name);lock.acquire(self.c,'RUN');other=dict(self.c,studio_run_id='b'*32)
  with self.assertRaises(StudioReviewRequired):StudioResource(self.tmp.name).acquire(other,'RUN')
  lock.release(other)
  with self.assertRaises(StudioReviewRequired):lock.acquire(other,'RUN')
  lock.release(self.c);lock.acquire(other,'RUN')
 def test_queue_three_projects_different_tasks_no_overlap_stop_and_restart(self):
  q=QueueManager(self.tmp.name)
  for i in ('a','b','c'):
   q.add({'id':i,'name':i,'folder':self.tmp.name});q.attach_automation(i,'task-'+i);q.stop(i)
  q.start_batch(['a','b','c']);self.assertEqual([p['id'] for p in q.list() if p['status']=='running'],['a'])
  q.automation_update('a',1,1,'done','completed');self.assertEqual(q.get('b')['status'],'running');q.pause('b');self.assertEqual(q.get('c')['status'],'waiting');q.resume('b');q.automation_update('b',1,1,'done','completed');self.assertEqual(q.get('c')['status'],'running');q.stop_all();q.close();q=QueueManager(self.tmp.name);self.assertEqual(q.get('c')['status'],'stopped');self.assertFalse(q._enabled());self.assertEqual(q.batch(),['a','b','c']);q.close()
 def test_scopes_and_tasks_validated(self):
  for raw in ({'tasks':['video']},{'tasks':['analysis'],'scopes':{'analysis':{'mode':'range','from':1,'to':2}}},{'tasks':['images'],'scopes':{'images':{'mode':'range','from':9,'to':1}}},{'tasks':['scenes'],'rerun':True}):
   with self.assertRaises(ValueError):normalize(raw)
  self.assertTrue(in_scope(5,{'mode':'selected','items':[1,5]}));self.assertFalse(in_scope(2,{'mode':'range','from':3,'to':6}))
 def test_workflow_tasks_are_project_specific(self):
  a,c=workflow(SID,self.c['studio_origin'],'edge','Default',self.tmp.name,'',work_config={'tasks':['sync']});self.assertFalse(any(x['action']=='STUDIO_SCENES' for x in a));self.assertEqual([x['action'] for x in a],['STUDIO_FILES'],'saving pictures needs no browser');self.assertEqual(c['work_config']['tasks'],['sync'])
 def test_partial_scenes_skip_other_parts(self):
  self.c['work_config']=normalize({'tasks':['scenes'],'scopes':{'scenes':{'mode':'range','from':2,'to':2}}});self.api.s['parts']=[{'id':'part1','status':'complete','scenes':[{'prompt':'keep'}]},{'id':'part2','status':'complete','scenes':[{'prompt':'keep2'}]}]
  self.w().step('STUDIO_SCENES');self.assertFalse((Path(self.tmp.name)/'scenes/part1.json').exists());self.assertTrue((Path(self.tmp.name)/'scenes/part2.json').exists());self.assertEqual(self.api.posts,[])
 def test_three_configured_projects_execute_scoped_work_in_order(self):
  configs=[{'tasks':['images','sync'],'scopes':{'images':{'mode':'range','from':1,'to':1},'sync':{'mode':'range','from':1,'to':1}}},{'tasks':['scenes','images'],'scopes':{'scenes':{'mode':'range','from':1,'to':1},'images':{'mode':'missing'}}},{'tasks':['retry_images']}]
  q=QueueManager(Path(self.tmp.name)/'batch');apis=[];contexts=[];actions=[];lock=StudioResource(Path(self.tmp.name)/'resource');post_order=[]
  for i,raw in enumerate(configs):
   folder=Path(self.tmp.name)/('p'+str(i));folder.mkdir();project=str(i);q.add({'id':project,'name':project,'folder':str(folder)});q.attach_automation(project,'task'+project);q.stop(project)
   api=API();api.s['id']=str(i+1)*32
   original=api.request
   def request(sid,route='',body=None,api=api,original=original,project=project):
    if body is not None:
     self.assertFalse(any(other.s.get('activeJob') for other in apis if other is not api));self.assertEqual(q.get(project)['status'],'running');post_order.append(project)
    return original(sid,route,body)
   api.request=request;apis.append(api)
   act,c=workflow(api.s['id'],self.c['studio_origin'],'edge','Default',str(folder),'',work_config=raw);c['manager_project_id']=project;contexts.append(c);actions.append([a for a in act if a['action'].startswith('STUDIO_')])
  q.start_batch(['0','1','2'])
  for i in range(3):
   c=contexts[i];api=apis[i];pres=lambda c=c:{'studio_tab_open':True,'chat_connected':True,'session_id':c['studio_project_id'],'manager_run_id':c['studio_run_id'],'origin':c['studio_origin']}
   for j,action in enumerate(actions[i]):
    finished=False
    for tick in range(40):
     lock.acquire(c,action['action']);w=StudioStep(c,api,pres);r=w.step(action['action'])
     if api.s.get('activeJob'):api.finish()
     if not r.get('waiting'):lock.release(c);finished=True;break
    self.assertTrue(finished)
   q.automation_update(str(i),len(actions[i]),len(actions[i]),'done','completed')
   self.assertEqual(q.get(str(i))['status'],'completed')
  self.assertEqual(post_order,['0','1','1','1','2']);self.assertFalse(any(p['status']=='running' for p in q.list()));q.close()
 def test_pause_and_stop_keep_distinct_task_states(self):
  import threading
  from automation_agent.runtime import AgentRuntime
  from automation_agent.task_store import TaskStore
  runtime=AgentRuntime.__new__(AgentRuntime);runtime.store=TaskStore(Path(self.tmp.name)/'pause.sqlite3');runtime.lock=threading.RLock();runtime.cancel=threading.Event();runtime.current=None;runtime.enabled=True
  class Executor:
   home=Path(self.tmp.name)
   def cancel(self):pass
  class Log:
   def write(self,*a,**kw):pass
  runtime.executor=Executor();runtime.log=Log();tid=runtime.store.submit([{'action':'WAIT'}]);runtime.store.claim(tid);runtime.pause();self.assertEqual(runtime.store.get(tid)['status'],'paused');runtime.store.resume(tid);runtime.start();runtime.stop();self.assertEqual(runtime.store.get(tid)['status'],'stopped');runtime.store.close()
 def test_critical_review_pauses_queue_before_next_project(self):
  import time
  from automation_agent.queue_bridge import QueueBridge
  q=QueueManager(Path(self.tmp.name)/'review');
  for pid in ('a','b'):q.add({'id':pid,'name':pid,'folder':self.tmp.name});q.attach_automation(pid,'t'+pid);q.stop(pid)
  class Agent:
   stopped=False
   def snapshot(self):return {'online':True,'tasks':[{'id':'ta','status':'needs_review','context':{'studio_project_id':SID}}]}
   def stop(self):self.stopped=True
  agent=Agent();bridge=QueueBridge(q,agent)
  try:
   q.start_batch(['a','b']);deadline=time.monotonic()+2
   while time.monotonic()<deadline and (q.get('a')['status']!='paused' or not agent.stopped):time.sleep(.02)
   self.assertEqual(q.get('a')['status'],'paused');self.assertEqual(q.get('b')['status'],'waiting');self.assertTrue(agent.stopped)
  finally:bridge.close();q.close()
 def test_browser_recovery_keeps_project_profile_nonce_and_does_not_submit_prompt(self):
  import threading
  from automation_agent.runtime import AgentRuntime
  from automation_agent.task_store import TaskStore
  runtime=AgentRuntime.__new__(AgentRuntime);runtime.store=TaskStore(Path(self.tmp.name)/'recover.sqlite3');runtime.lock=threading.RLock();runtime.cancel=threading.Event()
  class Executor:
   calls=[]
   def run(self,tid,action,context,*a):
    self.calls.append((action,copy.deepcopy(context)));return {'success':True,'result':{'context':{'hwnd':999,'pid':888}},'status':'completed'}
  class Log:
   def write(self,*a,**kw):pass
  runtime.executor=Executor();runtime.log=Log();c=dict(self.c,target_app='edge',hwnd=10,pid=20,expected_url='https://video-image-studio.vercel.app/?managerRun='+self.c['studio_run_id']);tid=runtime.store.submit([{'action':'STUDIO_IMAGES'}],context=c);runtime.store.claim(tid);runtime.recover_studio(runtime.store.get(tid));restored=runtime.store.get(tid)['context'];self.assertEqual(restored['studio_run_id'],c['studio_run_id']);self.assertEqual(restored['browser_profile'],'Default');self.assertEqual(restored['hwnd'],999);self.assertEqual([a['action'] for a,_ in runtime.executor.calls],['OPEN_APP','WAIT_WINDOW','FOCUS_WINDOW','NEW_TAB','OPEN_URL']);runtime.store.close()
