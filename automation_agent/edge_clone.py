"""Clone the Edge profile that is logged in to ChatGPT into a new profile, so an extra ChatGPT tab can run
in parallel without logging in again. Same Edge "User Data" folder, so the copied login stays readable.

Only while Edge is closed (its files are locked otherwise). Caches, history, saved passwords and form data
are not copied. "Local State" is backed up before the new profile is added to Edge's profile list."""
import json,os,re,shutil,subprocess,time
from pathlib import Path

SKIP_DIRS={'Cache','Code Cache','GPUCache','DawnCache','DawnGraphiteCache','DawnWebGPUCache','GrShaderCache','ShaderCache',
 'CacheStorage','ScriptCache','Sessions','blob_storage','Download Service','Crashpad','optimization_guide_hint_cache_store',
 'optimization_guide_model_and_features_store','Feature Engagement Tracker','VideoDecodeStats','BudgetDatabase'}
SKIP_FILES={'History','History-journal','Visited Links','Top Sites','Top Sites-journal','Login Data','Login Data-journal',
 'Login Data For Account','Login Data For Account-journal','Web Data','Web Data-journal','Favicons','Favicons-journal',
 'Shortcuts','Shortcuts-journal','LOCK','lockfile','Network Action Predictor','Network Action Predictor-journal'}

def user_data(base=None):return Path(base or Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft'/'Edge'/'User Data')

def edge_running():
 try:
  out=subprocess.run(['tasklist','/FI','IMAGENAME eq msedge.exe','/NH'],capture_output=True,text=True,timeout=10).stdout
  return 'msedge.exe' in out.lower()
 except (OSError,subprocess.SubprocessError):return False

def close_edge(wait=20,running=edge_running,run=subprocess.run,sleep=time.sleep):
 """Ask Edge to close (it saves its state), force only what is still left after the wait."""
 if not running():return True
 run(['taskkill','/IM','msedge.exe','/T'],capture_output=True,timeout=15)
 for _ in range(wait*2):
  if not running():return True
  sleep(.5)
 run(['taskkill','/IM','msedge.exe','/T','/F'],capture_output=True,timeout=15)
 for _ in range(20):
  if not running():return True
  sleep(.5)
 return not running()

def next_profile(ud,state):
 used={p.name for p in Path(ud).iterdir() if p.is_dir()}|set((state.get('profile') or {}).get('info_cache',{}))
 n=max([int(m.group(1)) for x in used if (m:=re.fullmatch(r'Profile (\d+)',x))]+[0])+1
 return 'Profile '+str(n)

def _ignore(_dir,names):return [n for n in names if n in SKIP_DIRS or n in SKIP_FILES or n.endswith('.tmp')]

def _write_json(path,data):
 tmp=path.with_name(path.name+'.ai-manager-tmp')
 tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');os.replace(tmp,path)

def clone(source='Default',name='ChatGPT 2',base=None,running=edge_running,clock=time.time):
 ud=user_data(base);src=ud/source;local_state=ud/'Local State'
 if running():raise RuntimeError('Edge đang mở; cần đóng Edge trước khi nhân bản hồ sơ.')
 if not src.is_dir():raise ValueError('Không thấy hồ sơ Edge nguồn: '+source)
 state=json.loads(local_state.read_text(encoding='utf8'))
 target=next_profile(ud,state);dst=ud/target;tmp=ud/(target+'.ai-manager-copy')
 # Copy to a temporary folder first; a failed copy never leaves a half profile behind.
 shutil.rmtree(tmp,ignore_errors=True)
 try:shutil.copytree(src,tmp,ignore=_ignore)
 except Exception:
  shutil.rmtree(tmp,ignore_errors=True);raise RuntimeError('Không chép được hồ sơ (Edge có thể vừa mở lại). Chưa thay đổi gì; thử lại.')
 os.replace(tmp,dst)
 prefs_path=dst/'Preferences'
 try:prefs=json.loads(prefs_path.read_text(encoding='utf8'))
 except (OSError,ValueError):prefs={}
 prefs.setdefault('profile',{})['name']=name
 _write_json(prefs_path,prefs)
 shutil.copy2(local_state,ud/('Local State.ai-manager-backup-'+str(int(clock()))))
 profile=state.setdefault('profile',{});cache=profile.setdefault('info_cache',{})
 cache[target]=dict(cache.get(source,{}),name=name,is_using_default_name=False)
 order=profile.setdefault('profiles_order',list(cache))
 if target not in order:order.append(target)
 _write_json(local_state,state)
 return {'profile':target,'name':name,'path':str(dst)}

def open_profiles(profiles,exe=None,popen=subprocess.Popen):
 from . import window_manager as wm
 exe=exe or wm.executable('edge')
 for p in profiles:popen([exe,'--profile-directory='+p,'https://chatgpt.com/'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_BREAKAWAY_FROM_JOB',0))
