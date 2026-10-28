"""Single-project Studio orchestration using its existing API. No prompt rewriting."""
import hashlib,json,os,re,time,urllib.parse,urllib.request,uuid
from pathlib import Path
from . import window_manager as wm
API='https://wtxgjsorpqjanxoevxuw.supabase.co/functions/v1/studio-api'
ID=re.compile(r'[A-Za-z0-9-]{16,64}')

class StudioReviewRequired(RuntimeError):pass

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
 with tmp.open('w',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
 tmp.replace(path)

class StudioAPI:
 def request(self,sid,route='',body=None):
  if not ID.fullmatch(sid):raise ValueError('Studio project ID không hợp lệ')
  url=API+'?'+urllib.parse.urlencode({'path':'sessions/'+sid+route})
  req=urllib.request.Request(url,None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json'},method='GET' if body is None else 'POST')
  with urllib.request.urlopen(req,timeout=10) as r:raw=r.read(5_000_001)
  if len(raw)>5_000_000:raise ValueError('Studio response quá lớn')
  data=json.loads(raw);session=data.get('session')
  if not isinstance(session,dict) or session.get('id')!=sid:raise RuntimeError('Studio trả sai project ID; đã chặn')
  return session

def validate_url(url):
 p=urllib.parse.urlparse(url)
 if p.scheme!='https' or p.path not in ('','/') or p.username or p.password or p.port not in (None,443) or not re.fullmatch(r'video-image-studio(?:-[a-z0-9-]+)?\.vercel\.app',p.hostname or ''):raise ValueError('Chọn URL Studio Vercel HTTPS hợp lệ')
 return p._replace(query='',fragment='').geturl().rstrip('/')+'/'

def workflow(sid,url,browser,profile,folder,script,context=None):
 if not ID.fullmatch(sid):raise ValueError('Studio ID không hợp lệ')
 if browser not in ('chrome','edge'):raise ValueError('Chọn Chrome hoặc Edge')
 base=validate_url(url);nonce=uuid.uuid4().hex
 target=dict(context or {},target_app=browser,browser=browser,browser_profile=profile,studio_project_id=sid,studio_run_id=nonce,studio_origin=base.rstrip('/'),studio_folder=str(folder),studio_script=script)
 launch=base+'?'+urllib.parse.urlencode({'managerProject':sid,'managerRun':nonce})
 def a(name,**kw):return dict(action=name,target_app=browser,**({'browser_profile':profile} if browser=='edge' else {}),**kw)
 actions=[a('OPEN_APP',timeout=25),a('WAIT_WINDOW',timeout=20),a('FOCUS_WINDOW'),a('OPEN_URL',url=launch),a('WAIT_PAGE',url=launch,timeout=30),a('STUDIO_READY'),a('STUDIO_ANALYZE'),a('STUDIO_SCENES')]
 return actions,target

class StudioStep:
 def __init__(self,context,api=None,presence=None,clock=time.time):
  self.c=context;self.api=api or StudioAPI();self.clock=clock;self.sid=context['studio_project_id'];self.folder=Path(context['studio_folder']);self.presence=presence or self.read_presence
  self.path=self.folder/'analysis'/('manager_'+context['studio_run_id']+'.json')
  try:self.j=json.loads(self.path.read_text(encoding='utf8'))
  except FileNotFoundError:self.j={'session_id':self.sid,'commands':{},'stages':{}}
  if self.j.get('session_id')!=self.sid:raise StudioReviewRequired('Checkpoint Studio ID không khớp')
 def save(self):atomic(self.path,self.j)
 def read_presence(self):
  query=urllib.parse.urlencode({'sessionId':self.sid,'runId':self.c['studio_run_id']})
  with urllib.request.urlopen('http://127.0.0.1:8765/api/studio-presence?'+query,timeout=3) as r:return json.load(r)
 def ready(self):
  p=self.presence()
  return p.get('studio_tab_open') and p.get('chat_connected') and p.get('session_id')==self.sid and p.get('manager_run_id')==self.c['studio_run_id'] and p.get('origin')==self.c['studio_origin']
 def wait(self,name,limit,context=None):
  start=self.j['stages'].setdefault(name,self.clock());self.save()
  if self.clock()-start>limit:raise TimeoutError('Studio quá thời gian tại '+name+'; giữ checkpoint, không gửi lại prompt tự động')
  return {'waiting':True,'context':dict(context or {},studio_waiting_action=name)}
 def command_key(self,key):return key+'#'+str(self.c.get('studio_retry_epoch',0))
 def receipt(self,key,job):
  return next((v for k,v in self.j['commands'].items() if k.startswith(key+'#') and v.get('job_id')==job.get('id')), {})
 def send(self,key,route,body,session):
  key=self.command_key(key)
  command=self.j['commands'].get(key)
  if command:
   # An uncertain POST is never automatically replayed.
   if command.get('state')=='intent':raise StudioReviewRequired('Lệnh Studio có kết quả chưa rõ sau gián đoạn. Kiểm tra Studio trước khi chạy lại; không gửi trùng.')
   return session
  self.j['commands'][key]={'state':'intent','at':self.clock(),'script_hash':hashlib.sha256(str(body.get('script','')).encode()).hexdigest()};self.save()
  try:result=self.api.request(self.sid,route,body)
  except Exception as exc:raise StudioReviewRequired('Chưa xác nhận Studio đã nhận lệnh. Đã giữ intent và chặn gửi lại để tránh trùng.') from exc
  self.j['commands'][key].update(state='accepted',job_id=(result.get('activeJob') or {}).get('id'));self.save();return result
 def step(self,name):
  if name=='STUDIO_READY':
   if not self.ready():return self.wait(name,120)
   s=self.api.request(self.sid)
   if s.get('activeJob'):raise StudioReviewRequired('Studio đang có tác vụ trước khi Manager bắt đầu. Chờ hoàn tất rồi thử lại.')
   return {'context':{'studio_ready':True,'studio_script_hash':hashlib.sha256(str(s.get('script','')).encode()).hexdigest()}}
  if not self.ready():return self.wait('connection',120)
  self.j['stages'].pop('connection',None)
  s=self.api.request(self.sid);parts=s.get('parts') or [];job=s.get('activeJob')
  actual={'studio_total_parts':len(parts),'studio_completed_parts':sum(p.get('status')=='complete' for p in parts),'studio_total_scenes':sum(len(p.get('scenes') or []) for p in parts),'studio_current_part':job.get('partId') if job else None}
  if name=='STUDIO_ANALYZE':
   if parts:
    atomic(self.folder/'analysis'/'studio_structure.json',{'project_id':self.sid,'parts':parts,'updated_at':self.clock()})
    return {'context':dict(actual,studio_stage='Phân cảnh',studio_waiting_action=None)}
   if job:
    receipt=self.receipt('structure',job)
    if job.get('id')!=receipt.get('job_id'):raise StudioReviewRequired('Tác vụ Studio không thuộc lệnh Manager đã xác nhận')
   else:
    if s.get('status')=='error' and not self.c.get('studio_retry_epoch'):raise RuntimeError('Studio lỗi: '+str(s.get('lastError') or 'Phân tích thất bại'))
    script=str(s.get('script') or self.c.get('studio_script') or '').strip()
    if not script:raise ValueError('Dự án chưa có kịch bản')
    s=self.send('structure','/analysis',{'script':script,'confirmReset':False,'expectedWorkEpoch':s.get('workEpoch',0)},s)
   return self.wait(name,1800,dict(actual,studio_stage='Phân tích cấu trúc'))
  if name!='STUDIO_SCENES':raise ValueError('Studio action không hợp lệ')
  if not parts:raise RuntimeError('Studio chưa có phần để phân cảnh')
  # Save only real successful outputs, one file per immutable part ID.
  for p in parts:
   if p.get('status')=='complete':
    part_id=str(p['id'])
    if not re.fullmatch(r'[A-Za-z0-9-]+',part_id):raise ValueError('Part ID không an toàn')
    atomic(self.folder/'scenes'/(part_id+'.json'),p)
  atomic(self.folder/'analysis'/'studio_progress.json',dict(actual,project_id=self.sid,updated_at=self.clock()))
  if all(p.get('status')=='complete' for p in parts):return {'context':dict(actual,studio_stage='Hoàn tất phân cảnh',studio_waiting_action=None)}
  part=next(p for p in parts if p.get('status')!='complete');key='part:'+str(part['id'])
  if job:
   receipt=self.receipt(key,job)
   if job.get('type')!='part_analysis' or job.get('partId')!=part['id'] or job.get('id')!=receipt.get('job_id'):raise StudioReviewRequired('Studio có tác vụ khác; không điều khiển nhầm')
  else:
   if part.get('status') in ('error','stopped') and not self.c.get('studio_retry_epoch'):raise RuntimeError('Phần '+str(part.get('title'))+' lỗi/đã dừng. Giữ các phần đã hoàn tất.')
   self.send(key,'/parts/'+urllib.parse.quote(str(part['id']),safe='')+'/analysis',{'expectedWorkEpoch':s.get('workEpoch',0)},s)
  return self.wait(key,1800,dict(actual,studio_stage='Phân cảnh',studio_current_part=part['id']))
