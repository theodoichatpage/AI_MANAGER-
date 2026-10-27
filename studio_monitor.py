"""Poll Studio's existing session read endpoint, without dispatching commands."""
import re, threading
from studio_reader import read_session
class StudioMonitor:
 def __init__(self,reader=read_session):
  self.reader=reader;self.lock=threading.Lock();self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation=0
 def configure(self,code):
  code=str(code).strip()
  if not re.fullmatch(r'[A-Za-z0-9-]{16,64}',code): raise ValueError('Mã kết nối không hợp lệ')
  with self.lock: self.code=code;self.status='connecting';self.data=None;self.error='';self.generation+=1
 def disconnect(self):
  with self.lock: self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation+=1
 def snapshot(self):
  with self.lock: return {'configured':bool(self.code),'status':self.status,'data':self.data,'error':self.error}
 def poll(self):
  with self.lock: code=self.code; generation=self.generation
  if not code:return
  try: data=self.reader(code);err=''
  except Exception: data=None;err='Không đọc được phiên Studio. Kiểm tra mạng và mã kết nối.'
  with self.lock:
   if generation!=self.generation:return
   if err: self.status='lost' if self.data else 'error';self.error=err
   else:self.status='connected';self.data=data;self.error=''
 def run(self,stop,interval=5):
  while not stop.wait(interval):self.poll()
