"""Parallel ChatGPT lanes: allocation, hand-back from lost lanes, limits and warnings (no real browser)."""
import tempfile,unittest
from pathlib import Path
from automation_agent import studio_lanes
from automation_agent.studio_lanes import step,live_lanes,warnings,open_step

def worker(lane,label=None,key=None,plan='plus',tabs=1,version='0.5.0',connected=True,dispatcher=True,seen=0):
 return {'lane_id':lane,'account_label':label or lane,'account_key':key,'account_plan':plan,'chat_tabs':tabs,'extension_version':version,'chat_connected':connected,'dispatcher':dispatcher,'seen':seen,'extension_job':''}

class FakeStudio:
 """Lane semantics of the Studio server: one job per lane, idempotent per (lane,target), release."""
 def __init__(self,parts=4,scenes=2):
  self.s={'id':'s'*16,'workEpoch':0,'stylePrompt':'Style {{SCENE_PROMPT}}','parts':[{'id':'p%d'%i,'title':'Phần %d'%i,'status':'ready','scenes':[]} for i in range(1,parts+1)],'laneJobs':[],'laneLast':{}}
  self.scenes=scenes;self.n=0;self.posts=[]
 def post(self,route,body):
  self.posts.append(route);bits=route.strip('/').split('/');lane=bits[1]
  if bits[2]=='release':
   self.s['laneJobs']=[j for j in self.s['laneJobs'] if j['id']!=body['jobId']];return {'released':True}
  busy=[j for j in self.s['laneJobs'] if j['lane']==lane]
  if busy:raise RuntimeError('409 Tab ChatGPT này đang bận.')
  self.n+=1;job={'id':'job%d'%self.n,'lane':lane}
  if bits[2]=='parts':
   if any(j.get('partId')==bits[3] for j in self.s['laneJobs']):raise RuntimeError('409 đang được tab khác')
   job.update(type='part_analysis',partId=bits[3]);self.part(bits[3])['status']='processing'
  else:
   job.update(type='image_generation',sceneKey=body['sceneKey'])
  self.s['laneJobs'].append(job);return {'command':job}
 def part(self,pid):return next(p for p in self.s['parts'] if p['id']==pid)
 def job(self,lane):return next((j for j in self.s['laneJobs'] if j['lane']==lane),None)
 def finish(self,lane,ok=True,error='ChatGPT lỗi'):
  j=self.job(lane);self.s['laneJobs'].remove(j)
  self.s['laneLast'][lane]={'jobId':j['id'],'type':j['type'],'status':'completed' if ok else 'error','partId':j.get('partId'),'sceneKey':j.get('sceneKey'),'error':'' if ok else error}
  if j['type']=='part_analysis':
   p=self.part(j['partId'])
   if ok:p.update(status='complete',scenes=[{'prompt':'scene %d'%i,'imageStatus':'waiting'} for i in range(self.scenes)])
   else:p['status']='error'
  else:
   pid,i=j['sceneKey'].rsplit(':',1);sc=self.part(pid)['scenes'][int(i)]
   if ok:sc.update(imageStatus='complete',imageResults=[{'url':'https://x/'+j['sceneKey']}])
   else:sc['imageStatus']='error'
  return j

class W:
 def __init__(self,studio,workers,tasks=('analysis','scenes'),retry=1,lanes=None):
  self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name);self.sid='s'*16;self.j={'commands':{},'stages':{}}
  self.c={'studio_run_id':'r'*32,'studio_origin':'https://video-image-studio.vercel.app','project_name':'Dự án',
   'work_config':{'tasks':list(tasks),'scopes':{},'error_policy':'continue','retry_limit':retry,**({'lanes':lanes} if lanes else {})}}
  self.ledger=None;self.now=1000.0;self.workers=workers;self.studio=studio;self.waits=[]
 def clock(self):return self.now
 def save(self):pass
 def presence(self):return {'workers':self.workers}
 def wait(self,name,limit,ctx=None):self.waits.append(name);return {'waiting':True,'context':ctx or {}}
 def round(self):return step(self,self.studio.s,post=self.studio.post)

