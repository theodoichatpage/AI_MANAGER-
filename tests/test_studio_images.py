import copy,io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from automation_agent.studio_workflow import StudioStep,workflow,StudioReviewRequired
from automation_agent.studio_images import save_image,fetch_image
from studio_catalog import matches,canonical
SID='a'*32
class API:
 def __init__(self):self.posts=[];self.s={'id':SID,'stylePrompt':'Existing style','parts':[{'id':'part_1','status':'complete','scenes':[{'prompt':'scene1','imageStatus':'waiting'},{'prompt':'scene2','imageStatus':'waiting'}]}]}
 def request(self,sid,route='',body=None):
  if body is not None:
   self.posts.append(copy.deepcopy(body));self.s['activeJob']={'id':'image'+str(len(self.posts)),'type':'image_generation','sceneKey':body['sceneKeys'][0]}
  return copy.deepcopy(self.s)
class ImageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.c={'studio_project_id':SID,'studio_run_id':'run','studio_origin':'https://video-image-studio.vercel.app','studio_folder':self.tmp.name}
  self.api=API();self.pres=lambda:{'studio_tab_open':True,'chat_connected':True,'session_id':SID,'manager_run_id':'run','origin':self.c['studio_origin']}
  b=io.BytesIO();Image.new('RGB',(4,4),'blue').save(b,'JPEG');self.data=b.getvalue()
 def tearDown(self):self.tmp.cleanup()
 def step(self):return StudioStep(self.c,self.api,self.pres).step('STUDIO_IMAGES')
 def test_only_missing_images_sequential_and_checkpoint(self):
  self.step();self.step();self.assertEqual(len(self.api.posts),1)
  self.api.s['activeJob']=None;self.api.s['parts'][0]['scenes'][0].update(imageStatus='complete',imageResults=[{'url':'https://unused'}])
  with patch('automation_agent.studio_images.fetch_image',return_value=self.data):
   # Inject fetch explicitly because save_image binds default fetch at definition.
   from automation_agent import studio_images
   original=studio_images.save_image
   with patch.object(studio_images,'save_image',side_effect=lambda *a:original(*a,fetch=lambda u:self.data)):
    self.step();self.step();self.assertEqual(self.api.posts[-1]['sceneKeys'],['part_1:1']);self.assertEqual(len(self.api.posts),2)
    self.api.s['activeJob']=None;self.api.s['parts'][0]['scenes'][1].update(imageStatus='complete',imageResults=[{'url':'https://unused'}]);self.step();r=self.step();self.assertNotIn('waiting',r);self.assertEqual(r['context']['studio_images_saved'],2)
 def test_file_format_and_cache_and_collision(self):
  folder=Path(self.tmp.name)/'images';p=save_image(folder,SID,'p:0',{'url':'unused'},fetch=lambda u:self.data);self.assertTrue(p.endswith('.jpg'));self.assertEqual(save_image(folder,SID,'p:0',{},fetch=lambda u:(_ for _ in ()).throw(Exception())),p)
 def test_missing_style_or_prompt_never_posts(self):
  self.api.s['stylePrompt']=''
  # Missing style: wait for the run's Studio tab to save it, never post an image job meanwhile.
  r=self.step();self.assertIn('phong cách',r['context']['studio_message']);self.assertEqual(self.api.posts,[])
  self.api.s['parts'][0]['scenes'][0]['prompt']=''
  with self.assertRaisesRegex(ValueError,'prompt'):self.step()
 def test_external_job_blocks(self):
  self.api.s['activeJob']={'id':'external','type':'image_generation','sceneKey':'part_1:0'}
  with self.assertRaises(RuntimeError):self.step()
  self.assertEqual(self.api.posts,[])
 def test_uncertain_post_keeps_intent(self):
  old=self.api.request
  def broken(sid,route='',body=None):
   if body is not None:raise TimeoutError()
   return old(sid,route,body)
  self.api.request=broken
  with self.assertRaises(StudioReviewRequired):self.step()
  self.api.request=old
  with self.assertRaises(StudioReviewRequired):self.step()
 def test_untrusted_download_rejected(self):
  with self.assertRaises(ValueError):fetch_image('http://127.0.0.1/private')
 def test_selected_stages(self):
  a,c=workflow(SID,'https://video-image-studio.vercel.app','edge','Default',self.tmp.name,'',stages=['images']);self.assertEqual(a[-1]['action'],'STUDIO_IMAGES');self.assertFalse(any(x['action']=='STUDIO_ANALYZE' for x in a));self.assertIn('managerStage=images',c['studio_launch_url'])
  with self.assertRaises(ValueError):workflow(SID,'https://video-image-studio.vercel.app','edge','Default',self.tmp.name,'',stages=[])
 def test_identity_legacy_and_canonical_keeps_progress(self):
  key={'id':SID,'origin':'https://video-image-studio.vercel.app','browser':'edge','profile':'Default'}
  p={'id':'old','studio_project_id':SID,'studio_url':key['origin']+'/','browser':'edge','browser_profile':'Default'};duplicate={'id':'new','studio_source':key}
  self.assertTrue(matches(p,key));self.assertTrue(matches(duplicate,key));self.assertEqual(canonical([p,duplicate],{'old':{'automation_task_id':'task','action_done':9},'new':{}})['id'],'old');self.assertFalse(matches(dict(p,browser_profile='Profile 2'),key));self.assertFalse(matches(dict(p,studio_project_id='b'*32),key))

 def test_invalid_image_never_marked_saved(self):
  with self.assertRaises(Exception):save_image(Path(self.tmp.name)/'images',SID,'p:0',{'url':'unused'},fetch=lambda u:b'<html>error</html>')
  self.assertEqual(list((Path(self.tmp.name)/'images').glob('*.json')),[])
 def test_error_needs_explicit_retry(self):
  self.api.s['parts'][0]['scenes'][0]['imageStatus']='error'
  with self.assertRaises(RuntimeError):self.step()
  self.assertEqual(self.api.posts,[]);self.c['studio_retry_epoch']=1;self.step();self.assertEqual(len(self.api.posts),1)

 def test_incomplete_part_cannot_be_marked_complete_by_image_only_run(self):
  self.api.s['parts'].append({'id':'p2','status':'ready','scenes':[]})
  with self.assertRaisesRegex(ValueError,'Phân cảnh'):self.step()
  self.assertEqual(self.api.posts,[])
