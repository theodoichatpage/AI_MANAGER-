"""Keep one fixed folder with the latest ChatGPT Bridge extension, so the user loads it into Edge once and
never re-installs: the extension notices a new version in its folder and reloads itself.
Source: the Studio repository's published release (version + ZIP) on GitHub."""
import io,json,os,re,shutil,tempfile,threading,time,urllib.request,zipfile
from pathlib import Path

RAW='https://raw.githubusercontent.com/theodoichatpage/VIDEO_IMAGE_STUDIO/phase3-manager-presence/vercel-migration/'
TARGET=Path(os.environ.get('LOCALAPPDATA') or Path.home())/'AI_MANAGER'/'chatgpt-extension'
NAME=re.compile(r'VIDEO_IMAGE_STUDIO_ChatGPT_Extension_v(\d+\.\d+\.\d+)\.zip')
MAX_ZIP=5_000_000;MAX_FILES=60;MAX_TOTAL=20_000_000

def _get(url,limit,opener=urllib.request.urlopen):
 with opener(urllib.request.Request(url,headers={'Cache-Control':'no-cache'}),timeout=20) as r:data=r.read(limit+1)
 if len(data)>limit:raise ValueError('Tệp quá lớn')
 return data

def latest(fetch=_get):
 text=fetch(RAW+'src/extensionRelease.ts',20000).decode('utf8')
 version=re.search(r'EXTENSION_VERSION\s*=\s*"(\d+\.\d+\.\d+)"',text);url=re.search(r'EXTENSION_DOWNLOAD_URL\s*=\s*"/resources/([^"]+)"',text)
 if not version or not url or not NAME.fullmatch(url.group(1)) or NAME.fullmatch(url.group(1)).group(1)!=version.group(1):raise ValueError('Không đọc được phiên bản Extension mới nhất')
 return version.group(1),url.group(1)

def installed(target=TARGET):
 try:return json.loads((Path(target)/'manifest.json').read_text(encoding='utf8')).get('version')
 except (OSError,ValueError):return None

def unpack(data,version):
 """Validated {relative path: bytes} from the release ZIP (single expected top folder, no path tricks)."""
 top='VIDEO_IMAGE_STUDIO_ChatGPT_Extension_v'+version+'/';files={};total=0
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  for info in z.infolist():
   if info.is_dir():continue
   name=info.filename
   if not name.startswith(top):raise ValueError('ZIP có tệp ngoài thư mục Extension')
   rel=name[len(top):]
   if not rel or rel.startswith('/') or '\\' in rel or any(p in ('','.','..') for p in rel.split('/')) or not re.fullmatch(r'[A-Za-z0-9_./-]+',rel):raise ValueError('Tên tệp trong ZIP không hợp lệ: '+name)
   total+=info.file_size
   if len(files)>=MAX_FILES or total>MAX_TOTAL:raise ValueError('ZIP quá lớn')
   files[rel]=z.read(info)
 manifest=json.loads(files.get('manifest.json',b'{}'))
 if manifest.get('version')!=version or 'background' not in manifest:raise ValueError('manifest.json không khớp phiên bản')
 return files

def install(files,target=TARGET):
 """Write every file first and manifest.json last, so the extension only sees the new version once complete."""
 target=Path(target);target.mkdir(parents=True,exist_ok=True)
 old={str(p.relative_to(target)).replace('\\','/') for p in target.rglob('*') if p.is_file()}
 for rel,data in sorted(files.items(),key=lambda x:x[0]=='manifest.json'):
  path=target/rel;path.parent.mkdir(parents=True,exist_ok=True)
  fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.tmp-')
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 for rel in old-set(files):
  if not rel.startswith('.tmp-'):
   try:(target/rel).unlink()
   except OSError:pass

BRIDGE_NAME='VIDEO IMAGE STUDIO — ChatGPT Bridge'
def edge_install_folders(base=None):
 """Folders the Edge profiles actually load this extension from (people often load a downloaded copy).
 Only folders whose manifest is our bridge are returned, so nothing else is ever overwritten."""
 ud=Path(base or Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft'/'Edge'/'User Data');found=[]
 for prefs in list(ud.glob('*/Secure Preferences'))+list(ud.glob('*/Preferences')):
  try:settings=json.loads(prefs.read_text(encoding='utf8')).get('extensions',{}).get('settings',{})
  except (OSError,ValueError):continue
  for row in settings.values():
   path=Path(str((row or {}).get('path') or ''))
   if not path.is_absolute() or not (path/'manifest.json').is_file():continue
   try:name=json.loads((path/'manifest.json').read_text(encoding='utf8')).get('name')
   except (OSError,ValueError):continue
   if name==BRIDGE_NAME and path not in found:found.append(path)
 return found

class ExtensionUpdater:
 def __init__(self,target=TARGET,fetch=_get,extra=edge_install_folders):
  self.target=Path(target);self.fetch=fetch;self.extra=extra;self.lock=threading.Lock()
  self.state={'path':str(self.target),'installed':installed(self.target),'latest':None,'checked_at':None,'error':None,'updated_at':None}
 def snapshot(self):
  with self.lock:return dict(self.state,installed=installed(self.target))
 def check(self):
  try:
   version,name=latest(self.fetch)
   targets=[self.target]+[p for p in self.extra() if p!=self.target]
   stale=[t for t in targets if installed(t)!=version]
   if stale:
    files=unpack(self.fetch(RAW+'public/resources/'+name,MAX_ZIP),version)
    for t in stale:install(files,t)
    with self.lock:self.state['updated_at']=time.time()
   with self.lock:self.state['folders']=[str(t) for t in targets]
   with self.lock:self.state.update(latest=version,error=None,checked_at=time.time())
  except Exception as exc:
   with self.lock:self.state.update(error=str(exc)[:300],checked_at=time.time())
  return self.snapshot()
 def run(self,stop,interval=1800):
  self.check()
  while not stop.wait(interval):self.check()
