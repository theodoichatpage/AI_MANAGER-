"""Observes heartbeats in dry-run only. It never returns browser commands."""
import json, threading, time
from recovery_policy import RecoveryPolicy

class RecoveryMonitor:
 def __init__(self,root,soft=300,hard=600):
  self.root=root;self.policy=RecoveryPolicy(soft,hard,max_attempts=3);self.lock=threading.Lock();self.last=None;self.decision='idle'
 def receive(self,expected,data,now=None,studio=None):
  if not expected or data.get('pairCode')!=expected:return False
  fp=data.get('fp') if isinstance(data.get('fp'),dict) else None
  job=data.get('activeJobId') if isinstance(data.get('activeJobId'),str) else None
  if job and len(job)>100:return False
  if fp is not None and (not isinstance(fp.get('msgCount',0),int) or not isinstance(fp.get('lastLen',0),int)):return False
  timestamp=time.time() if now is None else now
  studio=studio or {}
  fingerprint=(fp.get('generating'),fp.get('msgCount'),fp.get('lastLen'),studio.get('completed_parts'),studio.get('analyzed_scenes')) if fp else None
  blocked=next((k for k in ('captcha','rateLimit','login') if fp and fp.get(k) is True),None)
  if fp and job and fp.get('jobId')!=job:blocked=blocked or 'job_mismatch'
  with self.lock:
   decision=self.policy.observe(job,fingerprint,timestamp,blocked=blocked,heartbeat=bool(data.get('tabAlive')) and fp is not None)
   self.last=timestamp;self.decision=decision
   self.root.mkdir(parents=True,exist_ok=True)
   with (self.root/'recovery.log').open('a',encoding='utf-8') as f:f.write(json.dumps({'at':timestamp,'decision':decision,'reason':blocked,'mode':'dry-run'},ensure_ascii=False)+'\n')
  return []
 def snapshot(self,now=None):
  with self.lock:
   timestamp=time.time() if now is None else now
   lines=[]
   try:
    with (self.root/'recovery.log').open(encoding='utf-8') as f:
     from collections import deque
     lines=[json.loads(line) for line in deque(f,maxlen=20)]
   except (OSError,ValueError):pass
   return {'mode':'dry-run','lastHeartbeat':self.last,'responding':self.last is not None and 0<=timestamp-self.last<=90,'decision':self.decision,'logs':lines}
