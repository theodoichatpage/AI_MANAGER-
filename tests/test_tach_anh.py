"""Hand-separated scenes are filed under their part, like Manager's own separation does."""
import tempfile,unittest
from pathlib import Path
from automation_agent import tach_anh

class TachAnh(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
  for part,scenes in {'Phan 1 - A':['Canh 1 - X','Canh 2 - Y'],'Phan 2 - B':['Canh 1 - Z']}.items():
   (self.p/'Anh'/part).mkdir(parents=True)
   for s in scenes:(self.p/'Anh'/part/(s+'.png')).write_bytes(b'x')
 def tearDown(self):self.tmp.cleanup()
 def scene(self,name,done=True):
  d=self.p/'Tach anh'/name;d.mkdir(parents=True)
  if done:(d/'01_bg.png').write_bytes(b'x')
  return d
 def test_scene_parts_reads_the_picture_folders(self):
  self.assertEqual(tach_anh.scene_parts(self.p),{'canh 1 - x':'Phan 1 - A','canh 2 - y':'Phan 1 - A','canh 1 - z':'Phan 2 - B'})
  self.assertEqual(tach_anh.scene_parts(self.p/'none'),{})
 def test_done_scenes_lists_flat_and_filed_scenes_with_layers(self):
  self.scene('Canh 1 - X');self.scene('Canh 2 - Y',done=False)
  d=self.p/'Tach anh'/'Phan 2 - B'/'Canh 1 - Z';d.mkdir(parents=True);(d/'02_mid.png').write_bytes(b'x')
  self.assertEqual(tach_anh.done_scenes(self.p),['canh 1 - x','canh 1 - z'])

if __name__=='__main__':unittest.main()
