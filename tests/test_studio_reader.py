import unittest
from studio_reader import summarize_session
class StudioReaderTests(unittest.TestCase):
 def test_summary_reads_real_states_and_project_name(self):
  s={'id':'test-session-id-1234','projectName':'Dự án thật trong Studio','status':'image_processing','parts':[{'id':'p1','title':'Part 1','status':'complete','scenes':[{'title':'Scene 1','prompt':'a','imageStatus':'complete'},{'title':'Scene 2','prompt':'b','imageStatus':'error'}]}], 'activeJob':{'type':'image_generation','sceneKey':'p1:1','status':'waiting'}}
  x=summarize_session(s)
  self.assertEqual(x['project_name'],'Dự án thật trong Studio')
  self.assertEqual((x['total_parts'],x['completed_parts'],x['total_scenes'],x['analyzed_scenes'],x['images_done'],x['images_failed']),(1,1,2,2,1,1))
  self.assertEqual(x['current_scene'],'Scene 2');self.assertIsNone(x['chat_connected']);self.assertIsNone(x['studio_tab_open'])
 def test_name_schema_fallbacks(self):
  self.assertEqual(summarize_session({'id':'x','name':'Tên Studio'})['project_name'],'Tên Studio')
  self.assertEqual(summarize_session({'id':'x','project':{'title':'Tên lồng'}})['project_name'],'Tên lồng')
 def test_unknown_not_zero(self):
  x=summarize_session({'id':'x'});self.assertIsNone(x['total_parts']);self.assertIsNone(x['project_name'])
if __name__=='__main__':unittest.main()
