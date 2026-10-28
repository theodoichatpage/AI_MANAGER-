import tempfile,os,unittest
from unittest.mock import patch
from types import SimpleNamespace
from automation_agent import edge_controller as ec

class BindingRegressionTests(unittest.TestCase):
 def test_open_does_not_need_or_call_window_property_api(self):
  w={'hwnd':42,'pid':7,'process_started':1,'title':'Edge','process':'msedge.exe'}
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'AI_MANAGER_AGENT_HOME':d}),patch.object(ec.wm,'require_windows'),patch.object(ec,'require_profile',return_value={'name':'Profile 1'}),patch.object(ec,'verified_windows',return_value=[]),patch.object(ec.wm,'windows',return_value=[w]),patch.object(ec,'native_matching_windows',return_value=([w],[{'hwnd':42,'verified':True}])),patch.dict('sys.modules',{'win32gui':SimpleNamespace()}):
   result=ec.EdgeController.open('Default')
   self.assertTrue(result['profile_verified']);self.assertEqual(result['context']['hwnd'],42)
 def test_same_pid_reused_hwnd_with_different_profile_is_blocked(self):
  from automation_agent.edge_bindings import make_record
  from automation_agent import edge_native
  w={'hwnd':42,'pid':7,'process_started':1};record=make_record(w,'Default','Name')
  with patch.object(ec,'require_profile'),patch.object(ec,'bindings',return_value={'42':record}),patch.object(ec.wm,'windows',return_value=[w]),patch.object(edge_native,'window_profile_report',return_value={'verified':False}):
   with self.assertRaisesRegex(RuntimeError,'đã chặn'):ec.verify_binding(record)
 def test_live_profile_proof_allows_matching_binding_without_properties(self):
  from automation_agent.edge_bindings import make_record
  from automation_agent import edge_native
  w={'hwnd':42,'pid':7,'process_started':1};record=make_record(w,'Default','Name')
  with patch.object(ec,'require_profile'),patch.object(ec,'bindings',return_value={'42':record}),patch.object(ec.wm,'windows',return_value=[w]),patch.object(edge_native,'window_profile_report',return_value={'verified':True}),patch.dict('sys.modules',{'win32gui':SimpleNamespace()}):
   ec.verify_binding(record)
 def test_different_pid_is_blocked(self):
  from automation_agent.edge_bindings import make_record,validate_live
  record=make_record({'hwnd':42,'pid':7,'process_started':1},'Default','Name')
  with self.assertRaisesRegex(RuntimeError,'đã thay đổi'):validate_live(record,{'hwnd':42,'pid':8,'process_started':2},{'verified':True})
