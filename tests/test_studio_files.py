"""Pictures and separated layers land in <project>/Anh|Tach anh/<Phan N - ...>/<Canh M - ...>, with or without downloading."""
import io,json,tempfile,unittest,zipfile
from pathlib import Path
from PIL import Image
from automation_agent import studio_files
from automation_agent.project_files import layout,plain,titled
from automation_agent.studio_workflow import workflow

def png():
 out=io.BytesIO();Image.new('RGB',(4,3),'red').save(out,'PNG');return out.getvalue()
PNG=png()
SESSION={'parts':[{'id':'pa','title':'Phần 1 - Từ đáy nghèo đói','scenes':[
  {'title':'Cảnh 1 - Hai đầu số phận','imageStatus':'complete','imageResults':[{'url':'https://x/1'}]},
  {'title':'Cảnh 2 - Đường: "xa"?','imageStatus':'complete','imageResults':[{'url':'https://x/2'}]}]},
 {'id':'pb','title':'Bắt đầu','scenes':[{'title':'Lương thực','imageStatus':'waiting'},{'title':'Cảnh 2 - Năm mươi ngày','imageStatus':'complete','imageResults':[{'url':'https://x/4'}]}]}]}

class Names(unittest.TestCase):
 def test_readable_names(self):
  self.assertEqual(plain('Đường đi: "xa"? '),'Duong di_ _xa_')
  self.assertEqual(titled('Phan',2,'Bắt đầu'),'Phan 2 - Bat dau')
  self.assertEqual(titled('Canh',1,'Cảnh 1 - Hai đầu số phận'),'Canh 1 - Hai dau so phan')
  lay=layout(SESSION)
  self.assertEqual(lay['pa:0'],('Phan 1 - Tu day ngheo doi','Canh 1 - Hai dau so phan'))
  self.assertEqual(lay['pb:0'],('Phan 2 - Bat dau','Canh 1 - Luong thuc'))
 def test_same_name_in_a_part_gets_a_number(self):
  lay=layout({'parts':[{'id':'p','title':'A','scenes':[{'title':'Cảnh 1 - X'},{'title':'Cảnh 1 - X'}]}]})
  self.assertEqual(lay['p:1'][1],'Canh 1 - X (2)')

class FakeEngine:
 def __init__(self):self.jobs={};self.sent=[];self.busy=False;self.down=False
 def start(self,data,filename,project,layers):
  if self.down:raise studio_files.EngineDown('x')
  if self.busy:raise studio_files.EngineBusy('x')
  jid='j%d'%len(self.jobs);self.jobs[jid]='processing';self.sent.append((filename,project,layers,data==PNG));return jid
 def status(self,jid):return {'status':self.jobs.get(jid,'lost'),'progress':50}
 def layers_zip(self,jid):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:
   for n in ('01_bg.png','02_mid.png','03_fg.png'):z.writestr(n,PNG)
   z.writestr('vi_tri.json','{}');z.writestr('_kiem_tra/ghep_lai.png',PNG)
  return out.getvalue()
 def finish(self):
  for k,v in self.jobs.items():
   if v=='processing':self.jobs[k]='complete'

class W:
 def __init__(self,folder,tasks,scopes=None,**cfg):
  self.folder=Path(folder);self.sid='s'*32;self.j={};self.ledger=None;self.now=1000.0;self.waits=[]
  self.c={'project_name':'Thử dự án','studio_run_id':'r1','work_config':dict({'tasks':tasks,'scopes':scopes or {},'retry_limit':1,'error_policy':'continue'},**cfg)}
 def clock(self):return self.now
 def save(self):pass
 def wait(self,name,limit,ctx=None):self.waits.append(name);return {'waiting':True,'context':ctx or {}}

