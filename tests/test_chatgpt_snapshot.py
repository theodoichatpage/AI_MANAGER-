import unittest
from unittest.mock import patch
from automation_agent.browser_controller import BrowserController


class FakeButton:
 def __init__(self, label):self.label=label
 def window_text(self):return self.label


class FakeDocument:
 def __init__(self,text,buttons):self.text=text;self.buttons=buttons
 def window_text(self):return self.text
 def descendants(self,control_type=None):return self.buttons if control_type=='Button' else []


class FakeRoot:
 def __init__(self,docs):self.docs=docs
 def descendants(self,control_type=None):return self.docs if control_type=='Document' else []


class ChatGPTSnapshotTests(unittest.TestCase):
 def snapshot(self,url,docs):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  with patch.object(browser,'read_url',return_value=url),patch('automation_agent.browser_controller.wm.validate_target'),patch('automation_agent.browser_controller.ui.root',return_value=FakeRoot(docs)):
   return browser.chatgpt_snapshot()

 def test_generating_is_never_complete(self):
  result=self.snapshot('https://chatgpt.com/c/test',[FakeDocument('answer in progress',[FakeButton('Stop generating')])])
  self.assertEqual(result['state'],'generating')
  self.assertFalse(result['completion_verified'])

 def test_stop_absent_does_not_imply_completion(self):
  result=self.snapshot('https://chatgpt.com/c/test',[FakeDocument('some answer',[FakeButton('Send prompt')])])
  self.assertEqual(result['state'],'unverified')
  self.assertFalse(result['completion_verified'])

 def test_reject_other_pages(self):
  with self.assertRaises(ValueError):self.snapshot('https://example.com/c/test',[])
  with self.assertRaises(ValueError):self.snapshot('https://chatgpt.com/',[])

 def test_reject_ambiguous_documents(self):
  with self.assertRaises(RuntimeError):self.snapshot('https://chatgpt.com/c/test',[FakeDocument('one',[]),FakeDocument('two',[])])


 def test_observe_stable_does_not_authorize_send(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  stable={'url':'https://chatgpt.com/c/test','text':'assistant text','fingerprint':'abc','generating':False}
  with patch.object(browser,'chatgpt_snapshot',side_effect=[stable,stable,stable]),patch('automation_agent.browser_controller.time.sleep',return_value=None):
   result=browser.chatgpt_observe(3,.2)
  self.assertTrue(result['stable'])
  self.assertFalse(result['completion_verified'])

 def test_observe_generating_blocks_completion(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  stable={'url':'https://chatgpt.com/c/test','text':'assistant text','fingerprint':'abc','generating':False}
  busy=dict(stable,generating=True)
  with patch.object(browser,'chatgpt_snapshot',side_effect=[stable,busy,stable]),patch('automation_agent.browser_controller.time.sleep',return_value=None):
   result=browser.chatgpt_observe(3,.2)
  self.assertFalse(result['stable'])
  self.assertEqual(result['state'],'generating')

 def test_observe_requires_multiple_samples(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  with self.assertRaises(ValueError):browser.chatgpt_observe(1)


 def test_dom_observe_verified_assistant(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  state={'url':'https://chatgpt.com/c/test','assistantCount':2,'turnCount':4,'lastRole':'assistant','lastAssistant':'answer','generating':False,'composerReady':True,'sendControlPresent':True}
  with patch.object(browser,'chatgpt_dom',side_effect=[state,state,state]),patch('automation_agent.browser_controller.time.sleep',return_value=None):
   result=browser.chatgpt_dom_observe()
  self.assertTrue(result['completion_verified'])
  self.assertEqual(result['lastAssistant'],'answer')

 def test_dom_observe_rejects_busy_or_switched_conversation(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  state={'url':'https://chatgpt.com/c/test','assistantCount':2,'turnCount':4,'lastAssistant':'answer','generating':False,'composerReady':True,'sendControlPresent':True}
  busy=dict(state,generating=True)
  switched=dict(state,url='https://chatgpt.com/c/other')
  for sequence in ([state,busy,state],[state,switched,state]):
   with patch.object(browser,'chatgpt_dom',side_effect=sequence),patch('automation_agent.browser_controller.time.sleep',return_value=None):
    self.assertFalse(browser.chatgpt_dom_observe()['completion_verified'])

 def test_dom_observe_rejects_empty_assistant(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  state={'url':'https://chatgpt.com/c/test','assistantCount':0,'turnCount':1,'lastAssistant':'','generating':False,'composerReady':True,'sendControlPresent':True}
  with patch.object(browser,'chatgpt_dom',side_effect=[state,state,state]),patch('automation_agent.browser_controller.time.sleep',return_value=None):
   self.assertFalse(browser.chatgpt_dom_observe()['completion_verified'])


 def test_send_requires_exact_receipt(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  import hashlib
  prompt='Continue test';base={'url':'https://chatgpt.com/c/test','turnCount':4}
  receipt=dict(base,turnCount=5,lastUserText=prompt)
  class Edit:
   element_info=type('Info',(),{'automation_id':'prompt-textarea'})()
   def is_enabled(self):return True
   def is_visible(self):return True
   def set_edit_text(self,text):self.text=text
   def window_text(self):return self.text
  edit=Edit()
  class Root:
   def descendants(self,control_type=None):return [edit]
  verified=dict(base,completion_verified=True,fingerprint=hashlib.sha256(b'answer').hexdigest())
  with patch.object(browser,'chatgpt_dom_observe',return_value=verified),patch.object(browser,'chatgpt_dom',return_value=receipt),patch('automation_agent.browser_controller.ui.root',return_value=Root()),patch('automation_agent.browser_controller.wm.validate_target'),patch('automation_agent.browser_controller.ui.hotkey') as hotkey:
   result=browser.chatgpt_send_verified(prompt,'exchange-001',base['url'],verified['fingerprint'])
  self.assertEqual(result['submission'],'received')
  hotkey.assert_called_once()

 def test_send_does_not_retry_after_missing_receipt(self):
  browser=BrowserController({'hwnd':123,'target_app':'chrome'})
  import hashlib
  prompt='Continue test';base={'url':'https://chatgpt.com/c/test','turnCount':4}
  class Edit:
   element_info=type('Info',(),{'automation_id':'prompt-textarea'})()
   def is_enabled(self):return True
   def is_visible(self):return True
   def set_edit_text(self,text):self.text=text
   def window_text(self):return self.text
  class Root:
   def descendants(self,control_type=None):return [Edit()]
  verified=dict(base,completion_verified=True,fingerprint=hashlib.sha256(b'answer').hexdigest())
  with patch.object(browser,'chatgpt_dom_observe',return_value=verified),patch.object(browser,'chatgpt_dom',return_value=dict(base,lastUserText='')),patch('automation_agent.browser_controller.ui.root',return_value=Root()),patch('automation_agent.browser_controller.wm.validate_target'),patch('automation_agent.browser_controller.ui.hotkey') as hotkey,patch('automation_agent.browser_controller.time.sleep',return_value=None):
   with self.assertRaises(RuntimeError):browser.chatgpt_send_verified(prompt,'exchange-002',base['url'],verified['fingerprint'])
  hotkey.assert_called_once()


if __name__=='__main__':unittest.main()
