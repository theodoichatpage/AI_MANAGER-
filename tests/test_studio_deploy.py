"""Dự án mới: YouTube -> transcript/rewrite request to the Studio tab; lanes in the workflow; presence lanes."""
import tempfile,unittest
from automation_agent.studio_workflow import StudioStep,workflow
from automation_agent.work_config import normalize
from tests.test_studio_reconcile import FakeAPI,tab as base_tab,SID
def tab(**state):return dict(base_tab(**state),manager_run_id='r'*32)
URL='https://video-image-studio.vercel.app'

class TranscriptPipeline(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=1000.0;self.sent=[]
  self.c={'studio_project_id':SID,'studio_run_id':'r'*32,'studio_origin':URL,'studio_folder':self.tmp.name,'studio_script':'','studio_youtube_url':'https://www.youtube.com/watch?v=abcdefghijk','studio_rewrite':True,'studio_rewrite_style':'Giọng kể chậm'}
  self.presence=tab()
 def tearDown(self):self.tmp.cleanup()
 def step(self,api):
  s=StudioStep(self.c,api,lambda:self.presence,clock=lambda:self.now);s.post_command=self.sent.append;return s
 def test_asks_studio_then_follows_progress_then_continues(self):
  api=FakeAPI({'id':SID,'parts':[],'script':''})
  r=self.step(api).step('STUDIO_TRANSCRIPT');self.assertTrue(r['waiting'])
  cmd=self.sent[-1];self.assertEqual(cmd['type'],'transcript_pipeline');self.assertEqual(cmd['url'],self.c['studio_youtube_url']);self.assertEqual(cmd['style'],'Giọng kể chậm');self.assertTrue(cmd['rewrite'])
  self.presence=tab(pipeline={'id':cmd['id'],'stage':'rewrite','done':3,'total':8})
  r=self.step(api).step('STUDIO_TRANSCRIPT');self.assertIn('3/8',r['context']['studio_message'])
  self.assertEqual(self.sent[-1]['id'],cmd['id'],'same request id while it runs: Studio never restarts it')
  # Studio saved the rewritten script to its server: the step completes, analysis can start.
  api.s['script']='Kịch bản viết lại';self.presence=tab(pipeline={'id':cmd['id'],'stage':'done','done':8,'total':8})
  r=self.step(api).step('STUDIO_TRANSCRIPT');self.assertNotIn('waiting',r);self.assertIn('viết lại',r['context']['studio_transcript_state'])
  self.assertEqual(api.posts,[])
 def test_studio_error_stops_with_clear_message(self):
  api=FakeAPI({'id':SID,'parts':[],'script':''});self.step(api).step('STUDIO_TRANSCRIPT')
  self.presence=tab(pipeline={'id':self.sent[-1]['id'],'stage':'error','error':'Video không có phụ đề'})
  with self.assertRaises(RuntimeError) as e:self.step(api).step('STUDIO_TRANSCRIPT')
  self.assertIn('Video không có phụ đề',str(e.exception))
 def test_retry_sends_a_new_request(self):
  api=FakeAPI({'id':SID,'parts':[],'script':''});self.step(api).step('STUDIO_TRANSCRIPT');first=self.sent[-1]['id']
  self.c['studio_retry_epoch']=1;self.step(api).step('STUDIO_TRANSCRIPT');self.assertNotEqual(self.sent[-1]['id'],first)
 def test_existing_script_skips_the_request(self):
  api=FakeAPI({'id':SID,'parts':[],'script':'Đã có'});r=self.step(api).step('STUDIO_TRANSCRIPT')
  self.assertEqual(self.sent,[]);self.assertNotIn('waiting',r)

class WorkflowLanes(unittest.TestCase):
 def test_lanes_add_open_and_parallel_steps(self):
  cfg=normalize({'tasks':['analysis','scenes','images'],'lanes':[{'browser':'edge','profile':'Default'},{'browser':'edge','profile':'Profile 1'}]})
  actions,ctx=workflow(SID,URL,'edge','Default','.','',context={'studio_youtube_url':'https://youtu.be/abcdefghijk'},work_config=cfg,stages=['analysis','images'],name='Dự án A')
  names=[a['action'] for a in actions]
  self.assertEqual(names[names.index('STUDIO_READY')+1:],['STUDIO_LANES','STUDIO_TRANSCRIPT','STUDIO_ANALYZE','STUDIO_PARALLEL'])
  launch=ctx['studio_launch_url'];self.assertEqual(names[:2],['STUDIO_OPEN','STUDIO_READY'],'Edge is launched with the URL, nothing typed')
  self.assertIn('managerStage=transcript',launch);self.assertIn('managerName=',launch)
 def test_single_lane_keeps_the_proven_sequential_steps(self):
  actions,_=workflow(SID,URL,'edge','Default','.','',work_config=normalize({'tasks':['analysis','scenes']}))
  names=[a['action'] for a in actions];self.assertIn('STUDIO_SCENES',names);self.assertNotIn('STUDIO_PARALLEL',names)
 def test_lane_rules(self):
  with self.assertRaises(ValueError):normalize({'tasks':['scenes'],'lanes':[{'browser':'edge','profile':'Default'},{'browser':'edge','profile':'Default'}]})
  with self.assertRaises(ValueError):normalize({'tasks':['scenes'],'lanes':[{'browser':'edge','profile':'../x'}]})
  with self.assertRaises(ValueError):workflow(SID,URL,'edge','Default','.','',work_config=normalize({'tasks':['scenes'],'lanes':[{'browser':'edge','profile':'Profile 2'},{'browser':'edge','profile':'Default'}]}))

class PresenceLanes(unittest.TestCase):
 def test_workers_and_commands(self):
  import server
  p=server.StudioPresence()
  base={'sessionId':SID,'managerRunId':'r'*32,'chatReady':True}
  p.update(dict(base,tabId='t1',worker={'laneId':'lane_a1','extensionVersion':'0.5.0','account':{'key':'abc123','plan':'plus','label':'a***@gmail.com'},'chatTabs':1}))
  p.update(dict(base,tabId='t2',worker={'laneId':'bad id!'}))
  rows=p.snapshot(SID)['workers'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['account_plan'],'plus');self.assertNotIn('email',str(rows[0]))
  self.assertIsNone(p.pending(base));p.command(SID,'r'*32,{'type':'transcript_pipeline','id':'x'});self.assertEqual(p.pending(base)['id'],'x')
  self.assertIsNone(p.pending(dict(base,managerRunId='z'*32)),'another run never receives it')
if __name__=='__main__':unittest.main()

class LaunchOpen(unittest.TestCase):
 def test_studio_is_launched_then_relaunched_only_while_missing(self):
  from automation_agent import studio_lanes
  opened=[];orig=studio_lanes.open_lane;studio_lanes.open_lane=lambda lane,url,launch=None:opened.append((lane['profile'],url))
  try:
   tmp=tempfile.TemporaryDirectory();now=[1000.0];pres=[{'studio_tab_open':False}]
   c={'studio_project_id':SID,'studio_run_id':'r'*32,'studio_origin':URL,'studio_folder':tmp.name,'studio_launch':True,'studio_launch_url':URL+'/?managerProject='+SID,'browser_profile':'Profile 1'}
   mk=lambda:StudioStep(c,FakeAPI({'id':SID,'parts':[]}),lambda:pres[0],clock=lambda:now[0])
   self.assertNotIn('waiting',mk().step('STUDIO_OPEN'));self.assertEqual(opened,[('Profile 1',c['studio_launch_url'])])
   self.assertTrue(mk().step('STUDIO_READY')['waiting']);self.assertEqual(len(opened),1,'no second window right away')
   now[0]+=130;mk().step('STUDIO_READY');self.assertEqual(len(opened),2,'tab still missing after 2 minutes: launch again')
   tmp.cleanup()
  finally:studio_lanes.open_lane=orig
