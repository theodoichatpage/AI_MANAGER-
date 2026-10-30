"""Manager-side supervisor; network polling never runs on the dashboard render path."""
import json,os,secrets,socket,subprocess,sys,threading,time,urllib.request,urllib.error
from pathlib import Path
from .watchdog import ChildJob
from .build_identity import identity

class AgentClient:
 def __init__(self,home):
  self.home=Path(home);self.home.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self.process=None;self.job=None
  self.token=secrets.token_urlsafe(32);self.port=None;self.user_stopped=False;self.closing=threading.Event();self.restarts=[]
  self.cache={'online':False,'windows':sys.platform=='win32','error':None,'tasks':[],'logs':[]};self.thread=None
 def request(self,path,data=None,timeout=3):
  if not self.port:raise RuntimeError('Windows Agent chưa sẵn sàng')
  req=urllib.request.Request('http://127.0.0.1:%d%s'%(self.port,path),None if data is None else json.dumps(data).encode(),{'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
  except urllib.error.HTTPError as e:raise ValueError(json.load(e).get('error','Agent API lỗi')) from e
 def start_supervisor(self):
  if self.thread:return
  self.thread=threading.Thread(target=self.supervise,daemon=True);self.thread.start()
 def spawn(self):
  if sys.platform!='win32':raise RuntimeError('Agent điều khiển máy tính chỉ chạy trên Windows')
  with socket.socket() as s:s.bind(('127.0.0.1',0));self.port=s.getsockname()[1]
  settings={}
  try:settings=json.loads((self.home/'settings.json').read_text(encoding='utf8'))
  except (OSError,ValueError):pass
  env=dict(os.environ,AI_MANAGER_AGENT_HOME=str(self.home),AI_MANAGER_AGENT_TOKEN=self.token,AI_MANAGER_AGENT_PORT=str(self.port),AI_MANAGER_PARENT_PID=str(os.getpid()),AI_MANAGER_AGENT_SETTINGS=json.dumps(settings))
  self.job=ChildJob()
  with (self.home/'startup.log').open('ab') as log:
   self.process=subprocess.Popen([sys.executable,'-m','automation_agent.agent_server'],cwd=str(Path(__file__).resolve().parent.parent),env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  try:self.job.add(self.process.pid)
  except Exception:
   self.process.terminate();self.process.wait(3);self.job.close();self.job=None
   raise RuntimeError('Không tạo được Windows Job Object; Agent dừng để tránh action chạy ngoài kiểm soát')
 def supervise(self):
  if sys.platform!='win32':
   self.cache.update(error='Chỉ hỗ trợ điều khiển trên Windows; bản Linux không tạo kết quả giả');return
  failures=0
  while not self.closing.is_set():
   try:
    if self.user_stopped:
     self.cache.update(online=False,error='Agent đã dừng theo yêu cầu');self.closing.wait(.5);continue
    if not self.process or self.process.poll() is not None:
     now=time.time();self.restarts=[t for t in self.restarts if now-t<60]
     if len(self.restarts)>=3:self.cache.update(online=False,error='Agent lỗi 3 lần trong 60 giây. Bấm Khởi động Agent để thử lại.');self.user_stopped=True;continue
     self.restarts.append(now)
     if self.job:self.job.close()
     self.spawn();self.closing.wait(.5)
    # A busy Agent (sending lane work) may answer slowly; only a really silent one is restarted.
    state=self.request('/state',timeout=3)
    expected=identity();actual=state.get('agent_identity') or {}
    if actual.get('version')!=expected['version'] or actual.get('source_sha256')!=expected['source_sha256'] or actual.get('source_root')!=expected['source_root']:
     raise RuntimeError('Agent khác phiên bản/source Manager; đã chặn kết nối và sẽ khởi động lại Agent.')
    with self.lock:self.cache=state
    failures=0
   except Exception as e:
    failures+=1
    with self.lock:self.cache.update(online=False,error=str(e))
    if failures>=5 and self.process and self.process.poll() is None:
     if self.job:self.job.close();self.job=None
     self.process.terminate();self.process.wait(3);failures=0
   self.closing.wait(1)
 def snapshot(self):
  with self.lock:return dict(self.cache)
 def stop(self,terminate=False):
  if terminate:self.user_stopped=True
  try:self.request('/stop',{},timeout=5)
  except Exception:
   # If STOP cannot reach the agent, kill the entire Windows job, including input workers.
   self.user_stopped=True
   if self.job:self.job.close();self.job=None
   if self.process and self.process.poll() is None:self.process.terminate();self.process.wait(3)
   if not terminate:raise RuntimeError('Không liên lạc được Agent; đã chặn và dừng tiến trình để bảo đảm STOP')
  if terminate:
   if self.job:self.job.close();self.job=None
   if self.process and self.process.poll() is None:self.process.terminate();self.process.wait(3)
   with self.lock:self.cache.update(online=False,error='Agent đã dừng theo yêu cầu')
 def restart(self):
  self.user_stopped=False;self.restarts=[]
 def close(self):
  self.closing.set();self.stop(terminate=True)
  if self.thread:self.thread.join(3)