class Files(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.fetched=[]
 def tearDown(self):self.tmp.cleanup()
 def fetch(self,url):self.fetched.append(url);return PNG
 def run_until_done(self,w,engine,rounds=20):
  for _ in range(rounds):
   r=studio_files.step(w,SESSION,engine=engine,fetch=self.fetch)
   if 'waiting' not in r:return r
   engine.finish()
  self.fail('did not finish')
 def test_download_and_separate_in_part_folders(self):
  w=W(self.tmp.name,['sync','separate']);engine=FakeEngine()
  r=self.run_until_done(w,engine)
  root=Path(self.tmp.name)
  self.assertTrue((root/'Anh'/'Phan 1 - Tu day ngheo doi'/'Canh 1 - Hai dau so phan.png').is_file())
  self.assertTrue((root/'Anh'/'Phan 2 - Bat dau'/'Canh 2 - Nam muoi ngay.png').is_file())
  sep=root/'Tach anh'/'Phan 1 - Tu day ngheo doi'/'Canh 2 - Duong_ _xa_'
  self.assertTrue((sep/'03_fg.png').is_file() and (sep/'vi_tri.json').is_file() and (sep/'_kiem_tra'/'ghep_lai.png').is_file())
  self.assertEqual(r['context']['studio_separated'],3,'the scene without a picture is skipped');self.assertEqual(r['context']['studio_files_saved'],3)
  self.assertEqual(len(self.fetched),3,'separation reuses the downloaded file')
  self.assertEqual(engine.sent[0][:3],('Canh 1 - Hai dau so phan.png','Thu du an - Phan 1 - Tu day ngheo doi',3))
 def test_separate_without_downloading_keeps_only_layers(self):
  w=W(self.tmp.name,['separate'],{'separate':{'mode':'selected','items':[2]}},separate_layers=4);engine=FakeEngine()
  r=self.run_until_done(w,engine)
  root=Path(self.tmp.name)
  self.assertFalse((root/'Anh').exists(),'nothing downloaded');self.assertEqual(r['context']['studio_separated'],1)
  self.assertEqual(engine.sent,[('Canh 2 - Duong_ _xa_.png','Thu du an - Phan 1 - Tu day ngheo doi',4,True)])
 def test_engine_down_or_busy_waits_and_nothing_is_lost(self):
  from unittest.mock import patch
  from automation_agent import local_engine_boot
  w=W(self.tmp.name,['separate'],{'separate':{'mode':'selected','items':[1]}});engine=FakeEngine();engine.down=True;started=[]
  with patch.object(local_engine_boot,'launch',lambda:started.append(1)):
   r=studio_files.step(w,SESSION,engine=engine,fetch=self.fetch);self.assertIn('Local Engine chưa chạy',r['context']['studio_message'])
   self.assertEqual(len(started),1,'Manager starts the engine itself')
   r=studio_files.step(w,SESSION,engine=engine,fetch=self.fetch);self.assertEqual(len(started),1,'not again while it is loading')
   self.assertIn('đang chờ nó nạp',r['context']['studio_message'])
  engine.down=False;engine.busy=True
  r=studio_files.step(w,SESSION,engine=engine,fetch=self.fetch);self.assertIn('đang tách một ảnh khác',r['context']['studio_message'])
  engine.busy=False;r=self.run_until_done(w,engine);self.assertEqual(r['context']['studio_separated'],1)
 def test_lost_job_is_retried_then_reported(self):
  w=W(self.tmp.name,['separate'],{'separate':{'mode':'selected','items':[1]}});engine=FakeEngine()
  for _ in range(3):studio_files.step(w,SESSION,engine=engine,fetch=self.fetch);engine.jobs.clear()  # engine restarted each time
  self.assertEqual(len(engine.sent),2,'a lost job is sent again at once, up to retry_limit+1 tries')
  self.assertEqual(w.j['files']['sep']['pa:0']['state'],'error')
 def test_already_separated_scene_is_kept(self):
  dest=Path(self.tmp.name)/'Tach anh'/'Phan 1 - Tu day ngheo doi'/'Canh 1 - Hai dau so phan';dest.mkdir(parents=True);(dest/'vi_tri.json').write_text('{}')
  w=W(self.tmp.name,['separate'],{'separate':{'mode':'selected','items':[1]}});engine=FakeEngine()
  r=studio_files.step(w,SESSION,engine=engine,fetch=self.fetch);self.assertNotIn('waiting',r);self.assertEqual(engine.sent,[])
 def test_bad_zip_names_are_refused(self):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:z.writestr('../evil.png',PNG);z.writestr('vi_tri.json','{}')
  with self.assertRaises(ValueError):studio_files.unpack_layers(out.getvalue(),Path(self.tmp.name)/'x',Path(self.tmp.name)/'b')

class Parallax(unittest.TestCase):
 """After separation, Parallax25D makes the videos; Manager waits on its status file."""
 def setUp(self):self.tmp=tempfile.TemporaryDirectory()
 def tearDown(self):self.tmp.cleanup()
 def test_videos_are_made_after_separation(self):
  from unittest.mock import patch
  from automation_agent import parallax_video
  w=W(self.tmp.name,['separate','parallax'],{'separate':{'mode':'selected','items':[1]}});engine=FakeEngine();launched=[]
  def start(project,ratio,motion,rerun):
   launched.append((str(project),ratio,motion,rerun));return {'pid':7,'at':w.now,'status':str(Path(project)/'.vis'/'s.json')}
  progress=iter([('running',{'state':'starting'}),('running',{'state':'running','percent':50,'done':0,'total':1,'current':['Canh 1']}),
                 ('done',{'state':'done','done':1,'skipped':0,'scenes':{'Phan 1/Canh 1 - Hai dau so phan':{'state':'done','video':'v.mp4'}}})])
  with patch.object(parallax_video,'start',start),patch.object(parallax_video,'check',lambda job:next(progress)):
   r=studio_files.step(w,SESSION,engine=engine,fetch=lambda u:PNG)
   self.assertEqual(launched,[],'videos wait for separation');engine.finish()
   msgs=[]
   for _ in range(6):
    r=studio_files.step(w,SESSION,engine=engine,fetch=lambda u:PNG)
    if 'waiting' not in r:break
    msgs.append(r['context'].get('studio_message'))
  self.assertEqual(len(launched),1,'launched once');self.assertEqual(launched[0][1:],('16:9','random',False))
  self.assertIn('Làm video Parallax 50% (0/1 cảnh): Canh 1',msgs)
  self.assertEqual(r['context']['studio_parallax_made'],1);self.assertIsNone(r['context']['studio_files_failed'])
  self.assertIn('video Parallax',r['context']['studio_stage'])
 def test_an_interrupted_program_is_started_again_then_gives_up(self):
  from unittest.mock import patch
  from automation_agent import parallax_video
  root=Path(self.tmp.name)/'Tach anh'/'Phan 1'/'Canh 1';root.mkdir(parents=True);(root/'01_bg.png').write_bytes(b'x')
  w=W(self.tmp.name,['parallax']);launched=[]
  def start(project,ratio,motion,rerun):
   launched.append(rerun);return {'pid':len(launched),'at':w.now,'status':str(Path(project)/'.vis'/'s.json')}
  crash=('error','Parallax25D đã tắt giữa chừng (1/3 video).')
  with patch.object(parallax_video,'start',start),patch.object(parallax_video,'check',lambda job:crash):
   r=studio_files.step(w,SESSION,engine=FakeEngine(),fetch=lambda u:PNG)
   self.assertGreaterEqual(len(launched),1,'started in the first round')
   for _ in range(5):r=studio_files.step(w,SESSION,engine=FakeEngine(),fetch=lambda u:PNG)
  self.assertEqual(launched,[False,False,False],'3 runs in total, never with "rerun" (it would redo the finished videos)')
  self.assertIn('giữa chừng',r['context']['studio_files_failed'][0]);self.assertNotIn('waiting',r)
 def test_videos_that_failed_are_tried_again(self):
  from unittest.mock import patch
  from automation_agent import parallax_video
  root=Path(self.tmp.name)/'Tach anh'/'Phan 1'/'Canh 1';root.mkdir(parents=True);(root/'01_bg.png').write_bytes(b'x')
  w=W(self.tmp.name,['parallax']);launched=[]
  def start(project,ratio,motion,rerun):
   launched.append(1);return {'pid':len(launched),'at':w.now,'status':str(Path(project)/'.vis'/'s.json')}
  results=iter([('done',{'state':'done','done':0,'skipped':0,'scenes':{'Phan 1/Canh 1':{'state':'error','error':'x'}}}),
                ('done',{'state':'done','done':1,'skipped':0,'scenes':{'Phan 1/Canh 1':{'state':'done','video':'v.mp4'}}})])
  with patch.object(parallax_video,'start',start),patch.object(parallax_video,'check',lambda job:next(results)):
   for _ in range(4):
    r=studio_files.step(w,SESSION,engine=FakeEngine(),fetch=lambda u:PNG)
    if 'waiting' not in r:break
  self.assertEqual(len(launched),2);self.assertIsNone(r['context']['studio_files_failed']);self.assertEqual(r['context']['studio_parallax_made'],1)
 def test_missing_exe_is_reported_without_blocking_the_rest(self):
  from unittest.mock import patch
  from automation_agent import parallax_video
  root=Path(self.tmp.name)/'Tach anh'/'Phan 1'/'Canh 1';root.mkdir(parents=True);(root/'01_bg.png').write_bytes(b'x')
  w=W(self.tmp.name,['parallax'])
  with patch.object(parallax_video,'find_exe',lambda:None):r=studio_files.step(w,SESSION,engine=FakeEngine(),fetch=lambda u:PNG)
  self.assertNotIn('waiting',r);self.assertIn('Parallax25D.exe',r['context']['studio_files_failed'][0])
 def test_nothing_separated_yet(self):
  w=W(self.tmp.name,['parallax']);r=studio_files.step(w,SESSION,engine=FakeEngine(),fetch=lambda u:PNG)
  self.assertNotIn('waiting',r);self.assertEqual(r['context']['studio_message'],'Chưa có cảnh đã tách để làm video Parallax')

PARALLAX_BATCH_FOR_TEST=studio_files.PARALLAX_BATCH

class Streaming(unittest.TestCase):
 """While pictures are still being made, separation and Parallax follow the ones that exist (partial=True)."""
 def setUp(self):self.tmp=tempfile.TemporaryDirectory()
 def tearDown(self):self.tmp.cleanup()
 def test_separation_follows_existing_pictures_and_waits_for_the_others(self):
  w=W(self.tmp.name,['separate']);engine=FakeEngine()
  for _ in range(8):
   ctx=studio_files.step(w,SESSION,engine=engine,fetch=lambda u:PNG,partial=True);engine.finish()
  self.assertNotIn('waiting',ctx,'partial returns the board context, never a wait');self.assertEqual(ctx['studio_separated'],3)
  self.assertNotIn('no-image',[v.get('state') for v in w.j['files']['sep'].values()],'a scene with no picture yet is not given up')
  self.assertEqual(len(engine.sent),3)
  later={'parts':[dict(SESSION['parts'][0]),{'id':'pb','title':'Bắt đầu','scenes':[{'title':'Lương thực','imageStatus':'complete','imageResults':[{'url':'https://x/3'}]},SESSION['parts'][1]['scenes'][1]]}]}
  for _ in range(4):
   ctx=studio_files.step(w,later,engine=engine,fetch=lambda u:PNG,partial=True);engine.finish()
  self.assertEqual(ctx['studio_separated'],4,'the picture that arrived later is separated too')
 def test_parallax_starts_for_a_batch_then_again_for_new_scenes(self):
  from unittest.mock import patch
  from automation_agent import parallax_video
  w=W(self.tmp.name,['separate','parallax']);engine=FakeEngine();launched=[]
  def start(project,ratio,motion,rerun):
   launched.append(parallax_video.scenes_ready(Path(project)/'Tach anh'));return {'pid':len(launched),'at':w.now,'status':'s'}
  state={'v':('running',{'state':'running','percent':10,'done':0,'total':3})}
  with patch.object(parallax_video,'start',start),patch.object(parallax_video,'check',lambda job:state['v']):
   ctx=studio_files.step(w,SESSION,engine=engine,fetch=lambda u:PNG,partial=True)
   self.assertEqual(launched,[],'no separated scene yet: nothing to start')
   for _ in range(8):ctx=studio_files.step(w,SESSION,engine=engine,fetch=lambda u:PNG,partial=True);engine.finish()
   self.assertEqual(launched,[3],'3 scenes are separated and no picture is left to separate: one run starts')
   self.assertEqual(ctx['studio_parallax_percent'],10);self.assertNotIn('waiting',ctx)
   state['v']=('done',{'state':'done','done':3,'skipped':0,'scenes':{}})
   ctx=studio_files.step(w,SESSION,engine=engine,fetch=lambda u:PNG,partial=True)
   self.assertEqual(launched,[3],'nothing new: no second run')
 def test_parallax_does_not_wait_for_the_separation_job_in_flight(self):
  from unittest.mock import patch
  from automation_agent import parallax_video
  w=W(self.tmp.name,['separate','parallax']);launched=[]
  for n in range(PARALLAX_BATCH_FOR_TEST):
   d=Path(self.tmp.name)/'Tach anh'/'Phan 1'/('Canh %d'%n);d.mkdir(parents=True);(d/'01_bg.png').write_bytes(b'x')
  w.j['files']={'saved':{},'sep':{},'job':{'key':'pa:0','ordinal':1,'id':'j0','at':w.now}}
  engine=FakeEngine();engine.jobs['j0']='processing'
  def start(project,ratio,motion,rerun):
   launched.append(1);return {'pid':1,'at':w.now,'status':'s'}
  with patch.object(parallax_video,'start',start),patch.object(parallax_video,'check',lambda job:('running',{'state':'running','percent':5,'done':0,'total':8})):
   ctx=studio_files.step(w,SESSION,engine=engine,fetch=lambda u:PNG,partial=True)
  self.assertEqual(launched,[1],'one run although a separation job is still in flight');self.assertEqual(ctx['studio_parallax_percent'],5)
 def test_lanes_call_it_every_round_when_separation_is_on(self):
  from unittest.mock import patch
  from automation_agent import studio_lanes
  import tests.test_studio_lanes as tl
  st=tl.FakeStudio(parts=1,scenes=2);st.part('p1').update(status='complete',scenes=[{'prompt':'x','imageStatus':'waiting'} for _ in range(2)])
  w=tl.W(st,[tl.worker('laneA')],tasks=('images','separate'));calls=[]
  with patch('automation_agent.studio_files.step',lambda *a,**k:calls.append(k.get('partial')) or {'studio_separated':1,'studio_separate_total':2,'studio_message':'Đang tách'}):
   studio_lanes.step(w,st.s,post=st.post)
  self.assertEqual(calls,[True])
  w2=tl.W(st,[tl.worker('laneA')],tasks=('images',))
  with patch('automation_agent.studio_files.step',lambda *a,**k:calls.append('no')):
   studio_lanes.step(w2,st.s,post=st.post)
  self.assertEqual(calls,[True],'not called when neither separation nor Parallax is on')

class Actions(unittest.TestCase):
 def test_files_only_needs_no_browser_and_separation_runs_last(self):
  sid='a'*32
  a,c=workflow(sid,'https://video-image-studio.vercel.app','edge','Default','C:/x','',work_config={'tasks':['separate']})
  self.assertEqual([x['action'] for x in a],['STUDIO_FILES']);self.assertTrue(c['studio_launch'])
  a,_=workflow(sid,'https://video-image-studio.vercel.app','edge','Default','C:/x','',work_config={'tasks':['images','separate']})
  self.assertEqual(a[-2]['action'],'STUDIO_IMAGES');self.assertEqual(a[-1]['action'],'STUDIO_FILES')
  a,c=workflow(sid,'https://video-image-studio.vercel.app','edge','Default','C:/x','',work_config={'tasks':['parallax']})
  self.assertEqual([x['action'] for x in a],['STUDIO_FILES'],'videos only: no browser')
if __name__=='__main__':unittest.main()
