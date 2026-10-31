"""Làm video Parallax (task 'parallax'): turn separated scenes into 2.5D videos with Parallax25D.exe.

Input:  <project>/Tach anh/Phan N - .../Canh M - .../ (layer PNGs from "Tách ảnh")
Output: <project>/Video Parallax/Phan N - .../Canh M - ....mp4
Parallax25D.exe --cli makes every scene it finds (skipping ones whose video is newer than its layers) and writes its
progress to a status file. It is a windowed program with no console output, so Manager starts it detached, then reads
that file on every step. The exe needs ~8 s to unpack before it writes anything; a missing file then means "starting"."""
import json,os,subprocess,time
from pathlib import Path

OUTPUT='Video Parallax'
STATUS_NAME='parallax_status.json'
START_GRACE=15        # a launched exe that is gone with no status file after this long has failed
RES={'9:16':'1080x1920','1:1':'1080x1080','4:3':'1440x1080','3:4':'1080x1440'}
MOTIONS=('random','right','left','up','down','zoomin','zoomout','dolly')
DETACHED=0x00000008|0x00000200|0x08000000  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

def candidates():
 env=os.environ.get('AI_MANAGER_PARALLAX_EXE')
 home=Path(os.environ.get('USERPROFILE') or Path.home())
 return [Path(p) for p in (env,home/'Desktop'/'Parallax25D.exe',home/'Projects'/'VIDEO_IMAGE_STUDIO'/'parallax-tool'/'dist'/'Parallax25D.exe') if p]

def find_exe():
 """The newest Parallax25D.exe found (an older Desktop copy may predate the command-line mode)."""
 found=[p for p in candidates() if p.is_file()]
 return max(found,key=lambda p:p.stat().st_mtime) if found else None

def resolution(ratio):return RES.get(str(ratio or ''),'1920x1080')

def scenes_ready(src):
 """How many scene folders hold layer PNGs (folders starting with _ or . are skipped, as the exe does)."""
 src=Path(src)
 if not src.is_dir():return 0
 n=0
 for root,dirs,files in os.walk(src):
  dirs[:]=[d for d in dirs if not d.startswith(('_','.'))]
  if any(f.lower().endswith('.png') and f[:3] in ('00_','01_','02_','03_') for f in files):n+=1
 return n

def alive(pid):
 try:
  import psutil
  return psutil.pid_exists(int(pid)) and psutil.Process(int(pid)).status()!=psutil.STATUS_ZOMBIE
 except Exception:return False

def read_status(path):
 try:return json.loads(Path(path).read_text(encoding='utf-8'))
 except (OSError,ValueError):return None

def start(project,ratio='16:9',motion='random',rerun=False,exe=None,popen=subprocess.Popen,clock=time.time):
 """Launch the exe for the whole project. Returns the job record kept in the step journal."""
 exe=exe or find_exe()
 if not exe:raise FileNotFoundError('Không thấy Parallax25D.exe (Desktop hoặc VIDEO_IMAGE_STUDIO\\parallax-tool\\dist). Chép bản mới ra Desktop.')
 project=Path(project);src=project/'Tach anh';dst=project/OUTPUT;dst.mkdir(parents=True,exist_ok=True)
 status=project/'.vis'/STATUS_NAME;status.parent.mkdir(parents=True,exist_ok=True)
 try:status.unlink()
 except FileNotFoundError:pass
 args=[str(exe),'--cli',str(src),str(dst),'--status',str(status),'--res',resolution(ratio),'--motion',motion if motion in MOTIONS else 'random']
 if rerun:args.append('--rerun')
 proc=popen(args,cwd=str(Path(exe).parent),creationflags=DETACHED,close_fds=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 return {'pid':proc.pid,'at':clock(),'status':str(status),'exe':str(exe)}

def check(job,clock=time.time,is_alive=alive):
 """('running', info) / ('done', info) / ('error', message) for a launched job."""
 now=clock();info=read_status(job['status'])
 # A status file from an earlier run (written before this launch) does not count.
 if info and float(info.get('started_at') or 0)<float(job['at'])-5:info=None
 running=is_alive(job['pid'])
 if not info:
  if running or now-float(job['at'])<START_GRACE:return 'running',{'state':'starting','percent':0}
  return 'error','Parallax25D đã tắt mà không báo tiến độ (bản cũ chưa có chế độ dòng lệnh? Chép bản mới ra Desktop).'
 state=info.get('state')
 if state=='done':return 'done',info
 if state=='error':return 'error',str(info.get('error') or 'Parallax25D báo lỗi')[:300]
 # Read again before calling it a crash: the exe may have written "done" and exited in between.
 if not running:
  last=read_status(job['status']) or info
  if last.get('state')=='done':return 'done',last
  return 'error','Parallax25D đã tắt giữa chừng (%s/%s video).'%(last.get('done',0),last.get('total','?'))
 return 'running',info
