"""The Local Engine (separation) is a program on this PC. When a step needs it and it is not running, Manager starts it
itself instead of asking the user to open it. At most one start per 90 s and 5 per run; the loading of the models takes
about 20 s, so a recent start means "wait"."""
import os,subprocess
from pathlib import Path

START_GAP=90
MAX_STARTS=5
DETACHED=0x00000008|0x00000200|0x08000000  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

def engine_dir():return Path(os.environ.get('LOCALAPPDATA') or Path.home())/'VIDEO_IMAGE_STUDIO'/'LocalEngine'

def launch(popen=subprocess.Popen):
 home=engine_dir();python=home/'.venv'/'Scripts'/'python.exe'
 if not python.is_file() or not (home/'app.py').is_file():raise FileNotFoundError('Chưa cài Local Engine. Chạy file VIDEO_IMAGE_STUDIO_Local_Engine_Setup.bat một lần.')
 popen([str(python),'app.py'],cwd=str(home),creationflags=DETACHED,close_fds=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def ensure(state,now,start=None):
 """Message for the board; starts the engine when it is time. `state` is a dict kept in the step's journal."""
 b=state.setdefault('engine_boot',{'at':0,'tries':0})
 if b['tries'] and now-float(b['at'])<START_GAP:return 'Manager đã bật Local Engine, đang chờ nó nạp mô hình (khoảng 20 giây).'
 if b['tries']>=MAX_STARTS:return 'Local Engine không tự bật được sau %d lần. Mở start_engine.bat trong %s rồi Manager sẽ tách tiếp.'%(MAX_STARTS,engine_dir())
 try:(start or launch)()
 except OSError as exc:
  b['tries']=MAX_STARTS;return str(exc)
 b.update(at=now,tries=b['tries']+1)
 return 'Local Engine chưa chạy: Manager đang tự bật (lần %d/%d).'%(b['tries'],MAX_STARTS)
