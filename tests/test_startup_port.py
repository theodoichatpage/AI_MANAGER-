import os,socket,subprocess,sys,tempfile,unittest
class StartupPortTest(unittest.TestCase):
 def test_busy_port_displays_clear_message_and_does_not_open_old_version(self):
  with socket.socket() as sock, tempfile.TemporaryDirectory() as td:
   sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); sock.bind(('127.0.0.1',8765));sock.listen()
   p=subprocess.run([sys.executable,'server.py','--no-browser'],env=dict(os.environ,AI_MANAGER_HOME=td),capture_output=True,text=True,timeout=5)
   self.assertNotEqual(p.returncode,0); self.assertIn('8765',p.stdout); self.assertIn('AI MANAGER',p.stdout)
if __name__=='__main__':unittest.main()
