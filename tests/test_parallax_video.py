"""Làm video Parallax: Manager starts Parallax25D.exe --cli detached and follows its status file."""
import json,tempfile,time,unittest
from pathlib import Path
from automation_agent import parallax_video as pv
from automation_agent.work_config import normalize

class Proc:
 def __init__(self,pid=4321):self.pid=pid

class ParallaxVideo(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.project=Path(self.tmp.name)/'001_A';self.project.mkdir()
 def tearDown(self):self.tmp.cleanup()
 def scene(self,rel):
  d=self.project/'Tach anh'/rel;d.mkdir(parents=True)
  for n in ('01_bg.png','02_mid.png','03_fg.png'):(d/n).write_bytes(b'x')
  return d
 def test_counts_scene_folders_and_skips_backups(self):
  self.scene('Phan 1 - A/Canh 1 - B');self.scene('Phan 1 - A/Canh 2 - C');self.scene('_backups/run/Canh 1 - B')
  (self.project/'Tach anh'/'Phan 1 - A'/'Canh 1 - B'/'_kiem_tra').mkdir()
  self.assertEqual(pv.scenes_ready(self.project/'Tach anh'),2)
  self.assertEqual(pv.scenes_ready(self.project/'none'),0)
 def test_start_builds_the_command_and_clears_an_old_status(self):
  exe=Path(self.tmp.name)/'Parallax25D.exe';exe.write_bytes(b'')
  old=self.project/'.vis'/pv.STATUS_NAME;old.parent.mkdir();old.write_text('{"state":"done"}')
  calls=[];popen=lambda args,**kw:calls.append(args) or Proc()
  job=pv.start(self.project,'9:16','dolly',True,exe=exe,popen=popen,clock=lambda:100.0)
  self.assertFalse(old.exists(),'an old status file must not be read as this run')
  args=calls[0]
  self.assertEqual(args[:4],[str(exe),'--cli',str(self.project/'Tach anh'),str(self.project/'Video Parallax')])
  self.assertIn('1080x1920',args);self.assertIn('dolly',args);self.assertIn('--rerun',args)
  self.assertEqual(job,{'pid':4321,'at':100.0,'status':str(old),'exe':str(exe)})
  with self.assertRaises(FileNotFoundError):
   import os;from unittest.mock import patch
   with patch.object(pv,'find_exe',lambda:None):pv.start(self.project)
 def test_check_follows_the_status_file(self):
  status=self.project/'s.json';job={'pid':1,'at':100.0,'status':str(status)}
  self.assertEqual(pv.check(job,clock=lambda:105,is_alive=lambda p:True)[0],'running','unpacking: no file yet')
  self.assertEqual(pv.check(job,clock=lambda:300,is_alive=lambda p:False)[0],'error','gone without any status')
  status.write_text(json.dumps({'state':'done','started_at':50}))
  self.assertEqual(pv.check(job,clock=lambda:105,is_alive=lambda p:True)[0],'running','a file from an earlier run is ignored')
  status.write_text(json.dumps({'state':'running','started_at':101,'done':1,'total':3,'percent':40}))
  kind,info=pv.check(job,clock=lambda:120,is_alive=lambda p:True);self.assertEqual((kind,info['percent']),('running',40))
  self.assertEqual(pv.check(job,clock=lambda:120,is_alive=lambda p:False),('error','Parallax25D đã tắt giữa chừng (1/3 video).'))
  status.write_text(json.dumps({'state':'done','started_at':101,'done':3,'total':3}))
  self.assertEqual(pv.check(job,clock=lambda:130,is_alive=lambda p:False)[0],'done')
  status.write_text(json.dumps({'state':'error','started_at':101,'error':'bad --res'}))
  self.assertEqual(pv.check(job,clock=lambda:130,is_alive=lambda p:False),('error','bad --res'))
 def test_board_summary_start_and_stop_by_hand(self):
  import os
  status=self.project/'.vis'/pv.STATUS_NAME;status.parent.mkdir()
  self.assertEqual(pv.summary(self.project)['state'],'idle');self.assertEqual(pv.summary(self.project)['videos'],0)
  (self.project/pv.OUTPUT/'Phan 1 - A').mkdir(parents=True);(self.project/pv.OUTPUT/'Phan 1 - A'/'Canh 1 - B.mp4').write_bytes(b'x')
  status.write_text(json.dumps({'state':'running','done':1,'total':4,'percent':25}))
  s=pv.summary(self.project);self.assertEqual((s['state'],s['done'],s['total'],s['videos']),('running',1,4,1))
  old=time.time()-600;os.utime(status,(old,old))
  self.assertEqual(pv.summary(self.project)['state'],'stopped','a running file nobody updates any more is a stopped program')
  with self.assertRaises(ValueError):pv.start_manual(self.project)  # no separated scenes yet
  self.scene('Phan 1 - A/Canh 1 - B')
  exe=Path(self.tmp.name)/'Parallax25D.exe';exe.write_bytes(b'')
  calls=[];job=pv.start_manual(self.project,'16:9','dolly',False,exe=exe,popen=lambda args,**kw:calls.append(args) or Proc(777))
  self.assertEqual(job['pid'],777);self.assertIn('dolly',calls[0])
  self.assertEqual(json.loads((self.project/'.vis'/pv.JOB_NAME).read_text())['pid'],777)
  killed=[];pv.stop_manual(self.project,run=lambda args,**kw:killed.append(args))
  self.assertEqual(killed[0][:3],['taskkill','/PID','777']);self.assertFalse((self.project/'.vis'/pv.JOB_NAME).exists())
  with self.assertRaises(ValueError):pv.stop_manual(self.project)
 def test_work_config_accepts_parallax(self):
  c=normalize({'tasks':['separate','parallax','sync'],'parallax_motion':'zoomin'})
  self.assertEqual(c['tasks'],['sync','separate','parallax']);self.assertEqual(c['parallax_motion'],'zoomin')
  with self.assertRaises(ValueError):normalize({'tasks':['parallax'],'parallax_motion':'spin'})
  with self.assertRaises(ValueError):normalize({'tasks':['parallax'],'scopes':{'parallax':{'mode':'range','from':1,'to':2}}})

if __name__=='__main__':unittest.main()
