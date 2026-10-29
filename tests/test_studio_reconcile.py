import copy,hashlib,json,tempfile,threading,unittest
from pathlib import Path
from automation_agent import studio_workflow
from automation_agent.studio_workflow import StudioStep,StudioScriptMissing,workflow
from automation_agent.studio_reconcile import reconcile,validate,prepare_resume,is_script_error
SID='b'*32
class FakeAPI:
 def __init__(self,s):self.s=s;self.posts=[]
 def request(self,sid,route='',body=None):
  if body is not None:
   self.posts.append((route,body));self.s['activeJob']={'id':'job'+str(len(self.posts)),'type':'script_structure'}
  return copy.deepcopy(self.s)
def tab(**state):
 base={'studio_tab_open':True,'chat_connected':True,'session_id':SID,'manager_run_id':'run','origin':'https://video-image-studio.vercel.app'}
 if state is not None:base['project_state']=dict({'script_draft_characters':0,'script_server_characters':0,'transcript_exists':False,'transcript_characters':0},**state)
 return base

class ScriptReconcileTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=1000.0
  self.c={'studio_project_id':SID,'studio_run_id':'run','studio_origin':'https://video-image-studio.vercel.app','studio_folder':self.tmp.name,'studio_script':''}
  self.presence=tab()
 def tearDown(self):self.tmp.cleanup()
 def step(self,api):return StudioStep(self.c,api,lambda:self.presence,clock=lambda:self.now)

 def test_missing_script_waits_then_resumes_when_user_adds_it_in_studio(self):
  api=FakeAPI({'id':SID,'parts':[],'script':'','status':'stopped','workEpoch':1})
  r=self.step(api).step('STUDIO_ANALYZE')
  self.assertTrue(r['waiting']);self.assertEqual(r['context']['studio_error_code'],'SCRIPT_MISSING');self.assertEqual(api.posts,[])
  # The user types the script in Studio: draft is reported first, then Studio saves it to its server.
  self.presence=tab(script_draft_characters=4200);self.now+=5
  r=self.step(api).step('STUDIO_ANALYZE');self.assertEqual(r['context']['studio_error_code'],'SCRIPT_NOT_SYNCED');self.assertEqual(api.posts,[])
  api.s['script']='Nguyễn Du '*420;self.now+=5
  r=self.step(api).step('STUDIO_ANALYZE')
  self.assertTrue(r['waiting']);self.assertEqual([p[0] for p in api.posts],['/analysis']);self.assertEqual(api.posts[0][1]['script'],api.s['script'].strip());self.assertEqual(api.posts[0][1]['expectedWorkEpoch'],1)
  # SAVE -> VERIFY -> CHECKPOINT of the exact Studio script.
  saved=Path(self.tmp.name,'analysis','studio_script.txt').read_text(encoding='utf8')
  journal=json.loads(Path(self.tmp.name,'analysis','manager_run.json').read_text(encoding='utf8'))
  self.assertEqual(journal['script']['sha256'],hashlib.sha256(saved.encode('utf8')).hexdigest());self.assertEqual(saved,api.s['script'].strip())

 def test_unowned_shared_draft_asks_user_and_never_posts(self):
  api=FakeAPI({'id':SID,'parts':[],'script':''});self.presence=tab(script_draft_characters=300,script_sync='unconfirmed')
  r=self.step(api).step('STUDIO_ANALYZE');self.assertIn('Lưu kịch bản này cho AI MANAGER',r['context']['studio_message']);self.assertEqual(api.posts,[])

 def test_script_wait_is_bounded_and_reports_script_missing(self):
  api=FakeAPI({'id':SID,'parts':[],'script':''});self.step(api).step('STUDIO_ANALYZE')
  self.now+=studio_workflow.SCRIPT_WAIT+1
  with self.assertRaises(StudioScriptMissing) as e:self.step(api).step('STUDIO_ANALYZE')
  self.assertIn('SCRIPT_MISSING',str(e.exception));self.assertEqual(api.posts,[])

 def test_retry_epoch_gets_fresh_script_wait(self):
  api=FakeAPI({'id':SID,'parts':[],'script':''});self.step(api).step('STUDIO_ANALYZE')
  self.now+=studio_workflow.SCRIPT_WAIT+1;self.c['studio_retry_epoch']=1
  self.assertTrue(self.step(api).step('STUDIO_ANALYZE')['waiting'])

 def test_manager_project_script_is_still_a_fallback(self):
  self.c['studio_script']='Kịch bản trong Manager'
  api=FakeAPI({'id':SID,'parts':[],'script':''});self.step(api).step('STUDIO_ANALYZE')
  self.assertEqual(api.posts[0][1]['script'],'Kịch bản trong Manager')

 def test_transcript_step_follows_real_state(self):
  api=FakeAPI({'id':SID,'parts':[],'script':''})
  self.assertTrue(self.step(api).step('STUDIO_TRANSCRIPT')['waiting'])
  self.presence=tab(transcript_exists=True,transcript_characters=9000)
  r=self.step(api).step('STUDIO_TRANSCRIPT');self.assertNotIn('waiting',r);self.assertIn('Transcript đã có',r['context']['studio_transcript_state'])
  self.presence=tab();api.s['script']='Script'
  self.assertIn('Kịch bản đã có',self.step(api).step('STUDIO_TRANSCRIPT')['context']['studio_transcript_state'])
  api.s['parts']=[{'id':'p1','status':'complete','scenes':[{}]}]
  self.assertIn('đã phân tích',self.step(api).step('STUDIO_TRANSCRIPT')['context']['studio_transcript_state'])
  self.assertEqual(api.posts,[])

 def test_completed_analysis_and_parts_are_not_rerun(self):
  api=FakeAPI({'id':SID,'parts':[{'id':'p1','status':'complete','scenes':[{'prompt':'x'}]}],'script':'S'})
  self.step(api).step('STUDIO_TRANSCRIPT');self.step(api).step('STUDIO_ANALYZE');self.step(api).step('STUDIO_SCENES')
  self.assertEqual(api.posts,[])

 def test_workflow_runs_transcript_before_analysis(self):
  actions,_=workflow(SID,'https://video-image-studio.vercel.app','edge','Default',self.tmp.name,'')
  names=[a['action'] for a in actions];self.assertLess(names.index('STUDIO_TRANSCRIPT'),names.index('STUDIO_ANALYZE'))
  actions,_=workflow(SID,'https://video-image-studio.vercel.app','edge','Default',self.tmp.name,'',stages=['images'])
  self.assertNotIn('STUDIO_TRANSCRIPT',[a['action'] for a in actions])

