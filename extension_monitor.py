"""Read-only, session-scoped extension heartbeat status."""
import threading
import time

class ExtensionMonitor:
 def __init__(self):
  self.lock=threading.Lock(); self.data=None
 def receive(self,expected,data,now=None,expected_job=None):
  if not expected or data.get('pairCode')!=expected:return False
  job=data.get('activeJobId')
  if job is not None and (not isinstance(job,str) or len(job)>150):return False
  if job and expected_job and job!=expected_job:return False
  now=time.time() if now is None else now
  with self.lock:
   self.data={'pairCode':expected,'received':now,'identityVersion':data.get('identityVersion'),
    'activeJobId':job or None,'chatTabId':data.get('chatTabId') if isinstance(data.get('chatTabId'),int) else None,
    'conversationUrl':data.get('conversationUrl') if isinstance(data.get('conversationUrl'),str) and data.get('conversationUrl','').startswith('https://chatgpt.com/c/') else None,
    'lastHeartbeatAt':data.get('lastHeartbeatAt') if isinstance(data.get('lastHeartbeatAt'),(int,float)) else None,
    'version':data.get('version') if isinstance(data.get('version'),str) else None}
  return True
 def snapshot(self,expected,now=None):
  now=time.time() if now is None else now
  with self.lock: d=dict(self.data) if self.data and self.data['pairCode']==expected and expected else None
  if not d:return {'status':'extension_lost','activeJobId':None,'chatTabId':None,'heartbeatAge':None}
  age=max(0,now-d['received']); stamp=d['lastHeartbeatAt']
  heartbeat_age=max(0,now-stamp/1000) if stamp is not None and stamp/1000<=now+10 else None
  if age>90:status='extension_lost'
  elif d['identityVersion']!=1:status='legacy'
  elif heartbeat_age is None or heartbeat_age>45:status='heartbeat_stopped'
  else:status='responding'
  d.pop('pairCode');d.pop('received');d['status']=status;d['heartbeatAge']=heartbeat_age
  return d
