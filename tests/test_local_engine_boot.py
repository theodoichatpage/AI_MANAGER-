"""Manager starts the Local Engine itself when a step finds it down (bounded, never a storm of processes)."""
import unittest
from automation_agent import local_engine_boot as boot

class Boot(unittest.TestCase):
 def test_starts_once_then_waits_for_the_models_to_load(self):
  st={};started=[]
  m=boot.ensure(st,1000,start=lambda:started.append(1));self.assertIn('đang tự bật (lần 1/5)',m)
  self.assertIn('đang chờ nó nạp',boot.ensure(st,1030,start=lambda:started.append(1)));self.assertEqual(len(started),1)
  self.assertIn('lần 2/5',boot.ensure(st,1000+boot.START_GAP+1,start=lambda:started.append(1)));self.assertEqual(len(started),2)
 def test_gives_up_after_the_limit_and_says_what_to_do(self):
  st={};t=1000
  for _ in range(boot.MAX_STARTS):boot.ensure(st,t,start=lambda:None);t+=boot.START_GAP+1
  m=boot.ensure(st,t,start=lambda:self.fail('no more starts'))
  self.assertIn('start_engine.bat',m)
 def test_not_installed_is_reported_once(self):
  def missing():raise FileNotFoundError('Chưa cài Local Engine.')
  st={};self.assertIn('Chưa cài',boot.ensure(st,1000,start=missing))
  self.assertIn('start_engine.bat',boot.ensure(st,5000,start=missing),'later rounds do not retry a missing install')

if __name__=='__main__':unittest.main()
