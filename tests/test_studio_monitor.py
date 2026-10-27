import unittest
from studio_monitor import StudioMonitor
class TestStudioMonitor(unittest.TestCase):
 def test_poll_recovers_inside_same_cycle(self):
  calls=[]
  def reader(code):
   calls.append(code)
   if len(calls)<3: raise OSError('slow')
   return {'project_id':code,'project_name':'Studio Project','images_done':1,'chat_connected':None,'studio_tab_open':None}
  m=StudioMonitor(reader=reader,max_recovery=3,recovery_delay=0)
  m.configure('abcdefghijklmnop');m.poll();s=m.snapshot()
  self.assertEqual(s['status'],'connected');self.assertEqual(s['data']['project_name'],'Studio Project');self.assertEqual(s['refresh_count'],2);self.assertEqual(s['failure_count'],0)
 def test_keeps_checkpoint_data_when_recovery_exhausted(self):
  calls=[]
  def reader(code):
   calls.append(code)
   if len(calls)==1:return {'project_id':code,'images_done':7}
   raise OSError('offline')
  m=StudioMonitor(reader=reader,max_recovery=2,recovery_delay=0);m.configure('abcdefghijklmnop');m.poll();m.poll();s=m.snapshot()
  self.assertEqual(s['status'],'lost');self.assertEqual(s['data']['images_done'],7);self.assertEqual(s['failure_count'],1);self.assertEqual(s['refresh_count'],2)
 def test_invalid_cannot_replace_current(self):
  m=StudioMonitor(reader=lambda _:{});m.configure('abcdefghijklmnop')
  with self.assertRaises(ValueError):m.configure('bad')
  self.assertTrue(m.snapshot()['configured'])
if __name__=='__main__':unittest.main()
