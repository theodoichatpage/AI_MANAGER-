"""Poll Studio's existing session endpoint and recover automatically from slow/lost reads."""
import re, threading, time
from studio_reader import read_session

class StudioMonitor:
 def __init__(self,reader=read_session,max_recovery=3,recovery_delay=2):
  self.reader=reader;self.lock=threading.Lock();self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation=0
  self.max_recovery=max(1,int(max_recovery));self.recovery_delay=max(0,float(recovery_delay));self.failure_count=0;self.refresh_count=0;self.last_ok=None;self.recovering=False
 def configure(self,code):
  code=str(code).strip()
  if not re.fullmatch(r'[A-Za-z0-9-]{16,64}',code): raise ValueError('Mã kết nối không hợp lệ')
  with self.lock:
   self.code=code;self.status='connecting';self.data=None;self.error='';self.failure_count=0;self.refresh_count=0;self.last_ok=None;self.recovering=False;self.generation+=1
 def disconnect(self):
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
