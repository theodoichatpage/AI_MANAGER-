"""Poll Studio's existing session read endpoint, without dispatching commands."""
import re, threading, time, hmac
from studio_reader import read_session
class StudioMonitor:
 def __init__(self,reader=read_session,clock=time.monotonic):
  self.reader=reader;self.clock=clock;self.last_presence=None;self.chat_ready=None;self.tabs={};self.closed_tabs={};self.closed_tabs={};self.lock=threading.Lock();self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation=0
 def configure(self,code):
  code=str(code).strip()
  if not re.fullmatch(r'[A-Za-z0-9-]{16,64}',code): raise ValueError('Mã kết nối không hợp lệ')
  with self.lock: self.code=code;self.status='connecting';self.data=None;self.error='';self.generation+=1;self.last_presence=None;self.chat_ready=None;self.tabs={};self.closed_tabs={}
 def disconnect(self):
  with self.lock: self.code='';self.status='unconfigured';self.data=None;self.error='';self.generation+=1;self.last_presence=None;self.chat_ready=None;self.tabs={};self.closed_tabs={}
 def presence(self,code,chat_ready,tab_id='legacy'):
  if not isinstance(tab_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',tab_id):return False
  with self.lock:
   if not self.code or not hmac.compare_digest(self.code,str(code)):return False
   stamp=self.clock();self.closed_tabs={k:v for k,v in self.closed_tabs.items() if stamp-v<300}
   if tab_id in self.closed_tabs:return False
   self.tabs[tab_id]=(stamp,bool(chat_ready));self.last_presence=stamp;return True
 def close_tab(self,code,tab_id):
  if not isinstance(tab_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',tab_id):return False
  with self.lock:
   if not self.code or not hmac.compare_digest(self.code,str(code)):return False
   self.tabs.pop(tab_id,None);self.closed_tabs[tab_id]=self.clock();return True
 def snapshot(self):
  with self.lock:
   active=[x for x in self.tabs.values() if self.clock()-x[0]<90]
   tab='connected' if active else ('lost' if self.last_presence is not None else 'unknown')
   latest=max(active,key=lambda x:x[0]) if active else None
   chat=('connected' if latest[1] else 'disconnected') if latest else 'unknown'
   return {'configured':bool(self.code),'status':self.status,'data':self.data,'error':self.error,'tab_status':tab,'chat_status':chat,'last_signal_age':round(max(0,self.clock()-self.last_presence)) if self.last_presence is not None else None}
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
