import json,tempfile,unittest
from unittest import mock
from automation_agent import story_pipeline as sp
from automation_agent.studio_workflow import StudioStep

SID='b'*32
TRANSCRIPT='Năm 1209 có biến loạn. Họ Trần nổi lên. Trần Thủ Độ nắm quyền. Nhà Lý suy tàn. Nhà Trần lập nghiệp.'

class FakeAPI:
 """Studio server: the rewrite list is the task list; `answer` plays the tabs."""
 def __init__(self):self.s={'id':SID,'parts':[],'script':'old','rewrite':{'sections':[]},'laneJobs':[]};self.posts=[]
 def request(self,sid,route='',body=None):
  if body is not None:
   self.posts.append(route)
   if route=='/rewrite':self.s['rewrite']={'sections':[dict(x,status='waiting',text='') for x in body['sections']]}
   if route=='/script':self.s['script']=body['script']
  return json.loads(json.dumps(self.s))
 def answer(self,fn):
  for x in self.s['rewrite']['sections']:
   if x['status']!='done':x.update(status='done',text=fn(x))

def rows(score):
 return {'rows':[{'id':i,'score':None if i in sp.VISUAL else score(i),'part':None if i in sp.VISUAL else 1,'evidence':'','reason':'r','fix':'f'} for i in range(len(sp.CRITERIA))]}

class StoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.c={'studio_project_id':SID,'studio_run_id':'run','studio_origin':'https://video-image-studio.vercel.app','studio_folder':self.tmp.name,
   'studio_youtube_url':'https://www.youtube.com/watch?v=WziSfyGZsUY','studio_rewrite':True,'studio_rewrite_style':'Giọng kênh'}
  self.api=FakeAPI()
  self.patches=[mock.patch.object(sp,'fetch_transcript',return_value=TRANSCRIPT),mock.patch('automation_agent.studio_workflow.engine_up',return_value=True),
   mock.patch('automation_agent.studio_lanes.rewrite_round',return_value={})]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.tmp.cleanup()
 def step(self):
  w=StudioStep(self.c,self.api,lambda:{'studio_tab_open':True,'chat_connected':True,'session_id':SID,'manager_run_id':'run','origin':self.c['studio_origin']})
  w.post_command=lambda cmd:None;w.ready=lambda:True
  return w,sp.Story(w).step(self.api.request(SID))
 def test_outline_write_review_repair_then_saved(self):
  plan={'plan':{'title':'Trần Thủ Độ: công thần hay kẻ cướp ngôi?','hook':'h','question':'q','promise':'p','tracks':['a','b'],'turns':'t','payoff':'y','ending':'e','sources':'Đại Việt sử ký toàn thư','cover':'c'},
   'branches':[{'title':'Mở đầu','end':2,'role':'hook'},{'title':'Kết','end':5,'role':'cao trào'}]}
  _,r=self.step();self.assertTrue(r['waiting'])
  self.assertIn('DÀN Ý',self.api.s['rewrite']['sections'][0]['prompt'])
  self.api.answer(lambda x:json.dumps(plan))
  _,r=self.step();self.assertTrue(r['waiting'])
  prompts=[x['prompt'] for x in self.api.s['rewrite']['sections']]
  self.assertEqual(len(prompts),2);self.assertIn('PHẦN MỞ ĐẦU',prompts[0]);self.assertIn('bấm theo dõi',prompts[1])
  self.api.answer(lambda x:'Viết lại '+x['id'])
  _,r=self.step()
  self.assertIn('Chấm Aprilynne',self.api.s['rewrite']['sections'][0]['title'])
  self.api.answer(lambda x:json.dumps(rows(lambda i:6 if i==6 else 9)))
  _,r=self.step()
  self.assertTrue(self.api.s['rewrite']['sections'][0]['id'].startswith('fix0'))
  self.assertIn('THỂ HIỆN CÔNG SỨC',self.api.s['rewrite']['sections'][0]['prompt'])
  self.api.answer(lambda x:'Bản sửa có dẫn Đại Việt sử ký toàn thư')
  self.step();self.step()
  self.api.answer(lambda x:json.dumps(rows(lambda i:9)))
  w,r=self.step()
  self.assertIsNone(r)
  self.assertIn('Bản sửa có dẫn',self.api.s['script'])
  self.assertTrue(w.j['aprilynne_done']);self.assertEqual(len(w.j['story_parts']),2)
 def test_rounds_used_up_keep_the_best_or_stop(self):
  story={'stage':'review','tries':{},'round':2,'plan':{'title':'T'},'sections':[{'id':'s1','title':'A','role':'','source':'x'*100,'text':'cuối'}],
   'best':{'passed':8,'texts':['tốt nhất'],'rows':rows(lambda i:9)['rows']}}
  json.dump(story,open(self.tmp.name+'/story.json','w'))
  import os;os.makedirs(self.tmp.name+'/analysis',exist_ok=True);os.replace(self.tmp.name+'/story.json',self.tmp.name+'/analysis/story.json')
  self.step();self.api.answer(lambda x:json.dumps(rows(lambda i:5)))
  with self.assertRaises(RuntimeError):self.step()

if __name__=='__main__':unittest.main()
