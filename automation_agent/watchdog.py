"""Windows Job Object: close handle => kill agent/action descendants."""
import sys, uuid
class ChildJob:
 def __init__(self):
  self.job=None
  if sys.platform=='win32':
   import win32job
   self.job=win32job.CreateJobObject(None,'AI_MANAGER_'+uuid.uuid4().hex);info=win32job.QueryInformationJobObject(self.job,win32job.JobObjectExtendedLimitInformation)
   info['BasicLimitInformation']['LimitFlags']|=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | win32job.JOB_OBJECT_LIMIT_BREAKAWAY_OK
   win32job.SetInformationJobObject(self.job,win32job.JobObjectExtendedLimitInformation,info)
 def add(self,pid):
  if self.job:
   import win32api,win32con,win32job
   p=win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS,False,pid)
   try:win32job.AssignProcessToJobObject(self.job,p)
   finally:p.Close()
 def close(self):
  if self.job:self.job.Close();self.job=None
