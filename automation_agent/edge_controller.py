"""Existing Edge profiles, UIA version-page proof, durable exact-window binding."""
import json,os,time,subprocess
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
 from .edge_bindings import validate_record,validate_live
 from .edge_native import window_profile_report
 profile=target.get('browser_profile');require_profile(profile)
 record=bindings().get(str(target.get('hwnd')))
 validate_record(target,record)
 live=next((w for w in wm.windows('edge') if w['hwnd']==target.get('hwnd')),None)
 if not live:validate_live(record,None,{})
 validate_live(record,live,window_profile_report(live,profile))

def toolbar_profile_matches(names,profile,profiles):
 selected=next((p for p in profiles if p['directory']==profile),None)
 if not selected:return False
 name=selected['name']
 if sum(p['name']==name for p in profiles)!=1:return False
 return name in names

def native_profile_names(win):
 names=[]
 # Never use title, bookmarks, arbitrary page text or a page-created toolbar.
 for c in win.descendants(control_type='Button'):
  i=c.element_info
  if i.automation_id not in ('profile-button','avatarToolbarButton','profileButton') and i.class_name not in ('AvatarToolbarButton','AvatarToolbarButtonView','BrowserProfileButton','ProfileToolbarButton'):continue
  parent=c
  for _ in range(20):
   if parent.element_info.control_type=='Document':break
   if parent.element_info.handle==win.handle:
    names.append(c.window_text());break
   try:parent=parent.parent()
   except Exception:break
 return names

def inspect_window_profile(w,profile):
 # No conversation/page text is exported. Only counts, native IDs and proof booleans.
 from pywinauto import Desktop
 report={'hwnd':w['hwnd'],'pid':w['pid'],'profile':profile,'verified':False,'address_control_found':False,'version_page':False,'profile_path_match':False}
 try:
  win=Desktop(backend='uia').window(handle=w['hwnd'])
  native=native_profile_names(win)
  report['native_profile_match']=toolbar_profile_matches(native,profile,list_profiles())
  if report['native_profile_match']:report['verified']=True;return report
  bars=win.descendants(control_type='Edit');report['edit_count']=len(bars)
  report['native_edit_controls']=[{'class':b.element_info.class_name,'id':b.element_info.automation_id} for b in bars if b.element_info.class_name=='OmniboxViewViews' or b.element_info.automation_id in ('addressEditBox','view_1020') or b.element_info.name in ('Address and search bar','Thanh địa chỉ và tìm kiếm')]
  for bar in bars:
   info=bar.element_info
   if info.class_name=='OmniboxViewViews' or info.automation_id in ('addressEditBox','view_1020') or info.name in ('Address and search bar','Thanh địa chỉ và tìm kiếm'):
    report['address_control_found']=True
    try:
     value=bar.get_value().strip().rstrip('/')
     report['version_page']=value=='edge://version'
    except Exception as exc:report['address_error']=type(exc).__name__
    if report['version_page']:break
  if not report['version_page']:return report
  controls=win.descendants(control_type='Text');report['text_count']=len(controls)
  texts=[]
  for c in win.descendants(auto_id='profile_path')+controls:texts.extend(c.window_text().splitlines())
  report['profile_path_match']=matches_profile_path(texts,user_data_root()/profile)
  report['verified']=report['profile_path_match']
 except Exception as exc:report['inspection_error']=type(exc).__name__
 return report

def prove_window(w,profile):return inspect_window_profile(w,profile)['verified']

def diagnostics(profile):
 require_profile(profile)
 rows=wm.windows('edge')
 from .edge_native import window_profile_report
 return {'profile':profile,'window_count':len(rows),'windows':[window_profile_report(w,profile) for w in rows[:10]],'truncated':len(rows)>10,'read_only':True}

def matching_windows(rows,profile):
 matches=[]
 for w in rows:
  try:
   if prove_window(w,profile):matches.append(w)
  except Exception:
   # A stale/inaccessible window is not proof and must not abort other windows.
   continue
 return matches

def native_matching_windows(rows,profile):
 from .edge_native import window_profile_report
 reports=[window_profile_report(w,profile) for w in rows]
 valid={r['hwnd'] for r in reports if r['verified']}
 return [w for w in rows if w['hwnd'] in valid],reports

class EdgeController(BrowserController):
 def __init__(self,target):
  verify_binding(target);super().__init__(target)
 def address_bar(self):
  try:return super().address_bar()
  except RuntimeError as exc:raise RuntimeError(str(exc).replace('Chrome','Edge')) from exc
 @staticmethod
 def open(profile,settings=None):
  wm.require_windows();meta=require_profile(profile)
  rows=verified_windows(profile)
  if rows:return {'already_running':True,'context':dict(rows[0],target_app='edge') if len(rows)==1 else {'target_app':'edge','browser':'edge','browser_profile':profile},'windows':rows}
  matches,reports=native_matching_windows(wm.windows('edge'),profile)
  if not matches:
   # One launch per minute/profile even after timeout; repeated clicks do not spawn windows.
   launch_path=binding_file().with_name('edge_launches.json')
   try:launches=json.loads(launch_path.read_text(encoding='utf8'))
   except (OSError,ValueError):launches={}
   if time.time()-float(launches.get(profile,0))>=60:
    exe=wm.executable('edge',settings)
    launch_path.parent.mkdir(parents=True,exist_ok=True);launches[profile]=time.time()
    tmp=launch_path.with_suffix('.tmp');tmp.write_text(json.dumps(launches),encoding='utf8');tmp.replace(launch_path)
    subprocess.Popen([exe,'--profile-directory='+profile,'--force-renderer-accessibility','--new-window','about:blank'],shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_BREAKAWAY_FROM_JOB',0))
   deadline=time.monotonic()+12
   while time.monotonic()<deadline:
    matches,reports=native_matching_windows(wm.windows('edge'),profile)
    if matches:break
    time.sleep(.4)
  # Keep safe diagnostics automatically, with no URLs, page text or credentials.
  report_path=binding_file().with_name('edge_last_verification.json')
  report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps({'profile':profile,'windows':reports}),encoding='utf8')
  if not matches:
   causes=sorted({r.get('native_error','không có thuộc tính profile phù hợp') for r in reports})
   raise RuntimeError('Edge đã mở nhưng Windows chưa xác nhận profile. Đã dừng xác minh; không tự mở thêm cửa sổ. Chi tiết: '+', '.join(causes or ['không thấy cửa sổ Edge']))
  from .edge_bindings import make_record
  data=bindings();contexts=[]
  for w in matches:
   context=make_record(w,profile,meta['name'])
   data[str(context['hwnd'])]=context;contexts.append(context)
  path=binding_file();tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data),encoding='utf8');tmp.replace(path)
  return {'context':contexts[0] if len(contexts)==1 else {'target_app':'edge','browser':'edge','browser_profile':profile},'profile_verified':True,'windows':contexts}