class ManualStudioWorkTests(unittest.TestCase):
 """The user runs analysis by hand in Studio: Manager observes, never sends, then continues."""
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=1000.0
  self.c={'studio_project_id':SID,'studio_run_id':'run','studio_origin':'https://video-image-studio.vercel.app','studio_folder':self.tmp.name,'studio_script':''}
 def tearDown(self):self.tmp.cleanup()
 def step(self,api):return StudioStep(self.c,api,lambda:tab(),clock=lambda:self.now)
 def test_user_structure_job_is_observed_then_manager_continues_with_parts(self):
  api=FakeAPI({'id':SID,'parts':[],'script':'S','activeJob':{'id':'userjob','type':'script_structure','status':'waiting'}})
  self.assertTrue(self.step(api).step('STUDIO_READY')['context']['studio_ready'])
  r=self.step(api).step('STUDIO_ANALYZE');self.assertTrue(r['waiting']);self.assertEqual(r['context']['studio_external_job'],'userjob');self.assertEqual(api.posts,[])
  api.s.update(activeJob=None,parts=[{'id':'p1','status':'complete','scenes':[{'prompt':'a'}]},{'id':'p2','status':'ready','scenes':[]}])
  r=self.step(api).step('STUDIO_ANALYZE');self.assertNotIn('waiting',r);self.assertIsNone(r['context']['studio_message'])
  self.step(api).step('STUDIO_SCENES');self.assertEqual([p[0] for p in api.posts],['/parts/p2/analysis'])
 def test_user_part_job_and_studio_batch_are_observed(self):
  api=FakeAPI({'id':SID,'script':'S','parts':[{'id':'p1','status':'processing','scenes':[]},{'id':'p2','status':'ready','scenes':[]}],'activeJob':{'id':'u2','type':'part_analysis','partId':'p1'}})
  self.assertTrue(self.step(api).step('STUDIO_SCENES')['waiting'])
  api.s.update(activeJob=None,batchAnalysis=True,analysisQueue=['p2']);api.s['parts'][0]['status']='complete';api.s['parts'][0]['scenes']=[{'prompt':'a'}]
  self.assertTrue(self.step(api).step('STUDIO_SCENES')['waiting']);self.assertEqual(api.posts,[])
 def test_lost_chatgpt_waits_longer_while_studio_job_runs(self):
  api=FakeAPI({'id':SID,'script':'S','parts':[{'id':'p1','status':'processing','scenes':[]}],'activeJob':{'id':'u','type':'part_analysis','partId':'p1'}})
  st=StudioStep(self.c,api,lambda:dict(tab(),chat_connected=False),clock=lambda:self.now)
  self.assertTrue(st.step('STUDIO_SCENES')['waiting']);self.now+=600
  self.assertTrue(StudioStep(self.c,api,lambda:dict(tab(),chat_connected=False),clock=lambda:self.now).step('STUDIO_SCENES')['waiting'])
  api.s['activeJob']=None;self.now+=1
  with self.assertRaises(TimeoutError):StudioStep(self.c,api,lambda:dict(tab(),chat_connected=False),clock=lambda:self.now).step('STUDIO_SCENES')
  self.assertEqual(api.posts,[])
 def test_unknown_job_still_needs_review(self):
  from automation_agent.studio_workflow import StudioReviewRequired
  api=FakeAPI({'id':SID,'parts':[],'script':'S','activeJob':{'id':'x','type':'something_else'}})
  with self.assertRaises(StudioReviewRequired):self.step(api).step('STUDIO_READY')

