import ast
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from automation_agent import chatgpt_mcp as m

URL='https://chatgpt.com/c/dedicated-test'
SNAP='''uid=1_0 RootWebArea "ChatGPT" url="https://chatgpt.com/c/dedicated-test"
  uid=1_1 heading "You said:" level="5"
  uid=1_2 StaticText "seed"
  uid=1_3 heading "ChatGPT said:" level="6"
  uid=1_4 StaticText "ACK ROUND 1"
  uid=1_5 button "Copy"
  uid=1_6 textbox "Ask anything" multiline
'''

class MCPRegression(unittest.TestCase):
 def test_live_actions_use_exact_requested_prompts(self):
  from tests import wincontrol_chatgpt_acceptance as live
  build=getattr(live,'acceptance_actions',None)
  self.assertTrue(callable(build),'live runner must expose its actual action sequence')
  actions=build(URL)
  self.assertEqual([a['action'] for a in actions],['OBSERVE_CHATGPT','SEND_CHATGPT','OBSERVE_CHATGPT','SEND_CHATGPT','OBSERVE_CHATGPT'])
  self.assertEqual([a['text'] for a in actions if a['action']=='SEND_CHATGPT'],['WINCONTROL TEST ROUND 1','WINCONTROL TEST ROUND 2'])
  self.assertEqual(len({a['exchange_id'] for a in actions if a['action']=='SEND_CHATGPT'}),2)

 def test_snapshot_must_prove_exact_url(self):
  for snap in (SNAP.replace(URL,'https://chatgpt.com/c/other'),'\n'.join(SNAP.splitlines()[1:])):
   with self.assertRaises(RuntimeError):m.parse_snapshot(snap,URL)

 def test_extract_exact_assistant_not_controls(self):
  state=m.parse_snapshot(SNAP,URL)
  self.assertEqual(state['lastAssistant'],'ACK ROUND 1')
  self.assertEqual(state['turnCount'],2)
  self.assertEqual(state['lastRole'],'assistant')

 def test_idle_composer_does_not_require_send_button(self):
  with patch.object(m,'_config',return_value={}),patch.object(m,'_call',return_value={'snapshot':SNAP}),patch.object(m.time,'sleep'):
   self.assertTrue(m.observe({}, {},URL)['completion_verified'])

 def test_user_tail_does_not_authorize_send(self):
  snap=SNAP.replace('  uid=1_6 textbox', '  uid=1_7 heading "You said:" level="5"\n  uid=1_8 StaticText "pending"\n  uid=1_6 textbox')
  with patch.object(m,'_config',return_value={}),patch.object(m,'_call',return_value={'snapshot':snap}),patch.object(m.time,'sleep'):
   self.assertFalse(m.observe({}, {},URL)['completion_verified'])

 def test_send_rejects_changed_turn_count_before_input(self):
  state=dict(completion_verified=True,url=URL,fingerprint='a'*64,turnCount=4)
  verified=dict(completed=True,url=URL,fingerprint='a'*64,turn_count=2)
  with patch.object(m,'observe',return_value=state),patch.object(m,'_config',return_value={}),patch.object(m,'_call') as call:
   with self.assertRaises(RuntimeError):m.send({}, {},URL,'hello','exchange-0001',verified)
   call.assert_not_called()

 def test_runner_has_no_removed_cdp_parameter(self):
  tree=ast.parse((Path(__file__).parent/'wincontrol_chatgpt_acceptance.py').read_text(encoding='utf-8'))
  self.assertFalse(any(isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='args' and n.attr=='cdp_port' for n in ast.walk(tree)))

 def test_uses_existing_bridge(self):
  self.assertIn('chrome_mcp_bridge.mjs',Path(m.__file__).read_text(encoding='utf-8'))
  self.assertNotIn('chatgpt_mcp_bridge.mjs',Path(m.__file__).read_text(encoding='utf-8'))

 def test_send_receipt_is_new_exact_user_turn(self):
  prompt='round two'
  received=SNAP.replace('  uid=1_6 textbox','  uid=1_7 heading "You said:" level="5"\n  uid=1_8 StaticText "round two"\n  uid=1_6 textbox')
  state=dict(completion_verified=True,url=URL,fingerprint='a'*64,turnCount=2)
  verified=dict(completed=True,url=URL,fingerprint='a'*64,turn_count=2)
  with patch.object(m,'observe',return_value=state),patch.object(m,'_config',return_value={}),patch.object(m,'_call',side_effect=[{'clicked':True},{'snapshot':received}]) as call:
   result=m.send({}, {},URL,prompt,'exchange-0002',verified)
   self.assertEqual(call.call_count,2)
   self.assertEqual(result['submission'],'received')
   self.assertEqual(result['prompt_sha256'],hashlib.sha256(prompt.encode()).hexdigest())

 def test_lost_receipt_never_resends(self):
  state=dict(completion_verified=True,url=URL,fingerprint='a'*64,turnCount=2)
  verified=dict(completed=True,url=URL,fingerprint='a'*64,turn_count=2)
  with patch.object(m,'observe',return_value=state),patch.object(m,'_config',return_value={}),patch.object(m,'_call',side_effect=[{'clicked':True},RuntimeError('disconnected')]) as call:
   with self.assertRaises(RuntimeError):m.send({}, {},URL,'hello','exchange-0003',verified)
   self.assertEqual([c.args[1] for c in call.call_args_list],['fill_click','snapshot'])

 def test_restart_preserves_uncertain_send_and_rejects_duplicate(self):
  import tempfile
  from automation_agent.task_store import TaskStore
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'agent.sqlite3';store=TaskStore(db)
   actions=[dict(action='SEND_CHATGPT',exchange_id='exchange-restart',text='hello')]
   tid=store.submit(actions);store.claim(tid);store.mark_action(tid,0);store.close()
   restored=TaskStore(db)
   try:
    self.assertEqual(restored.get(tid)['status'],'needs_review')
    with self.assertRaises(ValueError):restored.submit(actions)
    with self.assertRaises(ValueError):restored.resume(tid)
   finally:restored.close()

if __name__=='__main__':unittest.main()
