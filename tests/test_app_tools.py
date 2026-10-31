"""Backup holds every project (not the trash) and settings; restore never overwrites an existing project."""
import json,tempfile,unittest,zipfile
from pathlib import Path
import app_tools

class Backup(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();t=Path(self.tmp.name)
  self.root=t/'VIDEO_PROJECTS';self.base=t/'.ai_manager';self.dest=t/'backups'
  for name in ('001_A','002_B'):
   (self.root/name/'Anh'/'Phan 1').mkdir(parents=True);(self.root/name/'project.json').write_text(json.dumps({'name':name}))
   (self.root/name/'Anh'/'Phan 1'/'Canh 1.png').write_bytes(b'png')
  (self.root/'_Thung_rac'/'003_C').mkdir(parents=True);(self.root/'_Thung_rac'/'003_C'/'project.json').write_text('{}')
  (self.root/'.ai_manager_queue.sqlite3').write_bytes(b'db')
  (self.base/'automation').mkdir(parents=True);(self.base/'config.json').write_text('{"root":"x"}');(self.base/'automation'/'settings.json').write_text('{}')
 def tearDown(self):self.tmp.cleanup()
 def test_backup_then_restore_on_a_new_pc(self):
  r=app_tools.backup(self.root,self.base,self.dest)
  names=zipfile.ZipFile(r['path']).namelist()
  self.assertIn('projects/001_A/Anh/Phan 1/Canh 1.png',names);self.assertIn('settings/config.json',names);self.assertIn('settings/automation/settings.json',names)
  self.assertFalse(any('_Thung_rac' in n or 'sqlite3' in n for n in names),'trash and the live queue are not backed up')
  self.assertEqual([x['path'] for x in app_tools.backups(self.dest)],[r['path']])
  new=Path(self.tmp.name)/'new';root2=new/'VIDEO_PROJECTS';base2=new/'.ai_manager'
  (root2/'002_B').mkdir(parents=True);(root2/'002_B'/'project.json').write_text('{"name":"keep"}')
  out=app_tools.restore(r['path'],root2,base2,busy=False)
  self.assertEqual(out['added'],['001_A']);self.assertEqual(out['skipped'],['002_B'])
  self.assertEqual((root2/'001_A'/'Anh'/'Phan 1'/'Canh 1.png').read_bytes(),b'png')
  self.assertEqual(json.loads((root2/'002_B'/'project.json').read_text())['name'],'keep','existing project untouched')
  self.assertTrue((base2/'config.json').exists())
 def test_restore_refuses_while_busy_or_odd_files(self):
  r=app_tools.backup(self.root,self.base,self.dest)
  with self.assertRaises(ValueError):app_tools.restore(r['path'],self.root,self.base,busy=True)
  bad=Path(self.tmp.name)/'bad.zip'
  with zipfile.ZipFile(bad,'w') as z:z.writestr('manifest.json','{}');z.writestr('projects/../evil.txt','x')
  with self.assertRaises(ValueError):app_tools.restore(bad,self.root,self.base,busy=False)
if __name__=='__main__':unittest.main()
