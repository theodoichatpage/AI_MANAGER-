"""App-level tools: update from GitHub, back up / restore everything needed to move to another PC, and a
checklist of what this PC still needs (Edge profiles, Extension, ChatGPT, Local Engine...)."""
import json,os,re,shutil,sqlite3,subprocess,sys,threading,time,urllib.request,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BACKUPS=Path(os.environ.get('USERPROFILE',str(Path.home())))/'Documents'/'AI_MANAGER_Backups'
NO_WINDOW=0x08000000

# ------------------------------------------------------------------ update
def git(*args,timeout=60):
 r=subprocess.run(['git','-C',str(ROOT),*args],capture_output=True,text=True,timeout=timeout,creationflags=NO_WINDOW)
 if r.returncode:raise RuntimeError((r.stderr or r.stdout).strip()[:300] or 'git lỗi')
 return r.stdout.strip()

def update_check():
 try:
  branch=git('rev-parse','--abbrev-ref','HEAD');git('fetch','--quiet','origin',branch,timeout=90)
  behind=int(git('rev-list','--count','HEAD..origin/'+branch));dirty=bool(git('status','--porcelain','--untracked-files=no'))
  notes=git('log','--format=%s','-n','10','HEAD..origin/'+branch).splitlines() if behind else []
  return {'ok':True,'branch':branch,'behind':behind,'dirty':dirty,'current':git('rev-parse','--short','HEAD'),'notes':notes}
 except FileNotFoundError:return {'ok':False,'error':'Máy chưa có Git; không tự cập nhật được.'}
 except Exception as exc:return {'ok':False,'error':str(exc)}

def update_apply(busy):
 """Fast-forward to GitHub only when nothing runs and nothing local would be overwritten, then restart."""
 if busy:raise ValueError('Đang có dự án chạy; dừng hoặc chờ xong rồi cập nhật.')
 info=update_check()
 if not info.get('ok'):raise ValueError(info.get('error'))
 if info['dirty']:raise ValueError('Thư mục AI Manager có thay đổi chưa lưu; không cập nhật để tránh ghi đè.')
 if not info['behind']:return dict(info,updated=False)
 git('merge','--ff-only','origin/'+info['branch'])
 restart()
 return dict(info,updated=True)

def restart():
 """Start the launcher in 'restart' mode, then stop this server shortly after the reply is sent."""
 pythonw=Path(sys.executable).with_name('pythonw.exe')
 subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable),str(ROOT/'app_launcher.pyw'),'--restart','--background'],cwd=str(ROOT),creationflags=NO_WINDOW|0x00000008,close_fds=True)
 threading.Timer(1.5,lambda:os._exit(0)).start()

# ------------------------------------------------------------------ backup / restore
STATE={'running':False,'done':0,'total':0,'path':None,'error':None,'kind':None}
def _settings_files(base):
 base=Path(base);return [(p,'settings/'+p.relative_to(base).as_posix()) for p in (base/'config.json',base/'automation'/'settings.json') if p.is_file()]

def backup(root,base,dest=BACKUPS):
 """Zip every project folder (not the trash) and Manager's settings into Documents\\AI_MANAGER_Backups."""
 root=Path(root);dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 files=[(p,'projects/'+p.relative_to(root).as_posix()) for p in root.rglob('*') if p.is_file() and not p.relative_to(root).parts[0].startswith(('_Thung_rac','.')) and len(p.relative_to(root).parts)>1 and '.tmp-' not in p.name]
 files+=_settings_files(base)
 target=dest/('AI_Manager_backup_'+time.strftime('%Y%m%d_%H%M%S')+'.zip');tmp=Path(str(target)+'.part')
 STATE.update(running=True,done=0,total=len(files),path=str(target),error=None,kind='backup')
 try:
  with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
   z.writestr('manifest.json',json.dumps({'app':'AI Manager','created':time.strftime('%Y-%m-%d %H:%M:%S'),'root':str(root),'files':len(files)},ensure_ascii=False))
   for path,name in files:
    stored=path.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.zip')
    z.write(path,name,compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED);STATE['done']+=1
  tmp.replace(target);return {'path':str(target),'files':len(files),'size':target.stat().st_size}
 except Exception as exc:
  STATE['error']=str(exc)[:300];tmp.unlink(missing_ok=True);raise
 finally:STATE['running']=False

def backups(dest=BACKUPS):
 dest=Path(dest)
 return [{'path':str(p),'name':p.name,'size':p.stat().st_size,'at':p.stat().st_mtime} for p in sorted(dest.glob('AI_Manager_backup_*.zip'),reverse=True)] if dest.exists() else []

