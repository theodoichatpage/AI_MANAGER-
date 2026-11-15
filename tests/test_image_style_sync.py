"""Saving the image prompt in Manager pushes it to the project's Studio (user, 2026-11-15)."""
import unittest
from unittest import mock
import server

class FakeAPI:
 style='old';posts=[]
 def request(self,sid,route=None,body=None):
  if route:FakeAPI.posts.append((sid,route,body));FakeAPI.style=body['stylePrompt'];return {}
  return {'stylePrompt':FakeAPI.style}

class Sync(unittest.TestCase):
 def setUp(self):FakeAPI.style='old';FakeAPI.posts=[]
 def run_sync(self,meta,p=None):
  with mock.patch('automation_agent.studio_workflow.StudioAPI',FakeAPI):return server.sync_image_style({'studio_project_id':'sid1'} if p is None else p,meta)
 def test_changed_prompt_goes_to_studio(self):
  self.assertEqual(self.run_sync({'images':True,'image_style':'new style'}),'synced')
  self.assertEqual(FakeAPI.posts,[('sid1','/settings',{'stylePrompt':'new style'})])
 def test_same_prompt_is_not_sent_again(self):
  FakeAPI.style='same';self.assertEqual(self.run_sync({'images':True,'image_style':'same'}),'same');self.assertEqual(FakeAPI.posts,[])
 def test_switch_off_empty_or_no_studio_leaves_studio_alone(self):
  self.assertEqual(self.run_sync({'images':False,'image_style':'x'}),'skipped')
  self.assertEqual(self.run_sync({'images':True,'image_style':'  '}),'skipped')
  self.assertEqual(self.run_sync({'images':True,'image_style':'x'},p={}),'skipped')
  self.assertEqual(FakeAPI.posts,[])

if __name__=='__main__':unittest.main()
