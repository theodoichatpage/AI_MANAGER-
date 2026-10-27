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

class TestStudioPresence(unittest.TestCase):
 def test_presence_expires_and_requires_matching_session(self):
  now=[100.0]
  m=StudioMonitor(reader=lambda _: {},clock=lambda:now[0]);m.configure('abcdefghijklmnop')
  self.assertFalse(m.presence('wrong-session-123',True))
  self.assertEqual(m.snapshot()['tab_status'],'unknown')
  self.assertTrue(m.presence('abcdefghijklmnop',True))
  self.assertEqual(m.snapshot()['tab_status'],'connected');self.assertEqual(m.snapshot()['chat_status'],'connected')
  now[0]+=91;self.assertEqual(m.snapshot()['tab_status'],'lost');self.assertEqual(m.snapshot()['chat_status'],'unknown')
  self.assertTrue(m.presence('abcdefghijklmnop',False));self.assertEqual(m.snapshot()['chat_status'],'disconnected')
  m.disconnect();self.assertEqual(m.snapshot()['tab_status'],'unknown')

class TestTabClose(unittest.TestCase):
 def test_close_only_matching_tab_and_reopen(self):
  now=[100.0];m=StudioMonitor(reader=lambda _: {},clock=lambda:now[0]);m.configure('abcdefghijklmnop')
  self.assertTrue(m.presence('abcdefghijklmnop',True,tab_id='tab-a'))
  self.assertTrue(m.presence('abcdefghijklmnop',True,tab_id='tab-b'))
  self.assertTrue(m.close_tab('abcdefghijklmnop','tab-a'))
  self.assertEqual(m.snapshot()['tab_status'],'connected')
  self.assertTrue(m.close_tab('abcdefghijklmnop','tab-b'))
  self.assertEqual(m.snapshot()['tab_status'],'lost')
  self.assertEqual(m.snapshot()['chat_status'],'unknown')
  self.assertTrue(m.presence('abcdefghijklmnop',False,tab_id='tab-c'))
  self.assertEqual(m.snapshot()['tab_status'],'connected')
  self.assertEqual(m.snapshot()['chat_status'],'disconnected')
 def test_bad_session_cannot_close(self):
  m=StudioMonitor(reader=lambda _: {});m.configure('abcdefghijklmnop');m.presence('abcdefghijklmnop',True,tab_id='tab-a')
  self.assertFalse(m.close_tab('notvalid','tab-a'));self.assertEqual(m.snapshot()['tab_status'],'connected')
