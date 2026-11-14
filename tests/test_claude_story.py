import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
from automation_agent import claude_story as cs
from automation_agent.studio_workflow import StudioStep

SID='c'*32
ROOT=cs.tool_root()
HAVE_TOOL=(ROOT/'aprilinne'/'studio.py').is_file()

class FakeAPI:
 def __init__(self):self.s={'id':SID,'parts':[],'script':'old','rewrite':{'sections':[]},'laneJobs':[]};self.posts=[]
 def request(self,sid,route='',body=None):
  if body is not None:
   self.posts.append(route)
   if route=='/script':self.s['script']=body['script']
  return json.loads(json.dumps(self.s))

def graded_run(folder,approved=True):
 """A finished Claude run written with the real tool: two acts, both lines, a checked scorecard."""
 a=cs._tool(ROOT)
 import aprilinne.grade as G
 effort='Em đã dành 1000 giờ đọc Đại Việt sử ký toàn thư và Minh thực lục, và thấy chuyện sách giáo khoa không kể.'
 script=('## Hồi 1 — Mở\n\nPhía nhà Minh ra đòn thứ nhất bằng lá cờ phù Trần. Giai thoại lá cây kiến ăn chữ.\n\n'+effort+'\n\nLê Lợi dựng cờ ở Lam Sơn với hai nghìn quân. Các bác cho em xin một like nha.'
  '\n\n## Hồi 2 — Kết\n\nLê Lợi thắng ở Chi Lăng nhờ trận phục kích.\n\nPhía nhà Minh đòi lập Trần Cảo làm vua. Giai thoại Trần Cảo uống thuốc độc. Cho em xin một lượt theo dõi kênh nhé.')
 crit={k:{'diem':9 if approved else 5,'bang_chung':[{'hoi':1,'trich':'Lê Lợi dựng cờ ở Lam Sơn với hai nghìn quân'}],'ly_do':'r','cach_sua':''} for k in G.ALL}
 reply={'tuyen_A':'chiến trường','tuyen_B':'chính danh','doi_luc':'d',
  'doan':[{'tuyen':'B','mo_dau':'Phía nhà Minh ra đòn thứ nhất'},{'tuyen':'chung','mo_dau':'Em đã dành 1000 giờ đọc'},{'tuyen':'A','mo_dau':'Lê Lợi dựng cờ ở Lam Sơn'},
   {'tuyen':'A','mo_dau':'Lê Lợi thắng ở Chi Lăng'},{'tuyen':'B','mo_dau':'Phía nhà Minh đòi lập Trần Cảo'}],
  'ngoai_truyen':[{'hoi':1,'trich':'Giai thoại lá cây kiến ăn chữ'},{'hoi':2,'trich':'Giai thoại Trần Cảo uống thuốc độc'}],'phan_rieng_giai_thoai':[],
  'dau_tu':{'trich':effort,'bo_su':['Đại Việt sử ký toàn thư','Minh thực lục'],'trung_tuyen_B':True},'tieu_chi':crit,'su_that':[]}
 card=G.evaluate(script,reply)
 d=cs.runs_dir(folder)/cs.RUN;(d/'vong1').mkdir(parents=True)
 (d/'vong1'/'kich_ban.md').write_text(script,encoding='utf8');(d/'vong1'/'cham.json').write_text(json.dumps(card,ensure_ascii=False),encoding='utf8')
 (d/'state.json').write_text(json.dumps({'ten':'run','buoc':'xong','vong':1,'tot_nhat':1,'che_do':'video_dai','lich_su':[{'vong':1,'duyet':card['duyet']}]}),encoding='utf8')
 return card

class ClaudeStoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.c={'studio_project_id':SID,'studio_run_id':'run','studio_origin':'https://video-image-studio.vercel.app','studio_folder':self.tmp.name,
   'studio_youtube_url':'https://www.youtube.com/watch?v=Tncu7b9e4N0','studio_rewrite':True,'studio_story_engine':'claude','studio_story_mode':'video_dai',
   'studio_channel_name':'Kênh Sử','studio_story_note':'Nhấn mạnh Nguyễn Trãi','studio_aprilinne_root':str(ROOT)}
  self.api=FakeAPI();self.spawned=[]
  self.patches=[mock.patch('automation_agent.story_pipeline.fetch_transcript',return_value='Lê Lợi dựng cờ ở Lam Sơn.'),
   mock.patch('automation_agent.studio_workflow.engine_up',return_value=True),
   mock.patch.object(cs.ClaudeStory,'spawn',lambda me,args:(self.spawned.append(args),me.meta.update(pid=4242),me.save_meta())),
   mock.patch.object(cs,'process_alive',side_effect=lambda pid:self.alive)]
  self.alive=False
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.tmp.cleanup()
 def step(self,script=None):
  w=StudioStep(self.c,self.api,lambda:{'studio_tab_open':True,'chat_connected':True,'session_id':SID,'manager_run_id':'run','origin':self.c['studio_origin']})
  w.post_command=lambda cmd:None;w.ready=lambda:True
  return w,cs.ClaudeStory(w,script=script).step(self.api.request(SID))
 def write_state(self,**st):
  d=cs.runs_dir(self.tmp.name)/cs.RUN;d.mkdir(parents=True,exist_ok=True)
  (d/'state.json').write_text(json.dumps(dict({'ten':'run','vong':0,'che_do':'video_dai'},**st)),encoding='utf8')

 def test_engine_defaults_to_chatgpt(self):
  self.assertEqual(cs.engine({}),'chatgpt');self.assertEqual(cs.engine({'studio_story_engine':'claude'}),'claude')

 def test_start_hands_transcript_and_settings_to_the_tool(self):
  _,r=self.step();self.assertTrue(r['waiting'])
  args=self.spawned[0]
  self.assertEqual(args[:2],['moi','run']);self.assertIn('cli',args)
  self.assertEqual(args[args.index('--che-do')+1],'video_dai');self.assertEqual(args[args.index('--kenh')+1],'Kênh Sử')
  self.assertEqual(args[args.index('--ghi-chu')+1],'Nhấn mạnh Nguyễn Trãi')
  self.assertEqual(Path(args[args.index('--transcript')+1]).read_text(encoding='utf8'),'Lê Lợi dựng cờ ở Lam Sơn.')
  self.assertEqual(self.api.posts,[])   # no ChatGPT task list, nothing sent to Studio yet

 def test_pasted_script_is_the_source(self):
  self.step(script='Kịch bản dán sẵn.')
  self.assertEqual(Path(self.spawned[0][self.spawned[0].index('--transcript')+1]).read_text(encoding='utf8'),'Kịch bản dán sẵn.')

 def test_waits_while_running_and_resumes_a_stopped_run(self):
  self.write_state(buoc='cham',vong=2);self.alive=True
  _,r=self.step();self.assertTrue(r['waiting']);self.assertIn('chấm · vòng 2',r['context']['studio_message']);self.assertEqual(self.spawned,[])
  self.alive=False
  _,r=self.step();self.assertEqual(self.spawned[-1],['chay','run','--may','cli']);self.assertIn('chạy tiếp lần 1',r['context']['studio_message'])
  for _ in range(cs.TRIES-1):self.step()
  with self.assertRaises(RuntimeError):self.step()

 def test_not_logged_in_is_said_plainly(self):
  self.write_state(buoc='dan_y')
  (cs.runs_dir(self.tmp.name)/'chay.log').write_text('RuntimeError: Claude Code báo lỗi: Not logged in · Please run /login',encoding='utf8')
  with self.assertRaisesRegex(RuntimeError,'chưa đăng nhập'):self.step()

 @unittest.skipUnless(HAVE_TOOL,'CAU_TRUC_APRILINNE chưa có trên máy')
 def test_approved_script_goes_to_studio_as_parts(self):
  graded_run(self.tmp.name)
  w,r=self.step();self.assertIsNone(r)
  self.assertEqual(self.api.posts,['/script']);self.assertTrue(w.j['aprilynne_done'])
  self.assertEqual([p['title'] for p in w.j['story_parts']],['Mở','Kết'])
  self.assertTrue(self.api.s['script'].startswith('Phía nhà Minh ra đòn'));self.assertNotIn('## Hồi',self.api.s['script'])

 @unittest.skipUnless(HAVE_TOOL,'CAU_TRUC_APRILINNE chưa có trên máy')
 def test_not_approved_stops_with_the_failing_criteria(self):
  graded_run(self.tmp.name,approved=False)
  with self.assertRaisesRegex(RuntimeError,'chưa đạt'):self.step()
  self.assertEqual(self.api.posts,[])

 @unittest.skipUnless(HAVE_TOOL,'CAU_TRUC_APRILINNE chưa có trên máy')
 def test_story_review_serves_the_claude_run(self):
  import server
  graded_run(self.tmp.name);server._STORY_CACHE.clear()
  with mock.patch.object(server,'studio_project_folder',return_value=self.tmp.name):
   rep=server.story_review('e6ae3139a690474ca5db6654cdc5f9b5')
  self.assertEqual(rep['engine'],'aprilinne');self.assertEqual(rep['che_do'],'video_dai')
  self.assertEqual(len(rep['vong_cham']),1);self.assertEqual(rep['vong_cham'][0]['kich_ban'][0]['ten'],'Mở')

 def test_story_settings_only_for_claude(self):
  import server
  self.assertEqual(server.story_settings({}),{})
  self.assertEqual(server.story_settings({'story_engine':'claude','story_mode':'series','channel_name':'K'}),
   {'studio_story_engine':'claude','studio_story_mode':'series','studio_rewrite':True,'studio_channel_name':'K'})

 def test_project_inputs_validate_story_settings(self):
  import project_ops
  out=project_ops.inputs({'story_engine':'x','story_mode':'series','channel_name':' K ','story_note':'n'})
  self.assertEqual(out,{'story_engine':'chatgpt','story_mode':'series','channel_name':'K','story_note':'n'})

class ChatGptWaitTests(unittest.TestCase):
 """A Claude project needs no ChatGPT until its script is approved; a ChatGPT project always does."""
 def step(self,c,j=None,chat=False):
  presence={'studio_tab_open':True,'chat_connected':chat,'session_id':SID,'manager_run_id':'run','origin':'https://video-image-studio.vercel.app'}
  with tempfile.TemporaryDirectory() as folder:
   c=dict({'studio_project_id':SID,'studio_run_id':'run','studio_origin':presence['origin'],'studio_folder':folder},**c)
   w=StudioStep(c,FakeAPI(),lambda:presence)
   w.j.update(j or {})
   return bool(w.ready()),w.chat_needed()
 def test_claude_story_runs_without_chatgpt(self):
  self.assertEqual(self.step({'studio_story_engine':'claude'}),(True,False))
 def test_after_the_claude_script_chatgpt_is_needed_again(self):
  self.assertEqual(self.step({'studio_story_engine':'claude'},{'aprilynne_done':True}),(False,True))
  self.assertEqual(self.step({'studio_story_engine':'claude'},{'aprilynne_done':True},chat=True),(True,True))
 def test_chatgpt_project_still_waits_for_chatgpt(self):
  self.assertEqual(self.step({}),(False,True))

if __name__=='__main__':unittest.main()
