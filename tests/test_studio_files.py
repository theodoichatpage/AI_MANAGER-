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
  w=W(self.tmp.name,['separate'],{'separate':{'mode':'selected','items':[1]}});engine=FakeEngine();engine.down=True
  r=studio_files.step(w,SESSION,engine=engine,fetch=self.fetch);self.assertIn('Local Engine chưa chạy',r['context']['studio_message'])
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

class Actions(unittest.TestCase):
 def test_files_only_needs_no_browser_and_separation_runs_last(self):
  sid='a'*32
  a,c=workflow(sid,'https://video-image-studio.vercel.app','edge','Default','C:/x','',work_config={'tasks':['separate']})
  self.assertEqual([x['action'] for x in a],['STUDIO_FILES']);self.assertTrue(c['studio_launch'])
  a,_=workflow(sid,'https://video-image-studio.vercel.app','edge','Default','C:/x','',work_config={'tasks':['images','separate']})
  self.assertEqual(a[-2]['action'],'STUDIO_IMAGES');self.assertEqual(a[-1]['action'],'STUDIO_FILES')
if __name__=='__main__':unittest.main()
