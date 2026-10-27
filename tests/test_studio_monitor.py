import unittest
from studio_monitor import StudioMonitor
class TestStudioMonitor(unittest.TestCase):
 def test_poll_and_reconnect(self):
  calls=[]
  def reader(code):
   calls.append(code)
   if len(calls)==2: raise OSError('offline')
   return {'project_id':code,'images_done':len(calls),'chat_connected':None,'studio_tab_open':None}
  m=StudioMonitor(reader=reader)
  m.configure('abcdefghijklmnop'); m.poll(); self.assertEqual(m.snapshot()['status'],'connected')
  m.poll(); self.assertEqual(m.snapshot()['status'],'lost'); self.assertEqual(m.snapshot()['data']['images_done'],1)
  m.poll(); self.assertEqual(m.snapshot()['status'],'connected'); self.assertEqual(m.snapshot()['data']['images_done'],3)
 def test_invalid_cannot_replace_current(self):
  m=StudioMonitor(reader=lambda _:{});m.configure('abcdefghijklmnop')
  with self.assertRaises(ValueError):m.configure('bad')
  self.assertTrue(m.snapshot()['configured'])
if __name__=='__main__':unittest.main()
