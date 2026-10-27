"""Poll Studio's existing session read endpoint, without dispatching commands."""
import re, threading, time, hmac
from studio_reader import read_session
class StudioMonitor:
 def __init__(self,reader=read_session,clock=time.monotonic):
  self.reader=reader;self.clock=clock;self.last_presence=None;self.chat_ready=None;self.lock=threading.Lock();self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation=0
 def configure(self,code):
  code=str(code).strip()
  if not re.fullmatch(r'[A-Za-z0-9-]{16,64}',code): raise ValueError('Mã kết nối không hợp lệ')
  with self.lock: self.code=code;self.status='connecting';self.data=None;self.error='';self.generation+=1;self.last_presence=None;self.chat_ready=None
 def disconnect(self):
  with self.lock: self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation+=1;self.last_presence=None;self.chat_ready=None
 def presence(self,code,chat_ready):
  with self.lock:
   if not self.code or not hmac.compare_digest(self.code,str(code)):return False
   self.last_presence=self.clock();self.chat_ready=bool(chat_ready);return True
 def snapshot(self):
  with self.lock:
   fresh=self.last_presence is not None and self.clock()-self.last_presence < 90
   tab='connected' if fresh else ('lost' if self.last_presence is not None else 'unknown')
   chat=('connected' if self.chat_ready else 'disconnected') if fresh else 'unknown'
   return {'configured':bool(self.code),'status':self.status,'data':self.data,'error':self.error,'tab_status':tab,'chat_status':chat}
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