def restore(path,root,base,busy):
 """Put projects from a backup into the projects folder. Existing project folders are never overwritten."""
 if busy:raise ValueError('Đang có dự án chạy; dừng trước khi khôi phục.')
 path=Path(path);root=Path(root);base=Path(base)
 if not path.is_file() or path.suffix.lower()!='.zip':raise ValueError('Chọn tệp sao lưu .zip')
 added=set();skipped=set();settings=[]
 STATE.update(running=True,done=0,total=0,path=str(path),error=None,kind='restore')
 try:
  with zipfile.ZipFile(path) as z:
   if 'manifest.json' not in z.namelist():raise ValueError('Đây không phải tệp sao lưu của AI Manager')
   names=[n for n in z.namelist() if not n.endswith('/')];STATE['total']=len(names)
   for n in names:
    parts=n.split('/')
    if any(p in ('','.','..') for p in parts) or ':' in n or '\\' in n:raise ValueError('Tên tệp lạ trong bản sao lưu: '+n)
   existing={p.name for p in root.iterdir()} if root.exists() else set()
   for n in names:
    STATE['done']+=1;parts=n.split('/')
    if parts[0]=='projects' and len(parts)>2:
     folder=parts[1]
     if folder in existing and folder not in added:skipped.add(folder);continue
     added.add(folder);out=root.joinpath(*parts[1:])
    elif parts[0]=='settings' and len(parts)>1:
     out=base.joinpath(*parts[1:])
     if out.exists():continue
     settings.append(n)
    else:continue
    out.parent.mkdir(parents=True,exist_ok=True)
    with z.open(n) as src,open(out,'wb') as dst:shutil.copyfileobj(src,dst)
  return {'added':sorted(added),'skipped':sorted(skipped),'settings':settings}
 except Exception as exc:STATE['error']=str(exc)[:300];raise
 finally:STATE['running']=False

# ------------------------------------------------------------------ this PC's checklist
EDGE_DATA=Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft'/'Edge'/'User Data'
def edge_profiles(data=EDGE_DATA):
 try:cache=json.loads((Path(data)/'Local State').read_text(encoding='utf8')).get('profile',{}).get('info_cache',{})
 except (OSError,ValueError):return []
 return [{'directory':k,'name':v.get('name') or k} for k,v in cache.items()]

def bridge_in_profile(directory,data=EDGE_DATA):
 from extension_updater import BRIDGE_NAME
 for prefs in ('Secure Preferences','Preferences'):
  try:settings=json.loads((Path(data)/directory/prefs).read_text(encoding='utf8')).get('extensions',{}).get('settings',{})
  except (OSError,ValueError):continue
  for row in settings.values():
   p=Path(str((row or {}).get('path') or ''))
   try:
    m=json.loads((p/'manifest.json').read_text(encoding='utf8'))
    if p.is_absolute() and m.get('name')==BRIDGE_NAME:return m.get('version')
   except (OSError,ValueError):continue
 return None

def keeps_sites_active(directory,data=EDGE_DATA):
 """True/False when Edge's 'Always keep these sites active' list is readable, None when not found."""
 try:text=(Path(data)/directory/'Preferences').read_text(encoding='utf8')
 except OSError:return None
 m=re.search(r'"sleeping_tabs"\s*:\s*\{[^{}]*?"(?:exceptions|exclusion_list|site_list)"\s*:\s*\[([^\]]*)\]',text)
 if not m:return None
 return 'vercel.app' in m.group(1) and 'chatgpt.com' in m.group(1)

def engine_health():
 try:
  with urllib.request.urlopen('http://127.0.0.1:17841/v1/health',timeout=3) as r:return json.loads(r.read())
 except Exception:return None

