"""AI Manager as a desktop app.

  app_launcher.pyw              start Manager in the background if needed, then open its own window
  app_launcher.pyw --background start Manager in the background only (Windows start-up)
  app_launcher.pyw --restart    wait for the old Manager to stop, then start it again (after an update)
Run with the Manager runtime's pythonw.exe so no console window appears."""
import os,subprocess,sys,time,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8765/'
RUNTIME=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'AI_MANAGER'/'runtime-v02'/'Scripts'
NO_WINDOW=0x08000000;DETACHED=0x00000008

def running():
 try:
  with urllib.request.urlopen(URL+'api/state',timeout=3) as r:return r.status==200
 except Exception:return False

def start_server():
 python=RUNTIME/'python.exe'
 if not python.exists():python=Path(sys.executable)
 log=ROOT/'logs';log.mkdir(exist_ok=True)
 with open(log/'manager.log','ab') as out:
  subprocess.Popen([str(python),str(ROOT/'server.py'),'--no-browser'],cwd=str(ROOT),stdout=out,stderr=out,stdin=subprocess.DEVNULL,creationflags=NO_WINDOW|DETACHED,close_fds=True)
 for _ in range(60):
  if running():return True
  time.sleep(0.5)
 return False

def edge():
 for base in (os.environ.get('ProgramFiles(x86)'),os.environ.get('ProgramFiles'),os.environ.get('LOCALAPPDATA')):
  if base and (Path(base)/'Microsoft'/'Edge'/'Application'/'msedge.exe').exists():return Path(base)/'Microsoft'/'Edge'/'Application'/'msedge.exe'
 return None

def open_window():
 path=edge()
 if path:subprocess.Popen([str(path),'--app='+URL,'--profile-directory=Default','--window-size=1500,950'],creationflags=DETACHED,close_fds=True)
 else:os.startfile(URL)

def main(argv):
 if '--restart' in argv:
  for _ in range(40):
   if not running():break
   time.sleep(0.5)
 if not running() and not start_server():
  import ctypes;ctypes.windll.user32.MessageBoxW(None,'Không khởi động được AI Manager. Xem logs\\manager.log trong thư mục AI_MANAGER.','AI Manager',0x10);return 1
 if '--background' not in argv:open_window()
 return 0

if __name__=='__main__':sys.exit(main(sys.argv[1:]))
