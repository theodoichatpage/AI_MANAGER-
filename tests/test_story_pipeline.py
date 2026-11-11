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
 return {'rows':[{'id':i,'score':None if i in sp.VISUAL else score(i),'part':None if i in sp.VISUAL else 1,'evidence':'','reason':'r','fix':'Cắt đoạn lặp ở câu thứ hai'} for i in range(len(sp.CRITERIA))]}

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

 def test_long_script_body_is_read_in_full_chunks_and_every_weak_section_is_repaired(self):
  secs=[{'id':'s%d'%(i+1),'title':'P%d'%(i+1),'role':'','source':'x'*5000,'text':('Câu %d. '%(i+1))*800} for i in range(8)]
  groups=sp.review_groups(secs)
  names=[g for g,_ in groups]
  self.assertEqual(names[0],'open');self.assertEqual(names[-1],'end');self.assertGreaterEqual(len(names),5)
  # Full text, not excerpts, and the whole video's table of contents.
  p=sp.group_prompt(names[1],sp.BODY_IDS,{'title':'T'},secs,'g')
  self.assertIn(secs[0]['text'],p);self.assertIn('TOÀN VĂN',p);self.assertIn('"P8"',p)
  self.assertTrue(all(len(sp.group_prompt(g,ids,{'title':'T'},secs,'g'))<40000 for g,ids in groups))
  # Contrast takes the best chunk, boring passages the worst; the other weak chunk is kept as a finding.
  mk=lambda i,sc,pt:{'id':i,'score':sc,'part':pt,'evidence':'e','reason':'r','fix':'Cắt đoạn lặp'}
  got={'open':[mk(i,9,1) for i in (0,2,3,4,5,7)],'end':[mk(11,9,8),mk(12,9,8)]}
  bodies=names[1:-1]
  for k,g in enumerate(bodies):got[g]=[mk(6,9 if k==0 else 5,k+2),mk(9,7,k+2),mk(10,9,k+2),mk(13,6 if k<2 else 9,k+2)]
  rows,findings=sp.combine(groups,got)
  by={r['id']:r for r in rows}
  self.assertEqual(by[6]['score'],9);self.assertEqual(by[13]['score'],6);self.assertEqual(len(findings),1)
  self.assertEqual(sp.failing_parts(rows,findings),sorted({by[9]['part']-1,2-1,3-1}))
 def test_low_score_without_concrete_fix_is_asked_again(self):
  bad={'rows':[{'id':6,'score':6,'part':1,'evidence':'e','reason':'r','fix':''}]}
  with self.assertRaises(ValueError):sp.accept_group(json.dumps(bad),[6],1)
 def test_repair_names_what_to_keep(self):
  secs=[{'id':'s1','title':'A','role':'','source':'x'*100,'text':'Mở đầu hay. Đoạn lặp.'}]
  rows=[{'id':0,'score':10,'part':1,'evidence':'Mở đầu hay.','reason':'r','fix':''},{'id':13,'score':5,'part':1,'evidence':'Đoạn lặp.','reason':'lặp','fix':'Cắt câu Đoạn lặp'}]
  p=sp.repair_prompt(secs[0],0,1,{'title':'T'},'g',rows,secs)
  self.assertIn('TIÊU CHÍ ĐANG ĐẠT',p);self.assertIn('Mở đầu hay.',p);self.assertIn('Cắt câu Đoạn lặp',p)
 def test_a_worse_round_repairs_again_from_the_best_version(self):
  import os
  story={'stage':'review','tries':{},'round':1,'plan':{'title':'T'},'sections':[{'id':'s1','title':'A','role':'','source':'x'*100,'text':'bản tệ'}],
   'best':{'passed':10,'texts':['bản tốt'],'rows':rows(lambda i:9 if i!=6 else 7)['rows']}}
  os.makedirs(self.tmp.name+'/analysis',exist_ok=True);json.dump(story,open(self.tmp.name+'/analysis/story.json','w'))
  self.step();self.api.answer(lambda x:json.dumps(rows(lambda i:5)))
  w,r=self.step()
  d=json.load(open(self.tmp.name+'/analysis/story.json',encoding='utf8'))
  self.assertEqual(d['stage'],'repair');self.assertEqual(d['sections'][0]['text'],'bản tốt')
  self.assertEqual(d['history'][-1]['passed'],0)
  self.assertIn('bản tốt',self.api.s['rewrite']['sections'][0]['prompt'])

if __name__=='__main__':unittest.main()
