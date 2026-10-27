"""Dry-run stall policy; caller supplies validated heartbeat and fingerprints."""
class RecoveryPolicy:
 def __init__(self,soft,hard,max_attempts=3):
  if not 0<soft<hard or max_attempts<1: raise ValueError('Ngưỡng không hợp lệ')
  self.soft=soft;self.hard=hard;self.max_attempts=max_attempts
  self.job=None;self.fingerprint=None;self.changed_at=None;self.attempts=0;self.suspended=False
 def observe(self,job,fingerprint,now,blocked=None,heartbeat=True):
  if not job:
   self.job=None;self.fingerprint=None;self.changed_at=None;self.attempts=0;self.suspended=False
   return 'idle'
  if job!=self.job or fingerprint!=self.fingerprint:
   self.job=job;self.fingerprint=fingerprint;self.changed_at=now;self.attempts=0;self.suspended=bool(blocked or not heartbeat)
   return 'blocked' if blocked else ('disconnected' if not heartbeat else 'observing')
  if blocked:self.suspended=True;return 'blocked'
  if not heartbeat:self.suspended=True;return 'disconnected'
  if self.suspended:self.suspended=False;self.changed_at=now;return 'observing'
  elapsed=now-self.changed_at
  if elapsed>=self.hard:
   if self.attempts>=self.max_attempts:return 'failed'
   self.attempts+=1;self.changed_at=now
   return 'would_reload'
  if elapsed>=self.soft:return 'warning'
  return 'observing'
