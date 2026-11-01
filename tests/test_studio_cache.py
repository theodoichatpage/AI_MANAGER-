"""Egress: Manager re-downloads a Studio project only when its version stamp changed; gzip replies decode."""
import gzip,json,unittest
from automation_agent import studio_cache

class Cache(unittest.TestCase):
 def setUp(self):
  import os;self._home=os.environ.pop('AI_MANAGER_AGENT_HOME',None)  # other tests may leave a disk copy
  studio_cache._cache.clear();self.calls=[];self.version={'updatedAt':1,'workEpoch':0};self.full={'id':'s'*16,'updatedAt':1,'workEpoch':0,'parts':[]}
  def call(path,body=None,timeout=10,reply=None):
   self.calls.append(path)
   if path.endswith('/version'):return {'version':self.version}
   return {'session':dict(self.full)}
  self.orig=studio_cache.call;studio_cache.call=call
 def tearDown(self):
  import os;studio_cache.call=self.orig
  if self._home is not None:os.environ['AI_MANAGER_AGENT_HOME']=self._home
 def test_unchanged_project_is_not_downloaded_again(self):
  sid='s'*16
  studio_cache.session(sid);studio_cache.session(sid);studio_cache.session(sid)
  self.assertEqual([p for p in self.calls if not p.endswith('/version')],['sessions/'+sid])
  self.full['updatedAt']=2;self.version={'updatedAt':2,'workEpoch':0}
  self.assertEqual(studio_cache.session(sid)['updatedAt'],2)
  self.assertEqual(len([p for p in self.calls if not p.endswith('/version')]),2)
 def test_older_server_without_stamp_reads_full(self):
  self.version=None;sid='s'*16
  studio_cache.session(sid);studio_cache.session(sid)
  self.assertEqual(len([p for p in self.calls if not p.endswith('/version')]),2)
 def test_cached_copy_cannot_be_changed_by_caller(self):
  sid='s'*16;a=studio_cache.session(sid);a['parts'].append('x')
  self.assertEqual(studio_cache.session(sid)['parts'],[])
 def test_gzip_decode_and_limit(self):
  body={'session':{'id':'x'}}
  self.assertEqual(studio_cache.decode(gzip.compress(json.dumps(body).encode()),'gzip'),body)
  bomb=gzip.compress(b' '*(4*studio_cache.LIMIT+10))
  with self.assertRaises(ValueError):studio_cache.decode(bomb,'gzip')
class DiskCopy(Cache):
 """A new process (each Manager step) reuses the copy saved on disk instead of downloading the project again."""
 def test_new_process_uses_disk_copy(self):
  import os,tempfile,time
  with tempfile.TemporaryDirectory() as home:
   os.environ['AI_MANAGER_AGENT_HOME']=home
   try:
    sid='s'*16;studio_cache.session(sid);studio_cache._cache.clear()
    studio_cache.session(sid)
    self.assertEqual(len([p for p in self.calls if not p.endswith('/version')]),1,'second process: version check only')
    studio_cache._cache.clear();studio_cache.DISK_MAX_AGE,old=-1,studio_cache.DISK_MAX_AGE
    try:studio_cache.session(sid)
    finally:studio_cache.DISK_MAX_AGE=old
    self.assertEqual(len([p for p in self.calls if not p.endswith('/version')]),2,'an old disk copy is read again')
   finally:os.environ.pop('AI_MANAGER_AGENT_HOME',None)
class LaneCommandReply(unittest.TestCase):
 def test_lane_post_returns_the_command(self):
  from automation_agent.studio_workflow import StudioAPI
  orig=studio_cache.call;studio_cache.call=lambda path,body=None,timeout=10,reply=None:{'command':{'id':'job9'},'session':{'id':'s'*16,'updatedAt':5}}
  try:self.assertEqual(StudioAPI().request('s'*16,'/lanes/laneA01/parts/p1',{})['command']['id'],'job9')
  finally:studio_cache.call=orig
class Lean(unittest.TestCase):
 """After one full read, changes come as lean replies; the project text is merged back from the copy Manager holds."""
 def setUp(self):
  import os;self._home=os.environ.pop('AI_MANAGER_AGENT_HOME',None);studio_cache._cache.clear();self.calls=[]
  self.text={'script':'KỊCH BẢN','parts':[{'id':'p1','title':'Phần 1','content':'nội dung','status':'complete','scenes':[{'title':'Cảnh 1','prompt':'a door','imageStatus':'waiting'}]}]}
  self.fp='fp1';self.version={'updatedAt':1,'workEpoch':0}
  def lean_of(full):
   s={k:v for k,v in full.items() if k not in ('script','stylePrompt','rewrite')}
   s['parts']=[{**{k:v for k,v in p.items() if k not in ('title','content','range','analysisText')},'scenes':[{k:v for k,v in sc.items() if k not in ('title','prompt','content','backdrop','character','emotion','shot')} for sc in p['scenes']]} for p in full['parts']]
   return s
  def call(path,body=None,timeout=10,reply=None):
   self.calls.append((path,reply))
   if path.endswith('/version'):return {'version':self.version}
   full={'id':'s'*16,'updatedAt':self.version['updatedAt'],'workEpoch':0,**json.loads(json.dumps(self.text))}
   return {'session':lean_of(full),'textsFp':self.fp,'lean':True} if reply=='lean' else {'session':full,'textsFp':self.fp}
  self.orig=studio_cache.call;studio_cache.call=call
 def tearDown(self):
  import os;studio_cache.call=self.orig
  if self._home is not None:os.environ['AI_MANAGER_AGENT_HOME']=self._home
 def test_status_change_downloads_only_the_lean_part(self):
  sid='s'*16;studio_cache.session(sid)
  self.text['parts'][0]['scenes'][0]['imageStatus']='complete';self.version={'updatedAt':2,'workEpoch':0}
  s=studio_cache.session(sid)
  self.assertEqual(self.calls[-1],('sessions/'+sid,'lean'),'a change reads the lean reply only')
  self.assertEqual(s['script'],'KỊCH BẢN');self.assertEqual(s['parts'][0]['scenes'][0]['prompt'],'a door');self.assertEqual(s['parts'][0]['scenes'][0]['imageStatus'],'complete')
 def test_changed_text_reads_the_full_project_once(self):
  sid='s'*16;studio_cache.session(sid)
  self.text['parts'][0]['scenes'][0]['prompt']='a window';self.fp='fp2';self.version={'updatedAt':3,'workEpoch':0}
  s=studio_cache.session(sid)
  self.assertEqual(self.calls[-2:],[('sessions/'+sid,'lean'),('sessions/'+sid,'fp')]);self.assertEqual(s['parts'][0]['scenes'][0]['prompt'],'a window')
 def test_command_reply_is_completed(self):
  from automation_agent.studio_workflow import StudioAPI
  sid='s'*16;studio_cache.session(sid)
  s=StudioAPI().request(sid,'/settings',{'stylePrompt':'x'})
  self.assertEqual(s['parts'][0]['title'],'Phần 1');self.assertEqual(self.calls[-1],('sessions/'+sid+'/settings','lean'))
if __name__=='__main__':unittest.main()
