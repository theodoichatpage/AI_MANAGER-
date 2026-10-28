import tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from automation_agent.action_executor import ActionExecutor
class StopInputTests(unittest.TestCase):
 def test_stopping_wait_does_not_inject_mouse_or_keyboard(self):
  calls=[]
  user=types.SimpleNamespace(keybd_event=lambda *a:calls.append(('key',a)),mouse_event=lambda *a:calls.append(('mouse',a)),GetAsyncKeyState=lambda key:0)
  with tempfile.TemporaryDirectory() as td,patch('automation_agent.action_executor.sys.platform','win32'),patch('ctypes.windll',types.SimpleNamespace(user32=user),create=True):
   executor=ActionExecutor(Path(td));executor.current_action='WAIT_WINDOW';executor.cancel()
  self.assertEqual(calls,[])
 def test_unpressed_right_button_is_never_released(self):
  calls=[]
  user=types.SimpleNamespace(keybd_event=lambda *a:None,mouse_event=lambda *a:calls.append(a),GetAsyncKeyState=lambda key:0)
  with tempfile.TemporaryDirectory() as td,patch('automation_agent.action_executor.sys.platform','win32'),patch('ctypes.windll',types.SimpleNamespace(user32=user),create=True):
   executor=ActionExecutor(Path(td));executor.current_action='RIGHT_CLICK';executor.cancel()
  self.assertEqual(calls,[])
 def test_running_right_click_releases_only_held_right_button(self):
  calls=[]
  user=types.SimpleNamespace(keybd_event=lambda *a:None,mouse_event=lambda *a:calls.append(a),GetAsyncKeyState=lambda key:0x8000 if key==2 else 0)
  process=types.SimpleNamespace(poll=lambda:None,terminate=lambda:None,wait=lambda **kw:None)
  with tempfile.TemporaryDirectory() as td,patch('automation_agent.action_executor.sys.platform','win32'),patch('ctypes.windll',types.SimpleNamespace(user32=user),create=True):
   executor=ActionExecutor(Path(td));executor.current_action='RIGHT_CLICK';executor.process=process;executor.cancel()
  self.assertEqual(calls,[(0x10,0,0,0,0)])
