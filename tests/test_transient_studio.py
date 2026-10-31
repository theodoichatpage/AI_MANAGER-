"""A short network drop while talking to Studio is waited out; deleted projects stay deleted on auto sync."""
import json,socket,tempfile,unittest,urllib.error
from pathlib import Path
import project_ops
from automation_agent.action_worker import network_error

class Transient(unittest.TestCase):
 def test_network_errors(self):
  self.assertTrue(network_error(urllib.error.URLError('down')))
  self.assertTrue(network_error(socket.timeout()))
  self.assertTrue(network_error(ConnectionResetError()))
  self.assertTrue(network_error(urllib.error.HTTPError('u',502,'bad gateway',{},None)))
  self.assertFalse(network_error(urllib.error.HTTPError('u',404,'nf',{},None)))
  self.assertFalse(network_error(RuntimeError('Studio trả sai project ID; đã chặn')))
  self.assertFalse(network_error(ValueError('x')))
  import ssl,http.client,zlib,json
  self.assertTrue(network_error(ssl.SSLError('EOF occurred in violation of protocol')))
  self.assertTrue(network_error(http.client.IncompleteRead(b'')))
  self.assertTrue(network_error(http.client.RemoteDisconnected('closed')))
  self.assertTrue(network_error(zlib.error('truncated')))
  self.assertTrue(network_error(json.JSONDecodeError('x','<html>',0)))
  self.assertTrue(network_error(urllib.error.HTTPError('u',429,'busy',{},None)))
  self.assertFalse(network_error(FileNotFoundError('checkpoint')))
  self.assertTrue(network_error(TimeoutError('The read operation timed out')))
  self.assertFalse(network_error(TimeoutError('Studio quá thời gian tại STUDIO_PARALLEL; giữ checkpoint')))
 def test_trashed_studio_ids(self):
  with tempfile.TemporaryDirectory() as t:
   for i,m in enumerate(({'studio_project_id':'a'*32},{'studio_import_id':'b'*32,'studio_source':{'id':'c'*32}},{})):
    d=Path(t)/'_Thung_rac'/('00%d_x'%i);d.mkdir(parents=True);(d/'project.json').write_text(json.dumps(m))
   (Path(t)/'_Thung_rac'/'bad').mkdir();(Path(t)/'_Thung_rac'/'bad'/'project.json').write_text('{')
   self.assertEqual(project_ops.trashed_studio_ids(t),{'a'*32,'b'*32,'c'*32})
   self.assertEqual(project_ops.trashed_studio_ids(Path(t)/'none'),set())
if __name__=='__main__':unittest.main()
