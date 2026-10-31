"""Copy, rename and delete keep data safe; per-project prompts are saved."""
import json,tempfile,unittest
from pathlib import Path
import project_ops

class FakeQueue:
 def __init__(self):self.rows={};self.removed=[]
 def get(self,pid):return self.rows.setdefault(pid,{'status':'stopped'})
 def relocate(self,pid,name,folder):self.rows.setdefault(pid,{'status':'stopped'}).update(name=name,folder=str(folder))
 def remove(self,pid):self.removed.append(pid)
 def add(self,p):self.rows[p['id']]={'status':'waiting'}

def atomic(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
def slug(name):return name.replace(' ','_')

class Ops(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.q=FakeQueue();self.n=1
  self.p=self.make('Du an A',studio_project_id='a'*32,youtube_url='https://youtu.be/x',image_style='Gray {{ }}',script='Kịch bản')
 def tearDown(self):self.tmp.cleanup()
 def make(self,name,**extra):
  folder=self.root/('%03d_%s'%(self.n,slug(name)));folder.mkdir();self.n+=1
  p=dict({'id':'id%d'%self.n,'name':name,'folder':str(folder)},**extra);atomic(folder/'project.json',p);return p
 def create(self,name,script):return self.make(name,script=script)
 def test_rename_moves_folder_and_waits_for_studio(self):
  r=project_ops.rename(self.p,'  Dự   án B ',slug,self.q,atomic)
  self.assertEqual(r['name'],'Dự án B');self.assertTrue(r['name_pending']);self.assertTrue(r['folder_renamed'])
  self.assertTrue((self.root/'001_Dự_án_B'/'project.json').exists());self.assertFalse((self.root/'001_Du_an_A').exists())
  self.assertEqual(self.q.rows[self.p['id']]['folder'],str(self.root/'001_Dự_án_B'))
 def test_rename_refused_while_running(self):
  self.q.rows[self.p['id']]={'status':'running'}
  with self.assertRaises(ValueError):project_ops.rename(self.p,'X',slug,self.q,atomic)
  self.assertTrue(Path(self.p['folder']).exists())
 def test_copy_keeps_inputs_not_studio_link(self):
  c=project_ops.copy(self.p,self.create,self.q,atomic)
  saved=json.loads((Path(c['folder'])/'project.json').read_text(encoding='utf8'))
  self.assertEqual(saved['name'],'Du an A (bản sao)');self.assertEqual(saved['image_style'],'Gray {{ }}');self.assertEqual(saved['youtube_url'],'https://youtu.be/x')
  self.assertEqual(saved['script'],'Kịch bản');self.assertNotIn('studio_project_id',saved);self.assertEqual(saved['copied_from'],self.p['id'])
 def test_delete_moves_to_trash(self):
  r=project_ops.delete(self.p,self.q,self.root)
  self.assertFalse(Path(self.p['folder']).exists());self.assertTrue((Path(r['trash'])/'project.json').exists());self.assertEqual(self.q.removed,[self.p['id']])
 def test_update_saves_prompts_and_rejects_huge(self):
  project_ops.update(self.p,{'image_style':'New','rewrite_style':'R','unknown':'x'},atomic)
  saved=json.loads((Path(self.p['folder'])/'project.json').read_text(encoding='utf8'))
  self.assertEqual((saved['image_style'],saved['rewrite_style']),('New','R'));self.assertNotIn('unknown',saved)
  with self.assertRaises(ValueError):project_ops.update(self.p,{'image_style':'x'*20001},atomic)
if __name__=='__main__':unittest.main()
