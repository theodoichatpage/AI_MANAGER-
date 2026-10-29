"""Egress: Manager re-downloads a Studio project only when its version stamp changed; gzip replies decode."""
import gzip,json,unittest
from automation_agent import studio_cache

class Cache(unittest.TestCase):
 def setUp(self):
  studio_cache._cache.clear();self.calls=[];self.version={'updatedAt':1,'workEpoch':0};self.full={'id':'s'*16,'updatedAt':1,'workEpoch':0,'parts':[]}
  def call(path,body=None,timeout=10):
   self.calls.append(path)
   if path.endswith('/version'):return {'version':self.version}
   return {'session':dict(self.full)}
  self.orig=studio_cache.call;studio_cache.call=call
 def tearDown(self):studio_cache.call=self.orig
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
class LaneCommandReply(unittest.TestCase):
 def test_lane_post_returns_the_command(self):
  from automation_agent.studio_workflow import StudioAPI
  orig=studio_cache.call;studio_cache.call=lambda path,body=None,timeout=10:{'command':{'id':'job9'},'session':{'id':'s'*16,'updatedAt':5}}
  try:self.assertEqual(StudioAPI().request('s'*16,'/lanes/laneA01/parts/p1',{})['command']['id'],'job9')
  finally:studio_cache.call=orig
if __name__=='__main__':unittest.main()
