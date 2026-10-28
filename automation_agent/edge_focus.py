"""Bounded Edge-only foreground validation; never chooses a new target."""
import json,os,time
from pathlib import Path

def snapshot(hwnd):
 import win32gui,win32process,psutil
 row={'hwnd':hwnd,'exists':bool(win32gui.IsWindow(hwnd))}
 if not row['exists']:return row
 _,pid=win32process.GetWindowThreadProcessId(hwnd)
 row.update(pid=pid,exe=psutil.Process(pid).name().lower(),visible=bool(win32gui.IsWindowVisible(hwnd)),iconic=bool(win32gui.IsIconic(hwnd)),root=win32gui.GetAncestor(hwnd,2),owner=win32gui.GetAncestor(hwnd,3),window_class=win32gui.GetClassName(hwnd))
 return row

def matches(target,foreground):
 return bool(target.get('exists') and foreground.get('exists') and target.get('visible') and not target.get('iconic') and target.get('exe')=='msedge.exe' and foreground.get('exe')=='msedge.exe' and target.get('pid')==foreground.get('pid') and target.get('owner') and target['owner']==foreground.get('owner'))

def check(target,raise_error=True):
 import win32gui
 expected=snapshot(int(target['hwnd']));actual=snapshot(win32gui.GetForegroundWindow())
 if matches(expected,actual):return True
 if not raise_error:return False
 report={'at':time.time(),'target':expected,'foreground':actual,'profile':target.get('browser_profile'),'since_focus_seconds':time.time()-target['focus_verified_at'] if target.get('focus_verified_at') else None}
 path=Path(os.environ['AI_MANAGER_AGENT_HOME'])/'edge_focus_failure.json'
 path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 raise RuntimeError('Edge chưa có focus an toàn; foreground='+str(actual.get('exe','không có cửa sổ'))+'. Đã chặn nhập. Chẩn đoán: '+str(path))

def acquire(target):
 import win32gui,win32con
 from pywinauto import Desktop
 from .window_manager import validate_target
 hwnd=validate_target(target)
 if not check(target,False):
  win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
  Desktop(backend='uia').window(handle=hwnd).set_focus() # exactly one attempt
 deadline=time.monotonic()+1
 while time.monotonic()<deadline:
  validate_target(target)
  if check(target,False):
   target=dict(target,focus_verified_at=time.time())
   return {'context':target,'focused':True}
  time.sleep(.05)
 check(target)
