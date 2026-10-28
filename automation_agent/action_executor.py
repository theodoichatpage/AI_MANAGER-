import json, subprocess, sys, threading, time
from pathlib import Path

class ActionExecutor:
 def __init__(self,home,settings=None):self.home=Path(home);self.settings=settings or {};self.lock=threading.RLock();self.process=None
 def cancel(self):
  with self.lock:
   p=self.process
   if p and p.poll() is None:
    p.terminate()
    try:p.wait(timeout=2)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=2)
  if sys.platform=='win32':
   # A killed mouse/keyboard action must not leave a modifier or button held.
   import ctypes
   u=ctypes.windll.user32
   for key in (0x10,0x11,0x12,0x5B,0x5C):u.keybd_event(key,0,2,0)
   u.mouse_event(0x0004|0x0010|0x0040,0,0,0,0)
 def run(self,tid,action,context,cancel,retry=0):
  started=time.time();name=action['action'];result={};error=None;error_code=None;status='failed';success=False
  with self.lock:
   if cancel.is_set():return self._result(tid,name,False,'stopped',{},'Đã dừng',started,retry)
   flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0
   self.process=subprocess.Popen([sys.executable,'-m','automation_agent.action_worker'],cwd=str(Path(__file__).resolve().parent.parent),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=flags)
   p=self.process
  try:
   out,err=p.communicate(json.dumps({'action':action,'context':context,'home':str(self.home),'settings':self.settings}),timeout=float(action.get('timeout',30)))
   if cancel.is_set():status='stopped';error='Đã dừng'
   elif p.returncode!=0:raise RuntimeError('Action worker thoát bất thường: '+err[-500:])
   else:
    data=json.loads(out);success=bool(data.get('success'));result=data.get('result') or {};error=data.get('error');error_code=data.get('error_code');status='completed' if success else 'failed'
  except subprocess.TimeoutExpired:
   self.cancel()
   try:p.communicate(timeout=2)
   except subprocess.TimeoutExpired:
    if p.stdout:p.stdout.close()
    if p.stderr:p.stderr.close()
   status='timeout';error='Action quá thời gian; worker đã bị dừng'
  except Exception as e:error=str(e)
  finally:
   with self.lock:
    if self.process is p:self.process=None
  if cancel.is_set():success=False;status='stopped';error='Đã dừng'
  return dict(self._result(tid,name,success,status,result,error,started,retry),error_code=error_code)
 def _result(self,tid,name,success,status,result,error,started,retry):
  ended=time.time();return {'task_id':tid,'action':name,'success':success,'status':status,'result':result,'error':error,'started_at':started,'finished_at':ended,'duration':ended-started,'retry_count':retry}
