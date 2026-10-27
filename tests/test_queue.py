import tempfile, unittest
from pathlib import Path
from queue_manager import QueueManager

class QueueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.q=QueueManager(self.root)
  for i in 'ABC': self.q.add({'id':i,'name':i,'folder':str(self.root/i)})
 def tearDown(self): self.q.close(); self.tmp.cleanup()
 def test_sequence_and_recovery(self):
  q=self.q; q.start_all(); self.assertEqual([x['status'] for x in q.list()],['running','waiting','waiting'])
  q.progress('A',3,10); q.pause('A'); q.progress('A',5,10); self.assertEqual(q.get('A')['completed_scenes'],3)
  q.resume('A'); q.finish('A'); self.assertEqual(q.get('B')['status'],'running')
  q.fail('B','test'); self.assertEqual(q.get('C')['status'],'running')
  q.retry_errors(); self.assertEqual(q.get('B')['status'],'waiting')
  q.stop_all(); self.assertEqual(q.get('C')['status'],'stopped'); self.assertEqual(q.get('A')['status'],'completed')
  q.start_all(); self.assertEqual(q.get('B')['status'],'running'); q.progress('B',4,10)
  q.close(); self.q=QueueManager(self.root); q=self.q
  self.assertEqual(q.get('B')['status'],'paused'); self.assertEqual(q.get('B')['completed_scenes'],4)
  self.assertEqual([x['id'] for x in q.list()],['A','B','C']); self.assertTrue(q.logs())
 def test_reorder_and_single_running(self):
  q=self.q; q.move('C',-1); self.assertEqual([x['id'] for x in q.list()],['A','C','B'])
  q.start_all()
  with self.assertRaises(ValueError): q.move('A',1)
  with self.assertRaises(ValueError): q.resume('B')
  self.assertEqual(sum(x['status']=='running' for x in q.list()),1)
if __name__=='__main__': unittest.main()
