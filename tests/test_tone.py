"""Even out the brightness of a project's pictures without touching their colours."""
import json,tempfile,unittest
from pathlib import Path
try:
 from PIL import Image,ImageStat
 from automation_agent import tone
except ImportError:
 Image=None

def make(path,grey,red=False):
 """A 64x36 picture: a left/right split around `grey` so it has some contrast; optionally a red patch."""
 im=Image.new('RGB',(64,36),(grey,grey,grey))
 for x in range(32,64):
  for y in range(36):im.putpixel((x,y),(min(255,grey+40),)*3)
 if red:
  for x in range(4,12):
   for y in range(4,12):im.putpixel((x,y),(150,20,20))
 path.parent.mkdir(parents=True,exist_ok=True);im.save(path)

@unittest.skipIf(Image is None,'Pillow is not installed in this Python')
class Tone(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def mean(self,path):return tone.measure(path)[0]
 def test_dark_and_light_pictures_meet_at_the_target_and_originals_are_kept(self):
  for i,g in enumerate((50,60,70,80,160,170,180,190)):make(self.p/'Anh'/'Phan 1'/('c%d.png'%i),g)
  out=tone.balance_project(self.p)
  self.assertEqual(out['failed'],[]);self.assertGreater(out['adjusted'],0)
  means=[self.mean(f) for f in tone.pictures(self.p)]
  self.assertLess(max(means)-min(means),0.5*(190-50),'the spread shrinks a lot: %s'%means)
  self.assertGreater(max(means)-min(means),5,'but light and dark scenes stay a little different')
  self.assertTrue((self.p/'.vis'/'tone_backup'/'Phan 1'/'c0.png').is_file(),'the original is kept')
  self.assertAlmostEqual(self.mean(self.p/'.vis'/'tone_backup'/'Phan 1'/'c0.png'),65,delta=15)
 def test_running_again_does_not_stack(self):
  for i,g in enumerate((50,60,70,80,160,170,180,190)):make(self.p/'Anh'/('c%d.png'%i),g)
  tone.balance_project(self.p);before=[self.mean(f) for f in tone.pictures(self.p)]
  again=tone.balance_project(self.p);self.assertEqual(again['adjusted'],0)
  self.assertEqual(before,[self.mean(f) for f in tone.pictures(self.p)])
 def test_the_target_is_fixed_once_so_later_pictures_match_earlier_ones(self):
  for i,g in enumerate((100,105,110,115,120,125,130,135)):make(self.p/'Anh'/('c%d.png'%i),g)
  t=tone.target(self.p);self.assertEqual(json.loads((self.p/'.vis'/'tone.json').read_text())['target'],list(t))
  make(self.p/'Anh'/'new.png',200);tone.balance_file(self.p,self.p/'Anh'/'new.png')
  self.assertEqual(tone.target(self.p),t);self.assertLess(abs(self.mean(self.p/'Anh'/'new.png')-t[0]),0.5*abs(200-t[0]),'moved toward the earlier pictures')
 def test_few_pictures_use_the_default_until_enough_exist(self):
  make(self.p/'Anh'/'a.png',60);self.assertEqual(tone.target(self.p),tone.DEFAULT);self.assertFalse((self.p/'.vis'/'tone.json').exists())
 def test_colour_stays_red_and_the_checksum_record_stays_true(self):
  import hashlib
  for i,g in enumerate((50,60,70,80,160,170,180,190)):make(self.p/'Anh'/('c%d.png'%i),g,red=(i==0))
  rec=self.p/'Anh'/'.vis'/'x.json';rec.parent.mkdir();rec.write_text(json.dumps({'scene_key':'k','file':'c0.png','sha256':'old'}))
  tone.balance_project(self.p)
  with Image.open(self.p/'Anh'/'c0.png') as im:r,g,b=im.getpixel((8,8))
  self.assertGreater(r,g+60);self.assertGreater(r,b+60,'the red accent keeps its hue')
  self.assertEqual(json.loads(rec.read_text())['sha256'],hashlib.sha256((self.p/'Anh'/'c0.png').read_bytes()).hexdigest())
 def test_restore_puts_the_originals_back(self):
  for i,g in enumerate((50,60,70,80,160,170,180,190)):make(self.p/'Anh'/('c%d.png'%i),g)
  first=(self.p/'Anh'/'c0.png').read_bytes();tone.balance_project(self.p)
  self.assertNotEqual(first,(self.p/'Anh'/'c0.png').read_bytes())
  self.assertGreater(tone.restore(self.p),0);self.assertEqual(first,(self.p/'Anh'/'c0.png').read_bytes())

if __name__=='__main__':unittest.main()
