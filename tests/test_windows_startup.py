import sys,types,unittest
from unittest.mock import patch
class WindowsJobStartupTests(unittest.TestCase):
 def test_job_name_is_a_unique_string_not_none(self):
  from automation_agent.watchdog import ChildJob
  names=[]
  class Handle:
   def Close(self):pass
  def create(attrs,name):
   if not isinstance(name,str):raise TypeError('None is not a valid string in this context')
   names.append(name);return Handle()
  fake=types.SimpleNamespace(CreateJobObject=create,QueryInformationJobObject=lambda *a:{'BasicLimitInformation':{'LimitFlags':0}},SetInformationJobObject=lambda *a:None,JobObjectExtendedLimitInformation=9,JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE=0x2000,JOB_OBJECT_LIMIT_BREAKAWAY_OK=0x800)
  with patch.dict(sys.modules,{'win32job':fake}),patch('automation_agent.watchdog.sys.platform','win32'):
   a=ChildJob();b=ChildJob();a.close();b.close()
  self.assertEqual(len(names),2);self.assertTrue(all(names));self.assertNotEqual(names[0],names[1])