class Lanes(unittest.TestCase):
 def setUp(self):
  self.saved=[];studio_lanes.save_image=lambda folder,sid,key,result,ordinal:self.saved.append(key) or str(Path(folder)/key)

 def test_two_lanes_split_parts_and_finish(self):
  st=FakeStudio(parts=4);w=W(st,[worker('laneA'),worker('laneB')])
  r=w.round();self.assertTrue(r['waiting'])
  self.assertEqual({j['lane']:j['partId'] for j in st.s['laneJobs']},{'laneA':'p1','laneB':'p2'})
  st.finish('laneA');w.round()
  self.assertEqual(st.job('laneA')['partId'],'p3','free lane takes the next part while the other still works')
  st.finish('laneB');w.round();self.assertEqual(st.job('laneB')['partId'],'p4')
  st.finish('laneA');st.finish('laneB');r=w.round()
  self.assertEqual(r['context']['studio_completed_parts'],4);self.assertNotIn('waiting',r)
  self.assertEqual(sorted(p.name for p in (w.folder/'scenes').iterdir()),['p1.json','p2.json','p3.json','p4.json'])

 def test_three_lanes_image_lane_starts_as_soon_as_scenes_exist(self):
  st=FakeStudio(parts=4);w=W(st,[worker('laneA'),worker('laneB'),worker('laneC')],tasks=('analysis','scenes','images'))
  w.round()
  self.assertEqual(len(st.s['laneJobs']),3,'no images yet: the image lane helps with scenes')
  st.finish('laneA');w.round()
  self.assertEqual(st.job('laneA')['partId'],'p4')
  st.finish('laneC');w.round()
  self.assertEqual(st.job('laneC')['type'],'image_generation','image lane makes images while parts remain')
  # Scenes done: every lane makes images; images are saved one by one.
  for _ in range(20):
   for lane in ('laneA','laneB','laneC'):
    if st.job(lane):st.finish(lane)
   r=w.round()
   if 'waiting' not in r:break
  self.assertEqual(r['context']['studio_images_saved'],8);self.assertEqual(len(self.saved),8)

 def test_lost_lane_job_is_released_then_given_to_another_lane(self):
  st=FakeStudio(parts=2);w=W(st,[worker('laneA'),worker('laneB')])
  w.round();self.assertEqual(st.job('laneB')['partId'],'p2')
  w.workers=[worker('laneA')];w.now+=60;w.round()
  self.assertIsNotNone(st.job('laneB'),'a short drop keeps the job')
  w.now+=200;st.finish('laneA');w.round()
  self.assertTrue(any(p.endswith('/release') for p in st.posts))
  self.assertEqual(st.job('laneA')['partId'],'p2','released part moves to the live lane')

 def test_failed_part_retries_then_reports_without_blocking(self):
  st=FakeStudio(parts=2);w=W(st,[worker('laneA')],retry=1)
  w.round();st.finish('laneA',ok=False);w.round()
  self.assertEqual(st.job('laneA')['partId'],'p1','first error: retried')
  st.finish('laneA',ok=False);w.round()
  self.assertEqual(st.job('laneA')['partId'],'p2','after the retry limit the part is reported, others continue')
  st.finish('laneA');r=w.round()
  self.assertEqual(r['context']['studio_failed_items'],['part:p1']);self.assertNotIn('waiting',r)

 def test_image_limit_rests_only_that_lane(self):
  st=FakeStudio(parts=1,scenes=4);st.part('p1').update(status='complete',scenes=[{'prompt':'x','imageStatus':'waiting'} for _ in range(4)])
  w=W(st,[worker('laneA'),worker('laneB')],tasks=('images',))
  w.round();st.finish('laneA',ok=False,error="You've reached the image generation limit");r=w.round()
  self.assertIsNone(st.job('laneA'),'lane A rests after a limit message')
  self.assertIn('nghỉ tạo ảnh',r['context']['studio_attention'][0])
  w.now+=901;st.finish('laneB');w.round();self.assertIsNotNone(st.job('laneA'))

 def test_no_style_no_images(self):
  st=FakeStudio(parts=1);st.s['stylePrompt']='';st.part('p1').update(status='complete',scenes=[{'prompt':'x'}])
  w=W(st,[worker('laneA')],tasks=('images',));r=w.round()
  self.assertEqual(st.s['laneJobs'],[]);self.assertIn('phong cách',r['context']['studio_attention'][0])

 def test_old_extension_or_disconnected_lane_gets_nothing(self):
  self.assertEqual(list(live_lanes([worker('a1',version='0.4.34'),worker('b1',connected=False),worker('c1')])),['c1'])

 def test_warnings_explain_shared_account_and_extra_tabs(self):
  notes=warnings([worker('a1','a***@gmail.com','k1'),worker('b1','a***@gmail.com','k1',tabs=2),worker('b1','a***@gmail.com','k1'),worker('c1','c***@x.com','k2',plan='free')])
  text=' | '.join(notes)
  self.assertIn('dùng chung tài khoản',text);self.assertIn('nhiều tab ChatGPT',text);self.assertIn('2 tab Studio',text);self.assertIn('gói free',text)

 def test_extra_lanes_open_once_then_run_with_what_connected(self):
  opened=[];lanes=[{'browser':'edge','profile':'Default'},{'browser':'edge','profile':'Profile 1'},{'browser':'chrome','profile':'Default'}]
  w=W(FakeStudio(),[worker('a1')],lanes=lanes)
  r=open_step(w,launch=lambda lane,url:opened.append((lane['profile'],url)))
  self.assertTrue(r['waiting']);self.assertEqual(len(opened),2);self.assertIn('managerLane=1',opened[0][1])
  open_step(w,launch=lambda lane,url:opened.append(lane));self.assertEqual(len(opened),2,'never opens twice')
  w.now+=200;r=open_step(w,launch=None);self.assertNotIn('waiting',r);self.assertIn('1/3',r['context']['studio_message'])