class ResumeTests(unittest.TestCase):
 def task(self,error='Dự án chưa có kịch bản'):
  names=['OPEN_APP','WAIT_WINDOW','FOCUS_WINDOW','NEW_TAB','OPEN_URL','WAIT_PAGE','STUDIO_READY','STUDIO_ANALYZE','STUDIO_SCENES']
  return {'actions':[{'action':n} for n in names],'next_action':7,'error':error,'context':{'hwnd':1,'pid':2,'studio_project_id':SID}}
 def test_reconcile_facts(self):
  f=reconcile({'parts':[],'script':'  abc  '},tab(script_draft_characters=10))
  self.assertTrue(f['script_content_exists']);self.assertEqual(f['script_character_count'],3);self.assertEqual(f['script_source'],'studio_server')
  f=reconcile({'parts':[],'script':''},tab(script_draft_characters=10));self.assertEqual(f['script_source'],'studio_draft')
  f=reconcile({'parts':[],'script':''},{'studio_tab_open':False});self.assertFalse(f['script_content_exists']);self.assertFalse(f['transcript_known'])
  self.assertEqual(validate(f,'STUDIO_ANALYZE')[0],'SCRIPT_MISSING');self.assertEqual(validate(f,'STUDIO_SCENES'),(None,None))
 def test_resolved_script_resumes_from_studio_ready(self):
  t=self.task();f=reconcile({'parts':[],'script':'abc'},tab())
  self.assertEqual(prepare_resume(t,f,True),6);self.assertIsNone(t['error']);self.assertEqual(t['context']['studio_resolved_error'],'SCRIPT_MISSING');self.assertEqual(t['context']['hwnd'],1)
 def test_closed_studio_tab_reopens_same_run(self):
  t=self.task();f=reconcile({'parts':[],'script':'abc'},{})
  self.assertEqual(prepare_resume(t,f,False),0);self.assertNotIn('hwnd',t['context'])
 def test_running_studio_job_keeps_checkpoint(self):
  t=self.task();f=reconcile({'parts':[],'script':'abc','activeJob':{'type':'script_structure'}},tab())
  self.assertEqual(prepare_resume(t,f,True),7)
 def test_running_job_with_closed_tab_reopens_tab_without_sending(self):
  t=self.task();f=reconcile({'parts':[],'script':'abc','activeJob':{'type':'part_analysis'}},{})
  self.assertEqual(prepare_resume(t,f,False),0);self.assertNotIn('hwnd',t['context'])
 def test_needs_review_resumable_only_without_unknown_post(self):
  import json as _json
  from automation_agent.manager_service import AutomationService
  with tempfile.TemporaryDirectory() as d:
   c={'studio_project_id':SID,'studio_run_id':'run','studio_folder':d}
   task={'context':c,'current_action':'STUDIO_SCENES'}
   p=Path(d,'analysis','manager_run.json');p.parent.mkdir(parents=True)
   p.write_text(_json.dumps({'commands':{'part:a#0':{'state':'accepted','job_id':'j'}}}),encoding='utf8')
   self.assertTrue(AutomationService.review_resolvable(None,task))
   p.write_text(_json.dumps({'commands':{'part:b#0':{'state':'intent'}}}),encoding='utf8')
   self.assertFalse(AutomationService.review_resolvable(None,task))
   self.assertFalse(AutomationService.review_resolvable(None,dict(task,current_action='CLICK')))
 def test_paused_time_does_not_expire_watchdog_after_resume(self):
  with tempfile.TemporaryDirectory() as d:
   c={'studio_project_id':SID,'studio_run_id':'run','studio_origin':'https://video-image-studio.vercel.app','studio_folder':d}
   api=FakeAPI({'id':SID,'parts':[],'script':'S','activeJob':{'id':'u','type':'script_structure'}})
   StudioStep(c,api,lambda:tab(),clock=lambda:1000).step('STUDIO_ANALYZE')
   c['studio_resumed_at']=5000
   self.assertTrue(StudioStep(c,api,lambda:tab(),clock=lambda:5100).step('STUDIO_ANALYZE')['waiting'])
 def test_script_error_detection(self):
  self.assertTrue(is_script_error('Dự án chưa có kịch bản'));self.assertTrue(is_script_error('SCRIPT_MISSING: x'));self.assertFalse(is_script_error('Studio lỗi'))

