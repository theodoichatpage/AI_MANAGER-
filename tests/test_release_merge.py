"""Regression checks for the local/GitHub release merge; no external services."""
import tempfile
import unittest
from unittest.mock import patch
from automation_agent.studio_workflow import StudioStep
from server import project_state

class ReleaseMergeTests(unittest.TestCase):
 def transcript_step(self, folder, done=False, redo=False):
  context={'studio_project_id':'a'*32,'studio_run_id':'run','studio_folder':folder,'studio_aprilynne':False,'studio_youtube_url':'https://youtu.be/abcdefghijk'}
  class API:
   def request(self,*args):return {'id':'a'*32,'script':'existing script','parts':[]}
  presence=lambda:{'project_state':{'pipeline':{'id':'owned','stage':'done' if done else 'rewrite'}}}
  step=StudioStep(context,API(),presence)
  step.ready=lambda:True
  step.j['transcript_command']={'id':'owned'}
  if redo:step.j['transcript_redo']=True
  return step
 def test_completed_owned_transcript_does_not_restart(self):
  with tempfile.TemporaryDirectory() as folder:
   step=self.transcript_step(folder,done=True)
   with patch.object(step,'transcript_pipeline') as pipeline:
    result=step.step('STUDIO_TRANSCRIPT')
    pipeline.assert_not_called()
    self.assertNotIn('waiting',result)
 def test_explicit_redo_can_replace_existing_script(self):
  with tempfile.TemporaryDirectory() as folder:
   step=self.transcript_step(folder,redo=True)
   with patch.object(step,'transcript_pipeline',return_value={'waiting':True}) as pipeline:
    self.assertTrue(step.step('STUDIO_TRANSCRIPT')['waiting'])
    pipeline.assert_called_once()
 def test_review_preserves_both_progress_and_pipeline_counters(self):
  review=project_state({'analysisReview':{'id':'review','stage':'approved','done':2,'total':3,'attempts':1,'progress':7,'fingerprint':'a'*64}})['analysis_review']
  self.assertEqual((review['done'],review['total'],review['attempts'],review['progress']),(2,3,1,7))
  self.assertEqual(review['fingerprint'],'a'*64)
