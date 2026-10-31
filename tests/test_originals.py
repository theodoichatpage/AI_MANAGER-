"""Originals sent by the extension are kept on this PC and used instead of downloading from Studio's server."""
import base64,io,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from automation_agent import originals
from automation_agent.studio_images import save_image

def png(color=(200,0,0)):
 buf=io.BytesIO();Image.new('RGB',(8,6),color).save(buf,'PNG');return buf.getvalue()
def url(data,kind='png'):return 'data:image/'+kind+';base64,'+base64.b64encode(data).decode()

class Originals(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.project=Path(self.tmp.name)/'001_A';self.project.mkdir()
 def tearDown(self):self.tmp.cleanup()
 def test_save_find_and_bad_input(self):
  data=png();path=originals.save(self.project,'job_123456',url(data))
  self.assertEqual(path,self.project/'.vis'/'goc'/'job_123456.png');self.assertEqual(path.read_bytes(),data)
  self.assertEqual(originals.save(self.project,'job_123456',url(data)),path,'same picture twice is kept once')
  self.assertEqual(originals.read(self.project,{'jobId':'job_123456'}),data)
  self.assertIsNone(originals.read(self.project,{'jobId':'other_999'}))
  for job,value in (('../x',url(data)),('job_123456','data:text/plain;base64,aGk='),('job_123456','data:image/png;base64,bm90IGFuIGltYWdl')):
   with self.assertRaises(Exception):originals.save(self.project,job,value)
 def test_sync_uses_local_original_and_never_takes_a_preview_as_original(self):
  data=png((0,0,200));originals.save(self.project,'job_abcdef',url(data))
  calls=[];fetch=lambda u:calls.append(u) or png((9,9,9))
  dest=self.project/'Anh'/'Phan 1'
  path=save_image(dest,'s'*16,'p1:0',{'url':'https://x/thumb','jobId':'job_abcdef','local':True},1,fetch=fetch,name='Canh 1',project=self.project)
  self.assertEqual(Path(path).read_bytes(),data);self.assertEqual(calls,[],'nothing downloaded')
  with self.assertRaises(ValueError):
   save_image(dest,'s'*16,'p1:1',{'url':'https://x/thumb2','jobId':'job_missing','local':True},2,fetch=fetch,name='Canh 2',project=self.project)
  self.assertEqual(calls,[],'a preview-only result is not downloaded as the original')
  # An older result (full picture on Studio's server) is still downloaded as before.
  path=save_image(dest,'s'*16,'p1:2',{'url':'https://x/full','jobId':'job_old000'},3,fetch=fetch,name='Canh 3',project=self.project)
  self.assertEqual(calls,['https://x/full'])
if __name__=='__main__':unittest.main()
