"""Windows process/window adapters. No fixed screen coordinates."""
import os, sys, time, subprocess
from pathlib import Path

class WindowNotFoundError(RuntimeError):
 pass

class WindowChoiceRequired(RuntimeError):
 pass

class WindowLostError(RuntimeError):
 pass

APPS={'edge':{'names':['msedge.exe']},'chrome':{'names':['chrome.exe']},'capcut':{'names':['capcut.exe']},'test':{'names':['python.exe','pythonw.exe']}}

def require_windows():
 if sys.platform!='win32':raise RuntimeError('Windows Automation cần máy Windows; không mô phỏng thành công trên hệ điều hành khác.')

def processes():
 require_windows();import psutil
 rows=[]
 for p in psutil.process_iter(['pid','name','exe','create_time']):
  try:rows.append(p.info)
  except (psutil.NoSuchProcess,psutil.AccessDenied):pass
 return rows

def windows(app=None,title=None):
 require_windows();import win32gui,win32process,psutil,pywintypes
 rows=[]
 def visit(hwnd,_):
  try:
   if not win32gui.IsWindowVisible(hwnd):return
   text=win32gui.GetWindowText(hwnd)
   if not text:return
   _,pid=win32process.GetWindowThreadProcessId(hwnd);p=psutil.Process(pid);name=p.name().lower()
   if app and name not in APPS.get(app,{}).get('names',[]):return
   if app=='test' and text!='AI MANAGER Automation Test':return
   if title and title.casefold() not in text.casefold():return
   rows.append({'hwnd':hwnd,'pid':pid,'process':name,'title':text,'process_started':p.create_time()})
  except (OSError,psutil.Error,pywintypes.error):pass
 win32gui.EnumWindows(visit,None);return rows

def find_window(app, title=None):
 if app not in APPS:raise ValueError('Ứng dụng chưa được cấu hình')
 rows=windows(app,title)
 if not rows:raise WindowNotFoundError('Không tìm thấy cửa sổ '+app)
 if len(rows)>1:raise WindowChoiceRequired('Có nhiều cửa sổ '+app+'. Chọn đúng cửa sổ bằng HWND hoặc title trước khi điều khiển.')
 return rows[0]

def validate_target(target,foreground=False):
 require_windows();import win32gui,win32process,psutil
 app=target.get('target_app');hwnd=int(target.get('hwnd') or 0)
 if app not in APPS or not hwnd or not win32gui.IsWindow(hwnd):raise WindowLostError('Cửa sổ đích không còn tồn tại')
 _,pid=win32process.GetWindowThreadProcessId(hwnd);p=psutil.Process(pid)
 if p.name().lower() not in APPS[app]['names']:raise RuntimeError('Cửa sổ không thuộc ứng dụng đích')
 if target.get('pid') and pid!=int(target['pid']):raise RuntimeError('PID cửa sổ đã thay đổi')
 if target.get('process_started') and abs(p.create_time()-target['process_started'])>.01:raise RuntimeError('PID đã được tái sử dụng')
 if app=='test' and win32gui.GetWindowText(hwnd)!='AI MANAGER Automation Test':raise RuntimeError('Không phải cửa sổ test an toàn')
 if app=='edge':
  from .edge_controller import verify_binding
  verify_binding(dict(target,pid=pid,process_started=p.create_time()))
 if foreground and win32gui.GetForegroundWindow()!=hwnd:raise RuntimeError('Cửa sổ đích không có focus; đã chặn nhập/click để bảo vệ ứng dụng khác')
 import ctypes
 if ctypes.windll.user32.IsHungAppWindow(hwnd):raise RuntimeError('Windows báo cửa sổ không phản hồi')
 return hwnd

def focus(target):
 require_windows();import win32gui,win32con
 hwnd=validate_target(target);win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
 from pywinauto import Desktop
 Desktop(backend='uia').window(handle=hwnd).set_focus()
 validate_target(target,True);return {'context':target,'focused':True}

def set_state(target,state):
 require_windows();import win32gui,win32con
 hwnd=validate_target(target);code={'RESTORE':win32con.SW_RESTORE,'MAXIMIZE':win32con.SW_MAXIMIZE,'MINIMIZE':win32con.SW_MINIMIZE}[state];win32gui.ShowWindow(hwnd,code)
 return {'context':target,'window_state':state}

def close(target):
 require_windows();import win32gui,win32con
 hwnd=validate_target(target);win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  if not win32gui.IsWindow(hwnd):return {'closed':True}
  time.sleep(.1)
 raise RuntimeError('Cửa sổ chưa đóng; có thể đang chờ lưu dữ liệu. Không cưỡng bức đóng.')

def executable(app,settings=None):
 require_windows();settings=settings or {}
 if app not in ('chrome','edge','capcut'):raise ValueError('Chỉ mở Chrome, Edge hoặc CapCut')
 configured=settings.get(app+'_path')
 candidates=[]
 if configured:candidates.append(Path(configured))
 if app in ('chrome','edge'):
  import winreg
  for key in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
   try:
    with winreg.OpenKey(key,'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\'+APPS[app]['names'][0]) as reg:candidates.append(Path(winreg.QueryValue(reg,None)))
   except OSError:pass
  for env in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
   if os.environ.get(env):candidates.append(Path(os.environ[env])/('Microsoft/Edge/Application/msedge.exe' if app=='edge' else 'Google/Chrome/Application/chrome.exe'))
 else:
  local=Path(os.environ.get('LOCALAPPDATA',''))
  candidates.extend([local/'CapCut/Apps/CapCut.exe',local/'Programs/CapCut/CapCut.exe'])
  if (local/'CapCut/Apps').is_dir():candidates.extend(sorted((local/'CapCut/Apps').glob('*/CapCut.exe'),reverse=True))
 for p in candidates:
  if p.is_file() and p.name.lower()==APPS[app]['names'][0]:return str(p.resolve())
 raise RuntimeError('Không tìm thấy '+app+'. Điền đường dẫn '+APPS[app]['names'][0]+' trong Automation Test → Cài đặt.')

def open_app(app,settings=None):
 existing=windows(app)
 if existing:return {'already_running':True,'windows':existing,'context':dict(existing[0],target_app=app) if len(existing)==1 else {'target_app':app}}
 exe=executable(app,settings);args=[exe]
 if app=='chrome':args+=['--force-renderer-accessibility','--new-window','about:blank']
 proc=subprocess.Popen(args,shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_BREAKAWAY_FROM_JOB',0));return {'launched_pid':proc.pid,'context':{'target_app':app}}