class BridgeStaleSnapshotTests(unittest.TestCase):
 def test_old_failed_snapshot_is_not_applied_after_retry(self):
  from automation_agent.queue_bridge import QueueBridge
  updates=[]
  class Q:
   lock=threading.RLock()
   def list(self):return [{'id':'p','status':'running','execution_mode':'automation','automation_task_id':'t','running_since':200.0,'folder':tempfile.gettempdir()}]
   def automation_update(self,*a):updates.append(a)
   def studio_progress(self,*a):pass
   def pause(self,*a):pass
  class A:
   def snapshot(self):return {'online':True,'tasks':[{'id':'t','status':'failed','error':'Dự án chưa có kịch bản','updated_at':100.0,'context':{},'next_action':7,'actions':[]}]}
  b=QueueBridge(Q(),A())
  try:
   import time;time.sleep(1.2)
  finally:b.close()
  self.assertEqual(updates,[])

class BridgeOfflineAndCompletionTests(unittest.TestCase):
 def make(self,tasks,online):
  from automation_agent import queue_bridge
  calls=[]
  class Q:
   lock=threading.RLock()
   def list(self):return [{'id':'p','status':'running','execution_mode':'automation','automation_task_id':'t','running_since':200.0,'folder':tempfile.gettempdir()}]
   def pause(self,pid):calls.append('pause')
   def automation_update(self,*a):calls.append(('update',a[4]))
   def studio_progress(self,*a):pass
  class A:
   def snapshot(self):return {'online':online[0],'tasks':tasks}
  now=[0.0]
  b=queue_bridge.QueueBridge.__new__(queue_bridge.QueueBridge)
  b.queue=Q();b.agent=A();b.clock=lambda:now[0];b.offline_since=None;b.stop_event=threading.Event()
  return b,calls,now
 def run_once(self,b):
  import types
  b.stop_event=types.SimpleNamespace(wait=lambda s,n=[0]:(n.__setitem__(0,n[0]+1),n[0]>1)[1])
  b.loop()
 def test_short_agent_hiccup_does_not_pause(self):
  online=[False];b,calls,now=self.make([],online)
  self.run_once(b);now[0]=10;self.run_once(b);self.assertEqual(calls,[])
  now[0]=31;self.run_once(b);self.assertEqual(calls,['pause'])
 def test_completion_after_queue_pause_is_recorded(self):
  b,calls,now=self.make([{'id':'t','status':'completed','updated_at':100.0,'context':{},'next_action':9,'actions':[1]*9}],[True])
  self.run_once(b);self.assertIn(('update','completed'),calls)
 def test_old_failure_still_ignored(self):
  b,calls,now=self.make([{'id':'t','status':'failed','error':'old','updated_at':100.0,'context':{},'next_action':7,'actions':[1]*9}],[True])
  self.run_once(b);self.assertEqual(calls,[])

class PresenceStateTests(unittest.TestCase):
 def test_presence_keeps_counts_only(self):
  from server import StudioPresence
  p=StudioPresence(ttl=15)
  p.update({'sessionId':SID,'tabId':'t1','projectState':{'scriptDraftChars':4200,'serverScriptChars':0,'scriptSync':'pending','transcript':{'exists':True,'chars':900,'segments':12,'videoId':'abc'},'script':'SECRET TEXT'}})
  s=p.snapshot(SID)['project_state']
  self.assertEqual(s['script_draft_characters'],4200);self.assertTrue(s['transcript_exists']);self.assertNotIn('SECRET TEXT',json.dumps(s))
  p.update({'sessionId':SID,'tabId':'t1','projectState':{'scriptDraftChars':'x'}});self.assertEqual(p.snapshot(SID)['project_state']['script_draft_characters'],0)
  p.update({'sessionId':SID,'tabId':'t1'});self.assertIsNone(p.snapshot(SID)['project_state'])

if __name__=='__main__':unittest.main()

class ExtensionDiagnosticTests(unittest.TestCase):
 def test_diagnostic_kept_short_and_flat(self):
  from extension_monitor import ExtensionMonitor
  m=ExtensionMonitor()
  self.assertTrue(m.receive('pair',{'pairCode':'pair','identityVersion':1,'lastHeartbeatAt':1000,'diagnostic':{'sync':'x'*999,'capture':{'ok':False,'error':'Chưa tìm thấy ảnh','at':5},'watch':{'reloads':2,'gaveUp':True},'bad':{'a':{'b':{'c':1}}}}},now=1.0))
  d=m.snapshot('pair',now=2.0)['diagnostic']
  self.assertEqual(len(d['sync']),300);self.assertEqual(d['capture']['error'],'Chưa tìm thấy ảnh');self.assertEqual(d['watch']['reloads'],2);self.assertIsNone(d['bad']['a'])
