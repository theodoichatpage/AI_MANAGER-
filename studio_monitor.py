"""Poll Studio's existing session endpoint and recover automatically from slow/lost reads."""
import re, sys, threading, time
from pathlib import Path
from studio_reader import read_session

CODE=re.compile(r'[A-Za-z0-9-]{16,64}')

def _protect(raw):
 """Windows DPAPI: only this Windows user can read the saved pairing code. No other platform stores it."""
 if sys.platform!='win32':return None
 import win32crypt
 return win32crypt.CryptProtectData(raw,'AI MANAGER Studio pairing',None,None,None,0)

def _unprotect(blob):
 if sys.platform!='win32':return None
 import win32crypt
 return win32crypt.CryptUnprotectData(blob,None,None,None,0)[1]

class StudioMonitor:
 def __init__(self,reader=read_session,max_recovery=3,recovery_delay=2,store=None):
  self.store=Path(store) if store else None;self.reader=reader;self.lock=threading.Lock();self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation=0
  self.max_recovery=max(1,int(max_recovery));self.recovery_delay=max(0,float(recovery_delay));self.failure_count=0;self.refresh_count=0;self.last_ok=None;self.recovering=False
  self._restore()
 def _restore(self):
  """A Manager restart keeps the Studio pairing: the code saved (encrypted) by configure() is read back."""
  if not self.store or not self.store.is_file():return
  try:code=_unprotect(self.store.read_bytes()).decode('ascii')
  except Exception:return
  if code and CODE.fullmatch(code):
   with self.lock:self.code=code;self.status='connecting';self.generation+=1
 def _save(self,code):
  if not self.store:return
  try:
   blob=_protect(code.encode('ascii')) if code else None
   if blob is None:
    if self.store.exists():self.store.unlink()
    return
   self.store.parent.mkdir(parents=True,exist_ok=True);tmp=self.store.with_suffix('.tmp');tmp.write_bytes(blob);tmp.replace(self.store)
  except Exception:pass
 def configure(self,code):
  code=str(code).strip()
  if not CODE.fullmatch(code): raise ValueError('Mã kết nối không hợp lệ')
  self._save(code)
  with self.lock:
   self.code=code;self.status='connecting';self.data=None;self.error='';self.failure_count=0;self.refresh_count=0;self.last_ok=None;self.recovering=False;self.generation+=1
 def disconnect(self):
  self._save('')
  with self.lock:
   self.code='';self.status='unconfigured';self.data=None;self.error='';self.failure_count=0;self.recovering=False;self.generation+=1
 def snapshot(self):
  with self.lock:
   return {'configured':bool(self.code),'status':self.status,'data':self.data,'error':self.error,
    'failure_count':self.failure_count,'refresh_count':self.refresh_count,'last_ok':self.last_ok,'recovering':self.recovering}
 def _read(self,code):
  return self.reader(code)
 def poll(self):
  with self.lock: code=self.code; generation=self.generation
  if not code:return
  data=None;err=''
  for attempt in range(self.max_recovery+1):
   try:
    data=self._read(code);err='';break
   except Exception:
    err='Studio phản hồi quá lâu hoặc mất kết nối.'
    if attempt<self.max_recovery:
     with self.lock:
      if generation!=self.generation:return
      self.status='recovering';self.recovering=True;self.refresh_count+=1;self.error=f'{err} Đang tự làm mới và phục hồi ({attempt+1}/{self.max_recovery})...'
     if self.recovery_delay: time.sleep(self.recovery_delay)
  with self.lock:
   if generation!=self.generation:return
   self.recovering=False
   if err:
    self.failure_count+=1;self.status='lost' if self.data else 'error';self.error=f'{err} Đã thử phục hồi {self.max_recovery} lần; sẽ tiếp tục kiểm tra tự động.'
   else:
    self.status='connected';self.data=data;self.error='';self.failure_count=0;self.last_ok=time.time()
 def run(self,stop,interval=5,idle=60,busy=None):
  """Read every `interval` s while a project runs; when nothing runs, only every `idle` s (Studio's database
  is shared and has a usage quota)."""
  last=0.0
  while not stop.wait(interval):
   try:active=busy() if busy else True
   except Exception:active=True
   if active or time.time()-last>=idle:last=time.time();self.poll()
