"""Existing Edge profiles, UIA version-page proof, durable exact-window binding."""
import json,os,time,subprocess,secrets
from pathlib import Path
from . import window_manager as wm
from .edge_profiles import list_profiles,require_profile,user_data_root,matches_profile_path
from .browser_controller import BrowserController

def binding_file():
 return Path(os.environ['AI_MANAGER_AGENT_HOME'])/'edge_windows.json'

def bindings():
 try:return json.loads(binding_file().read_text(encoding='utf8'))
 except (OSError,ValueError):return {}

def verified_windows(profile=None):
 known=bindings();out=[]
 for w in wm.windows('edge'):
  b=known.get(str(w['hwnd']))
  if b and b['pid']==w['pid'] and b['process_started']==w['process_started'] and (not profile or b['browser_profile']==profile):
   t=dict(w,browser='edge',**{k:b[k] for k in ('browser_profile','browser_profile_name')})
   try:verify_binding(t)
   except (RuntimeError,ValueError):continue
   out.append(t)
 return out

def verify_binding(target):
 profile=target.get('browser_profile');require_profile(profile)
 b=bindings().get(str(target.get('hwnd')))
 import win32gui
 if not b or not b.get('window_nonce') or win32gui.GetProp(int(target.get('hwnd') or 0),'AI_MANAGER_EDGE_PROFILE')!=b['window_nonce'] or any(b.get(k)!=target.get(k) for k in ('pid','process_started','browser_profile')):
  raise RuntimeError('Chưa xác minh đúng Edge Profile/cửa sổ. Chọn profile rồi bấm Mở Edge trước.')

def prove_window(w,profile):
 # Read-only inspection of diagnostic page, no input to an unverified window.
 from pywinauto import Desktop
 win=Desktop(backend='uia').window(handle=w['hwnd'])
 bars=win.descendants(control_type='Edit')
 diagnostic=False
 for bar in bars:
  info=bar.element_info
  if info.class_name=='OmniboxViewViews' or info.automation_id in ('addressEditBox','view_1020'):
   try:diagnostic=bar.get_value().rstrip('/')=='edge://version'
   except Exception:continue
   if diagnostic:break
 if not diagnostic:return False
 texts=[]
 for c in win.descendants(control_type='Text'):
  texts.extend(c.window_text().splitlines())
 return matches_profile_path(texts,user_data_root()/profile)

class EdgeController(BrowserController):
 def __init__(self,target):
  verify_binding(target);super().__init__(target)
 @staticmethod
 def open(profile,settings=None):
  wm.require_windows();meta=require_profile(profile)
  rows=verified_windows(profile)
  if len(rows)>1:raise wm.WindowChoiceRequired('Có nhiều cửa sổ Edge đã xác minh. Chọn cửa sổ trước khi chạy.')
  if rows:return {'already_running':True,'context':dict(rows[0],target_app='edge'),'windows':rows}
  # Adopt an already-open version page if it proves the exact profile.
  before=wm.windows('edge')
  matches=[w for w in before if prove_window(w,profile)]
  if not matches:
   exe=wm.executable('edge',settings)
   subprocess.Popen([exe,'--profile-directory='+profile,'--force-renderer-accessibility','--new-window','edge://version/'],shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_BREAKAWAY_FROM_JOB',0))
   deadline=time.monotonic()+35
   while time.monotonic()<deadline:
    matches=[w for w in wm.windows('edge') if prove_window(w,profile)]
    if matches:break
    time.sleep(.4)
  if len(matches)!=1:raise RuntimeError('Không xác minh được duy nhất cửa sổ Edge Profile. Mở edge://version trong profile đã chọn rồi thử lại. Không thao tác vào trang khác.')
  context=dict(matches[0],target_app='edge',browser='edge',browser_profile=profile,browser_profile_name=meta['name'])
  import win32gui
  context['window_nonce']=secrets.randbelow(2**30)+1
  win32gui.SetProp(context['hwnd'],'AI_MANAGER_EDGE_PROFILE',context['window_nonce'])
  data=bindings();data[str(context['hwnd'])]=context
  path=binding_file();path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data),encoding='utf8');tmp.replace(path)
  return {'context':context,'profile_verified':True,'windows':[context]}
