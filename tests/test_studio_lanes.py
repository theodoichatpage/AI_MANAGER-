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
  self.saved=[];studio_lanes.save_scene_image=lambda project,sid,lay,key,result,ordinal:self.saved.append(key) or str(Path(project)/key)

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
  st=FakeStudio(parts=4);w=W(st,[worker('laneA'),worker('laneB'),worker('laneC')],tasks=('analysis','scenes','images','sync'))
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
  self.assertEqual(r['context']['studio_failed_items'],['part:p1'])
  self.assertTrue(r['waiting'],'a failed item is not the end: Manager waits to try it again')
  self.assertIn('tự thử lại',r['context']['studio_attention'][0])

 def test_failed_item_is_tried_again_after_a_pause_then_reported(self):
  st=FakeStudio(parts=1);w=W(st,[worker('laneA')],retry=0)
  w.round();st.finish('laneA',ok=False);w.round();self.assertIsNone(st.job('laneA'),'the one try is used')
  w.now+=900;w.round();self.assertEqual(st.job('laneA')['partId'],'p1','after 15 minutes it is sent again')
  for pause in (1800,3600,7200):
   st.finish('laneA',ok=False);r=w.round();self.assertTrue(r['waiting'])
   w.now+=pause;w.round()
  st.finish('laneA',ok=False);r=w.round()
  self.assertNotIn('waiting',r,'after the last new set it stays failed and the run ends');self.assertEqual(r['context']['studio_failed_items'],['part:p1'])

 def test_chatgpt_limit_is_not_a_used_try(self):
  st=FakeStudio(parts=1,scenes=1);st.part('p1').update(status='complete',scenes=[{'prompt':'x','imageStatus':'waiting'}])
  w=W(st,[worker('laneA')],tasks=('images',),retry=0)
  for _ in range(3):
   w.round();st.finish('laneA',ok=False,error="You've reached the image generation limit");w.round();w.now+=901
  r=w.round();self.assertEqual(st.job('laneA')['sceneKey'],'p1:0','still being tried after 3 limits with no retries allowed')
  self.assertIsNone(r['context']['studio_failed_items'],'a limit never marks the scene failed')

 def test_image_limit_rests_only_that_lane(self):
  st=FakeStudio(parts=1,scenes=4);st.part('p1').update(status='complete',scenes=[{'prompt':'x','imageStatus':'waiting'} for _ in range(4)])
  w=W(st,[worker('laneA'),worker('laneB')],tasks=('images',))
  w.round();st.finish('laneA',ok=False,error="You've reached the image generation limit");r=w.round()
  self.assertIsNone(st.job('laneA'),'lane A rests after a limit message')
  self.assertIn('nghỉ tạo ảnh',r['context']['studio_attention'][0])
  w.now+=901;st.finish('laneB');w.round();self.assertIsNotNone(st.job('laneA'))

 def test_image_limit_rests_the_lane_until_chatgpt_says_it_resets(self):
  st=FakeStudio(parts=1,scenes=2);st.part('p1').update(status='complete',scenes=[{'prompt':'x','imageStatus':'waiting'} for _ in range(2)])
  w=W(st,[worker('laneA')],tasks=('images',))
  notice="ChatGPT báo hết lượt tạo ảnh (giới hạn tài khoản): You've hit the Plus plan limit for image generations requests. You can create more images when the limit resets in 5 hours."
  w.round();st.finish('laneA',ok=False,error=notice);r=w.round()
  self.assertIn('nghỉ tạo ảnh 5 giờ',r['context']['studio_attention'][0])
  w.now+=901;w.round();self.assertIsNone(st.job('laneA'),'still resting after 15 minutes: ChatGPT said 5 hours')
  w.now+=5*3600;w.round();self.assertIsNotNone(st.job('laneA'),'works again once the limit has reset')

 def test_all_lanes_resting_is_waited_out_not_called_stuck(self):
  # Found live 2026-11-12 02:54: every lane rested after the limit, and the progress watchdog failed the run.
  class Watched(W):
   def wait(self,name,limit,ctx=None):
    start=self.j['stages'].setdefault(name,self.now)
    if self.now-start>limit:raise TimeoutError('Studio quá thời gian tại '+name)
    return super().wait(name,limit,ctx)
  st=FakeStudio(parts=1,scenes=3);st.part('p1').update(status='complete',scenes=[{'prompt':'x','imageStatus':'waiting'} for _ in range(3)])
  w=Watched(st,[worker('laneA')],tasks=('images',))
  w.round();st.finish('laneA',ok=False,error="ChatGPT báo hết lượt tạo ảnh (giới hạn tài khoản): You can create more images when the limit resets in 5 hours.")
  r=w.round();self.assertIn('đang nghỉ vì hết lượt tạo ảnh',r['context']['studio_message'])
  for _ in range(10):w.now+=1800;w.round()  # 5 hours of rest, checked every 30 minutes: no timeout
  self.assertTrue(any(n.startswith('lanes:rest:') for n in w.waits))
  w.now+=600;r=w.round();self.assertIsNotNone(st.job('laneA'),'the lane works again after its rest')
  self.assertIsNone(r['context']['studio_message'],'the resting message is cleared once the lane works again')

 def test_limit_wait_reads_chatgpt_reset_time(self):
  f=studio_lanes.limit_wait
  self.assertEqual(f('limit resets in 5 hours'),5*3600)
  self.assertEqual(f('Try again in 30 minutes'),1800)
  self.assertEqual(f('giới hạn, thử lại sau 2 giờ'),7200)
  self.assertEqual(f("You've reached the image generation limit"),studio_lanes.LIMIT_COOLDOWN,'no time given: the usual 15 minutes')
  self.assertEqual(f('resets in 2 minutes'),studio_lanes.LIMIT_COOLDOWN,'never shorter than the usual rest')
  self.assertEqual(f('resets in 48 hours'),studio_lanes.LIMIT_MAX,'never longer than 6 hours')

 def test_rerun_remakes_existing_pictures_and_saves_only_new_ones(self):
  studio_lanes.IMAGE_LANES=2;self.addCleanup(setattr,studio_lanes,'IMAGE_LANES',1)
  st=FakeStudio(parts=1,scenes=2);st.part('p1').update(status='complete',scenes=[{'prompt':'x','imageStatus':'complete','imageResults':[{'url':'https://x/old'}]} for _ in range(2)])
  w=W(st,[worker('laneA'),worker('laneB')],tasks=('images','sync'));w.c['work_config']['rerun']=True
  sent=[];old=st.post
  def post(route,body):sent.append(body);return old(route,body)
  st.post=post;w.round()
  self.assertEqual(len(st.s['laneJobs']),2,'already-made pictures are made again');self.assertTrue(all(b.get('force') for b in sent))
  self.assertEqual(self.saved,[],'the old pictures are not saved as results of this run')
  st.finish('laneA');st.finish('laneB')
  for _ in range(3):r=w.round()
  self.assertNotIn('waiting',r);self.assertEqual(r['context']['studio_images_saved'],2);self.assertEqual(len(self.saved),2)
 def test_backup_moves_old_picture_and_record(self):
  import hashlib,json
  from automation_agent.studio_lanes import backup_image
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);key='p1:0';rec=folder/'.vis'/(hashlib.sha256(key.encode()).hexdigest()+'.json');rec.parent.mkdir()
   (folder/'a.png').write_bytes(b'x');rec.write_text(json.dumps({'file':'a.png'}))
   backup_image(folder,key,'run1')
   self.assertFalse((folder/'a.png').exists());self.assertTrue((folder/'_backups'/'run1'/'a.png').exists());self.assertTrue((folder/'_backups'/'run1'/rec.name).exists())
   backup_image(folder,key,'run1')
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
  studio_lanes.save_scene_image=lambda *a,**k:'x'
  st=FakeStudio(parts=2);ws=[worker('laneA'),worker('laneB')];ws[0]['extension_job']='transcript-old';ws[1]['extension_job']='oldjob'
  w=W(st,ws);w.round()
  self.assertEqual(len(st.s['laneJobs']),2,'both lanes get a part although their extensions remember old job ids')
if __name__=='__main__':unittest.main()
