"""Edge profile clone: keeps the login data, skips caches/history/passwords, registers the profile, backs up."""
import json,tempfile,unittest
from pathlib import Path
from automation_agent import edge_clone

class Clone(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();ud=Path(self.tmp.name);self.ud=ud
  d=ud/'Default';(d/'Network').mkdir(parents=True);(d/'Cache'/'Cache_Data').mkdir(parents=True);(d/'Local Storage'/'leveldb').mkdir(parents=True)
  (d/'Network'/'Cookies').write_bytes(b'cookies');(d/'Local Storage'/'leveldb'/'000003.log').write_bytes(b'ls');(d/'Cache'/'Cache_Data'/'f').write_bytes(b'x'*10)
  (d/'History').write_bytes(b'h');(d/'Login Data').write_bytes(b'pw');(d/'Preferences').write_text(json.dumps({'profile':{'name':'Profile 1'}}))
  (ud/'Profile 3').mkdir()
  (ud/'Local State').write_text(json.dumps({'profile':{'info_cache':{'Default':{'name':'Profile 1','avatar_icon':'x'}},'profiles_order':['Default']},'os_crypt':{'encrypted_key':'k'}}))
 def tearDown(self):self.tmp.cleanup()
 def test_clone(self):
  r=edge_clone.clone(base=self.ud,running=lambda:False,clock=lambda:123)
  self.assertEqual(r['profile'],'Profile 4','next free number')
  dst=self.ud/'Profile 4'
  self.assertEqual((dst/'Network'/'Cookies').read_bytes(),b'cookies');self.assertTrue((dst/'Local Storage'/'leveldb'/'000003.log').exists())
  for skipped in ('Cache','History','Login Data'):self.assertFalse((dst/skipped).exists(),skipped)
  self.assertEqual(json.loads((dst/'Preferences').read_text())['profile']['name'],'ChatGPT 2')
  state=json.loads((self.ud/'Local State').read_text())
  self.assertEqual(state['profile']['info_cache']['Profile 4']['name'],'ChatGPT 2');self.assertEqual(state['profile']['info_cache']['Profile 4']['avatar_icon'],'x')
  self.assertEqual(state['profile']['profiles_order'],['Default','Profile 4']);self.assertEqual(state['os_crypt'],{'encrypted_key':'k'},'login key untouched')
  self.assertTrue((self.ud/'Local State.ai-manager-backup-123').exists())
  self.assertTrue((self.ud/'Default'/'History').exists(),'source untouched')
 def test_refuses_while_edge_runs(self):
  with self.assertRaises(RuntimeError):edge_clone.clone(base=self.ud,running=lambda:True)
  self.assertFalse((self.ud/'Profile 4').exists())
 def test_close_edge_graceful_then_force(self):
  calls=[];alive=[True]
  def run(cmd,**kw):calls.append(cmd);alive[0]=alive[0] and '/F' not in cmd
  self.assertTrue(edge_clone.close_edge(wait=1,running=lambda:alive[0],run=run,sleep=lambda s:None))
  self.assertEqual(calls[0],['taskkill','/IM','msedge.exe','/T']);self.assertIn('/F',calls[1])
if __name__=='__main__':unittest.main()