def setup_check(root,agent_online,workers,lanes_profiles):
 """Items with state ok / warn / missing and what to do. workers: live Studio tabs (with account/extension)."""
 items=[];add=lambda key,label,state,detail,fix='':items.append({'key':key,'label':label,'state':state,'detail':detail,'fix':fix})
 from install_app import installed
 shortcuts=installed()
 add('app','Biểu tượng AI Manager, tự chạy cùng Windows','ok' if all(shortcuts.values()) else 'missing',
     ', '.join(k for k,v in {'Desktop':shortcuts['desktop'],'menu Start':shortcuts['start'],'chạy cùng Windows':shortcuts['startup']}.items() if v) or 'Chưa cài','Bấm “Cài thành ứng dụng”.')
 add('agent','Windows Agent','ok' if agent_online else 'missing','Đã kết nối' if agent_online else 'Chưa kết nối','Mở lại AI Manager; Agent tự chạy.')
 root=Path(root);count=len(list(root.glob('*/project.json'))) if root.exists() else 0
 add('projects','Thư mục dự án','ok' if root.exists() else 'missing',str(root)+' · '+str(count)+' dự án','Khôi phục từ bản sao lưu nếu vừa chuyển máy.')
 edge=next((Path(b)/'Microsoft'/'Edge'/'Application'/'msedge.exe' for b in (os.environ.get('ProgramFiles(x86)'),os.environ.get('ProgramFiles')) if b and (Path(b)/'Microsoft'/'Edge'/'Application'/'msedge.exe').exists()),None)
 add('edge','Microsoft Edge','ok' if edge else 'missing',str(edge or 'Không tìm thấy'),'Cài Microsoft Edge.')
 profiles=edge_profiles()
 for prof in profiles:
  version=bridge_in_profile(prof['directory']);active=keeps_sites_active(prof['directory'])
  live=[w for w in workers if str(w.get('lane_id') or '').endswith('_'+prof['directory'].replace(' ','_'))]
  account=next((w.get('account_label') for w in live if w.get('account_label')),None)
  state='ok' if version and active is not False else 'missing' if not version else 'warn'
  detail=('Extension '+version if version else 'Chưa cài Extension')+(' · ChatGPT: '+account if account else ' · ChatGPT: chưa thấy kết nối (mở một dự án để kiểm tra)')
  if active is False:detail+=' · chưa thêm vercel.app/chatgpt.com vào “Always keep these sites active”'
  fix='Mở edge://extensions ở hồ sơ này, bật Developer mode, Load unpacked thư mục '+str(Path(os.environ.get('LOCALAPPDATA',''))/'AI_MANAGER'/'chatgpt-extension')+'; đăng nhập chatgpt.com.' if not version else 'edge://settings/system → Always keep these sites active: thêm [*.]vercel.app và chatgpt.com.' if active is False else ''
  add('profile:'+prof['directory'],'Hồ sơ Edge “'+prof['name']+'”',state,detail,fix)
 missing_lanes=[x for x in lanes_profiles if x not in {p['directory'] for p in profiles}]
 if missing_lanes:add('lanes','Hồ sơ ChatGPT phụ','missing','Dự án dùng hồ sơ chưa có: '+', '.join(missing_lanes),'Cài đặt → “+ Tạo hồ sơ ChatGPT phụ”.')
 health=engine_health()
 add('engine','Local Engine (tách ảnh)','ok' if health else 'warn','Đang chạy · '+str(health.get('device','')) if health else 'Chưa chạy','Mở Local Engine (start_engine) khi cần tách ảnh; máy mới phải cài lại Local Engine.')
 exe=next((p for p in (Path(os.environ.get('USERPROFILE',''))/'Desktop'/'Parallax25D.exe',) if p.exists()),None)
 add('parallax','Parallax25D.exe (làm video 2.5D)','ok' if exe else 'warn',str(exe or 'Không thấy trên Desktop'),'Chép Parallax25D.exe ra Desktop.')
 try:subprocess.run(['git','--version'],capture_output=True,timeout=10,creationflags=NO_WINDOW);git_ok=True
 except Exception:git_ok=False
 add('git','Git (để tự cập nhật AI Manager)','ok' if git_ok else 'warn','Có' if git_ok else 'Chưa cài','Cài Git for Windows.')
 last=backups()[:1]
 add('backup','Bản sao lưu gần nhất','ok' if last and time.time()-last[0]['at']<7*86400 else 'warn',time.strftime('%d/%m/%Y %H:%M',time.localtime(last[0]['at'])) if last else 'Chưa có','Bấm “Sao lưu ngay”.')
 return items


# ---- Settings popup: this PC's load, quick actions ----
def system_load(root):
 """CPU %, RAM and disk (of the drive holding the projects) for the settings popup."""
 import psutil,shutil
 vm=psutil.virtual_memory();drive=Path(root) if Path(root).exists() else Path.home()
 du=shutil.disk_usage(drive.anchor or str(drive))
 return {'cpu':psutil.cpu_percent(interval=0.3),'ram_used':vm.total-vm.available,'ram_total':vm.total,'disk_used':du.used,'disk_total':du.total,'drive':drive.anchor}

def edge_exe():
 for b in (os.environ.get('ProgramFiles(x86)'),os.environ.get('ProgramFiles')):
  if b and (Path(b)/'Microsoft'/'Edge'/'Application'/'msedge.exe').exists():return Path(b)/'Microsoft'/'Edge'/'Application'/'msedge.exe'
 return None

def temp_items(base,code=Path(__file__).resolve().parent):
 """Files that are safe to delete: diagnostic screenshots and Python caches. Never projects, images or the trash."""
 shots=[f for f in (Path(base)/'automation'/'screenshots').glob('*') if f.is_file()]
 caches=[f for d in Path(code).rglob('__pycache__') if '.git' not in d.parts for f in d.glob('*.pyc')]
 return shots+caches

def clean_temp(base):
 freed=0;count=0
 for f in temp_items(base):
  try:size=f.stat().st_size;f.unlink();freed+=size;count+=1
  except OSError:pass
 return {'files':count,'freed':freed}
