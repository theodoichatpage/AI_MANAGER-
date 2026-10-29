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
