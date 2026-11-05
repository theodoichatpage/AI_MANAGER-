"""A file that is briefly locked by a reader does not fail the write."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation_agent import fsutil,studio_workflow

class Replace(unittest.TestCase):
 def test_retries_while_the_file_is_locked_then_succeeds(self):
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d)/'a.tmp';dst=Path(d)/'a.json';tmp.write_text('new');real=os.replace;calls=[]
   def locked(a,b):
    calls.append(1)
    if len(calls)<4:raise PermissionError(5,'Access is denied')
    real(a,b)
   waits=[]
   with patch('os.replace',locked):fsutil.replace_retry(tmp,dst,sleep=waits.append)
   self.assertEqual(dst.read_text(),'new');self.assertEqual(len(calls),4);self.assertEqual(len(waits),3)
 def test_gives_up_after_the_limit(self):
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d)/'a.tmp';tmp.write_text('x')
   with patch('os.replace',side_effect=PermissionError(5,'Access is denied')):
    with self.assertRaises(PermissionError):fsutil.replace_retry(tmp,Path(d)/'a.json',tries=3,sleep=lambda s:None)
 def test_the_journal_write_uses_it(self):
  with tempfile.TemporaryDirectory() as d:
   n={'k':0};real=os.replace
   def flaky(a,b):
    n['k']+=1
    if n['k']==1:raise PermissionError(5,'Access is denied')
    real(a,b)
   with patch('os.replace',flaky),patch('time.sleep',lambda s:None):studio_workflow.atomic(Path(d)/'j.json',{'a':1})
   self.assertEqual((Path(d)/'j.json').read_text(encoding='utf8'),'{"a": 1}')

if __name__=='__main__':unittest.main()
