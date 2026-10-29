import json,tempfile,unittest
from pathlib import Path
from automation_agent import edge_profiles as ep

class EdgeProfilesTests(unittest.TestCase):
 def test_only_existing_profiles_and_safe_metadata(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'Profile 1').mkdir();(root/'Profile 1'/'Preferences').write_text('{}')
   (root/'Local State').write_text(json.dumps({'profile':{'info_cache':{'Profile 1':{'name':'My account','user_name':'safe@example.com','token':'SECRET'},'Profile 2':{'name':'Missing'},'../bad':{'name':'Bad'}}}}))
   self.assertEqual(ep.list_profiles(root),[{'directory':'Profile 1','name':'My account'}])
 def test_unregistered_existing_default_is_visible(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'Default').mkdir();(root/'Default'/'Preferences').write_text('{}')
   self.assertEqual(ep.list_profiles(root)[0]['directory'],'Default')
 def test_missing_or_traversal_profile_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   for p in ['../Default','Profile 999','', '--guest']:
    with self.assertRaises(ValueError):ep.require_profile(p,Path(d))
 def test_version_path_must_equal_not_prefix(self):
  self.assertTrue(ep.matches_profile_path(['C:\\Users\\PC\\Edge\\Profile 1'], 'C:\\Users\\PC\\Edge\\Profile 1'))
  self.assertFalse(ep.matches_profile_path(['C:\\Users\\PC\\Edge\\Profile 10'], 'C:\\Users\\PC\\Edge\\Profile 1'))

class EdgeWorkflowTests(unittest.TestCase):
 def test_profile_is_in_every_action(self):
  from automation_agent.workflows import workflow
  actions=workflow('edge_workflow','edge','https://chatgpt.com',123,'Profile 2')
  self.assertEqual(actions[-1]['action'],'SCREENSHOT')
  self.assertTrue(all(a['target_app']=='edge' and a['browser_profile']=='Profile 2' and a['hwnd']==123 for a in actions))
 def test_checkpoint_retains_profile_and_stopped_state(self):
  from automation_agent.task_store import TaskStore
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'agent.db';store=TaskStore(path)
   tid=store.submit([{'action':'WAIT'}],context={'target_app':'edge','browser_profile':'Profile 2'})
   store.stop_all();store.close();store=TaskStore(path)
   self.assertEqual(store.get(tid)['status'],'stopped');self.assertEqual(store.get(tid)['context']['browser_profile'],'Profile 2');store.close()
 def test_project_profile_survives_restart(self):
  from queue_manager import QueueManager
  with tempfile.TemporaryDirectory() as d:
   q=QueueManager(d);q.add({'id':'a','name':'A','folder':d});q.stop_all();q.set_browser('a','edge','Profile 2','Account');q.close()
   q=QueueManager(d);self.assertEqual(q.get('a')['browser_profile'],'Profile 2');self.assertEqual(q.get('a')['status'],'stopped');q.close()
 def test_mismatched_profile_is_blocked_before_window_action(self):
  from automation_agent.action_worker import dispatch
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(RuntimeError,'không khớp'):
    dispatch({'action':'HOTKEY','target_app':'edge','browser_profile':'Profile 1','keys':'ENTER'},{'target_app':'edge','browser_profile':'Profile 2','hwnd':123},d,{})
 def test_unverified_profile_is_blocked(self):
  from unittest.mock import patch
  from automation_agent import edge_controller as ec
  with patch.object(ec,'require_profile'),patch.object(ec,'bindings',return_value={}),patch.dict('sys.modules',{'win32gui':__import__('types').SimpleNamespace(GetProp=lambda *a:0)}):
   with self.assertRaisesRegex(RuntimeError,'Chưa xác minh'):ec.verify_binding({'browser_profile':'Profile 1','hwnd':1})
 def test_open_reuses_verified_window_without_launch(self):
  from unittest.mock import patch
  from automation_agent import edge_controller as ec
  w={'hwnd':42,'pid':7,'process_started':1,'browser_profile':'Profile 2','browser_profile_name':'Name'}
  with patch.object(ec.wm,'require_windows'),patch.object(ec,'require_profile',return_value={'name':'Name'}),patch.object(ec,'verified_windows',return_value=[w]),patch.object(ec.subprocess,'Popen') as launch:
   r=ec.EdgeController.open('Profile 2');self.assertTrue(r['already_running']);self.assertEqual(r['context']['hwnd'],42);launch.assert_not_called()
 def test_reused_handle_without_nonce_is_rejected(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  from automation_agent import edge_controller as ec
  t={'hwnd':1,'pid':2,'process_started':3,'browser_profile':'Default','window_nonce':123}
  with patch.object(ec,'require_profile'),patch.object(ec,'bindings',return_value={'1':t}),patch.dict('sys.modules',{'win32gui':SimpleNamespace(GetProp=lambda *a:0)}):
   with self.assertRaisesRegex(RuntimeError,'Chưa xác minh'):ec.verify_binding(t)

class EdgeToolbarProofTests(unittest.TestCase):
 def test_unique_exact_toolbar_profile_name(self):
  from automation_agent.edge_controller import toolbar_profile_matches
  rows=[{'directory':'Default','name':'Profile 1'},{'directory':'Profile 2','name':'Work'}]
  self.assertTrue(toolbar_profile_matches(['Profile 1'],'Default',rows))
  self.assertFalse(toolbar_profile_matches(['Profile 10'],'Default',rows))
 def test_duplicate_names_never_prove_identity(self):
  from automation_agent.edge_controller import toolbar_profile_matches
  rows=[{'directory':'Default','name':'Work'},{'directory':'Profile 2','name':'Work'}]
  self.assertFalse(toolbar_profile_matches(['Work'],'Default',rows))

class EdgeWindowScanTests(unittest.TestCase):
 def test_one_inaccessible_window_does_not_block_other_window(self):
  from unittest.mock import patch
  from automation_agent import edge_controller as ec
  with patch.object(ec,'prove_window',side_effect=[RuntimeError('UIA unavailable'),True]):
   self.assertEqual(ec.matching_windows([{'hwnd':1},{'hwnd':2}],'Default'),[{'hwnd':2}])

class EdgeDiagnosticTests(unittest.TestCase):
 def test_diagnostic_reports_failure_without_exporting_page_content(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  from automation_agent import edge_controller as ec
  class FakeWindow:
   def descendants(self,**kw):return []
  desktop=SimpleNamespace(window=lambda **kw:FakeWindow())
  with patch.dict('sys.modules',{'pywinauto':SimpleNamespace(Desktop=lambda **kw:desktop)}),patch.object(ec,'native_profile_names',return_value=[]),patch.object(ec,'list_profiles',return_value=[{'directory':'Default','name':'Name'}]):
   report=ec.inspect_window_profile({'hwnd':1,'pid':2},'Default')
   self.assertFalse(report['verified']);self.assertFalse(report['address_control_found']);self.assertEqual(report['edit_count'],0)
   self.assertNotIn('text',report);self.assertNotIn('url',report)
 def test_uia_exception_is_exposed_as_type_not_silently_discarded(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  from automation_agent import edge_controller as ec
  with patch.dict('sys.modules',{'pywinauto':SimpleNamespace(Desktop=lambda **kw:(_ for _ in ()).throw(RuntimeError('PRIVATE CONTENT')))}):
   report=ec.inspect_window_profile({'hwnd':1,'pid':2},'Default')
   self.assertEqual(report['inspection_error'],'RuntimeError');self.assertNotIn('PRIVATE CONTENT',json.dumps(report))
