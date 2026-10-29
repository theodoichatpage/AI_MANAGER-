import unittest
from automation_agent.edge_native import profile_from_properties

ROOT=r'C:\Users\PC\AppData\Local\Microsoft\Edge\User Data'
class NativeProfileTests(unittest.TestCase):
 def test_exact_icon_parent(self):
  self.assertTrue(profile_from_properties({'icon':ROOT+r'\Profile 1\Edge Profile.ico,0'},[],[],ROOT,'Profile 1'))
  self.assertFalse(profile_from_properties({'icon':ROOT+r'\Profile 10\Edge Profile.ico,0'},[],[],ROOT,'Profile 1'))
 def test_explicit_per_window_command(self):
  self.assertTrue(profile_from_properties({},['msedge.exe','--profile-directory=Profile 2'],['msedge.exe'],ROOT,'Profile 2'))
 def test_no_implicit_default_guess(self):
  self.assertFalse(profile_from_properties({},['msedge.exe'],['msedge.exe'],ROOT,'Default'))
 def test_custom_root_and_private_rejected(self):
  for flags in [['--user-data-dir=D:\\Other'],['--inprivate'],['--guest']]:
   self.assertFalse(profile_from_properties({},['msedge.exe','--profile-directory=Default']+flags,['msedge.exe'],ROOT,'Default'))
 def test_browser_process_root_must_match(self):
  self.assertFalse(profile_from_properties({},['msedge.exe','--profile-directory=Default'],['msedge.exe','--user-data-dir=D:\\Other'],ROOT,'Default'))
 def test_duplicate_flags_rejected(self):
  self.assertFalse(profile_from_properties({},['msedge.exe','--profile-directory=Default','--profile-directory=Profile 1'],[],ROOT,'Default'))
 def test_user_data_icon_does_not_match_other_root(self):
  self.assertFalse(profile_from_properties({'icon':r'D:\Other\Default\Edge Profile.ico,0'},[],[],ROOT,'Default'))

class NativeOpenTests(unittest.TestCase):
 def test_existing_native_proof_binds_without_launch_or_uia(self):
  import tempfile,os
  from unittest.mock import patch
  from types import SimpleNamespace
  from automation_agent import edge_controller as ec
  w={'hwnd':42,'pid':7,'process_started':1,'title':'Edge','process':'msedge.exe'}
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'AI_MANAGER_AGENT_HOME':d}),patch.object(ec.wm,'require_windows'),patch.object(ec,'require_profile',return_value={'name':'Profile 1'}),patch.object(ec,'verified_windows',return_value=[]),patch.object(ec.wm,'windows',return_value=[w]),patch.object(ec,'native_matching_windows',return_value=([w],[{'hwnd':42,'verified':True}])),patch.object(ec,'prove_window',side_effect=AssertionError('UIA must not run')),patch.object(ec.subprocess,'Popen') as launch,patch.dict('sys.modules',{'win32gui':SimpleNamespace()}):
   result=ec.EdgeController.open('Default')
   self.assertTrue(result['profile_verified']);self.assertEqual(result['context']['hwnd'],42);launch.assert_not_called()
 def test_failure_has_limit_and_does_not_use_uia(self):
  import tempfile,os,time,json
  from pathlib import Path
  from unittest.mock import patch
  from automation_agent import edge_controller as ec
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'AI_MANAGER_AGENT_HOME':d}):
   Path(d,'edge_launches.json').write_text(json.dumps({'Default':time.time()}))
   with patch.object(ec.wm,'require_windows'),patch.object(ec,'require_profile',return_value={'name':'Profile 1'}),patch.object(ec,'verified_windows',return_value=[]),patch.object(ec.wm,'windows',return_value=[]),patch.object(ec,'native_matching_windows',return_value=([],[])),patch.object(ec.time,'monotonic',side_effect=[0,13]),patch.object(ec.subprocess,'Popen') as launch,patch.object(ec,'prove_window',side_effect=AssertionError('UIA must not run')):
    with self.assertRaisesRegex(RuntimeError,'Đã dừng xác minh'):ec.EdgeController.open('Default')
    launch.assert_not_called()
