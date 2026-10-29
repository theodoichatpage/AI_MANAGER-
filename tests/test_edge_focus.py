import unittest
from automation_agent.edge_focus import matches
class FocusTests(unittest.TestCase):
 def setUp(self):self.t=dict(exists=True,visible=True,iconic=False,exe='msedge.exe',pid=20,owner=100)
 def test_same_owner(self):self.assertTrue(matches(self.t,dict(self.t,hwnd=101)))
 def test_other_app(self):self.assertFalse(matches(self.t,dict(self.t,exe='notepad.exe')))
 def test_other_pid(self):self.assertFalse(matches(self.t,dict(self.t,pid=21)))
 def test_closed(self):self.assertFalse(matches(dict(self.t,exists=False),self.t))
 def test_other_owner(self):self.assertFalse(matches(self.t,dict(self.t,owner=200)))
 def test_minimized(self):self.assertFalse(matches(dict(self.t,iconic=True),self.t))