class Rewrite(unittest.TestCase):
 def test_sections_spread_over_lanes_and_failures_retry(self):
  from automation_agent.studio_lanes import rewrite_round
  s={'workEpoch':0,'rewrite':{'sections':[{'id':'s%d'%i,'status':'waiting'} for i in range(1,5)]},'laneJobs':[],'laneLast':{}}
  posts=[];n=[0]
  def post(route,body):
   posts.append(route);bits=route.strip('/').split('/')
   if bits[2]=='release':s['laneJobs']=[j for j in s['laneJobs'] if j['id']!=body['jobId']];return {}
   n[0]+=1;job={'id':'j%d'%n[0],'lane':bits[1],'type':'transcript_rewrite','sectionId':bits[3]};s['laneJobs'].append(job)
   next(x for x in s['rewrite']['sections'] if x['id']==bits[3])['status']='processing';return {'command':job}
  def finish(lane,ok=True):
   j=next(j for j in s['laneJobs'] if j['lane']==lane);s['laneJobs'].remove(j)
   sec=next(x for x in s['rewrite']['sections'] if x['id']==j['sectionId']);sec['status']='done' if ok else 'error'
   s['laneLast'][lane]={'jobId':j['id'],'type':'transcript_rewrite','status':'completed' if ok else 'error','sectionId':j['sectionId']}
  w=W(FakeStudio(),[worker('laneA'),worker('laneB')],retry=1)
  r=rewrite_round(w,s,post=post);self.assertEqual({j['lane']:j['sectionId'] for j in s['laneJobs']},{'laneA':'s1','laneB':'s2'})
  finish('laneA');finish('laneB',ok=False);rewrite_round(w,s,post=post)
  self.assertEqual(sorted(j['sectionId'] for j in s['laneJobs']),['s2','s3'],'failed section retried, next one started')
  for _ in range(6):
   for lane in ('laneA','laneB'):
    if any(j['lane']==lane for j in s['laneJobs']):finish(lane)
   r=rewrite_round(w,s,post=post)
  self.assertEqual(r['studio_rewrite_done'],4);self.assertEqual(r['studio_rewrite_total'],4)
class StaleExtensionJob(unittest.TestCase):
 def test_old_remembered_job_does_not_block_a_free_lane(self):
  studio_lanes.save_image=lambda *a,**k:'x'
  st=FakeStudio(parts=2);ws=[worker('laneA'),worker('laneB')];ws[0]['extension_job']='transcript-old';ws[1]['extension_job']='oldjob'
  w=W(st,ws);w.round()
  self.assertEqual(len(st.s['laneJobs']),2,'both lanes get a part although their extensions remember old job ids')
if __name__=='__main__':unittest.main()
