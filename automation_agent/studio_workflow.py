"""Single-project Studio orchestration using its existing API. No prompt rewriting."""
import hashlib,json,os,re,time,urllib.parse,urllib.request,uuid
from pathlib import Path
from . import window_manager as wm
API='https://wtxgjsorpqjanxoevxuw.supabase.co/functions/v1/studio-api'
ID=re.compile(r'[A-Za-z0-9-]{16,64}')

class StudioReviewRequired(RuntimeError):pass
class StudioScriptMissing(ValueError):pass
SCRIPT_WAIT=600

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
 with tmp.open('w',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
 tmp.replace(path)

class StudioAPI:
 def create(self,sid):
  """Create an empty Studio project on the server (AI MANAGER "Dự án mới"); an existing one is returned as is."""
  if not ID.fullmatch(sid):raise ValueError('Studio project ID không hợp lệ')
  req=urllib.request.Request(API+'?path=sessions',json.dumps({'id':sid}).encode(),{'Content-Type':'application/json'},method='POST')
  with urllib.request.urlopen(req,timeout=10) as r:session=json.loads(r.read(5_000_001)).get('session')
  if not isinstance(session,dict) or session.get('id')!=sid:raise RuntimeError('Studio không tạo được dự án')
  return session
 def request(self,sid,route='',body=None):
  if not ID.fullmatch(sid):raise ValueError('Studio project ID không hợp lệ')
  from . import studio_cache
  # Plain reads go through the version-stamp cache; commands always reach the server.
  if body is None and not route:session=studio_cache.session(sid)
  else:
   data=studio_cache.call('sessions/'+sid+route,body);session=data.get('session')
   if route.startswith('/lanes/'):
    if isinstance(session,dict):studio_cache.remember(session)
    return data
   studio_cache.remember(session)
  if not isinstance(session,dict) or session.get('id')!=sid:raise RuntimeError('Studio trả sai project ID; đã chặn')
  return session

def validate_url(url):
 p=urllib.parse.urlparse(url)
 if p.scheme!='https' or p.path not in ('','/') or p.username or p.password or p.port not in (None,443) or not re.fullmatch(r'video-image-studio(?:-[a-z0-9-]+)?\.vercel\.app',p.hostname or ''):raise ValueError('Chọn URL Studio Vercel HTTPS hợp lệ')
 return p._replace(query='',fragment='').geturl().rstrip('/')+'/'

def workflow(sid,url,browser,profile,folder,script,context=None,stages=None,work_config=None,name=None):
 if not ID.fullmatch(sid):raise ValueError('Studio ID không hợp lệ')
 if browser not in ('chrome','edge'):raise ValueError('Chọn Chrome hoặc Edge')
 if work_config is not None:
  from .work_config import normalize
  work_config=normalize(work_config)
  stages=(['analysis'] if any(k in work_config['tasks'] for k in ('analysis','scenes')) else [])+(['images'] if any(k in work_config['tasks'] for k in ('images','retry_images','sync')) else [])
 stages=['analysis'] if stages is None else stages
 if not isinstance(stages,list) or not stages or any(x not in ('analysis','images') for x in stages):raise ValueError('Chọn Phân tích/Phân cảnh hoặc Tạo ảnh; transcript chưa hỗ trợ')
 base=validate_url(url);nonce=uuid.uuid4().hex
 target=dict(context or {},target_app=browser,browser=browser,browser_profile=profile,studio_project_id=sid,studio_run_id=nonce,studio_origin=base.rstrip('/'),studio_folder=str(folder),studio_script=script,studio_stages=stages,work_config=work_config)
 lanes=(work_config or {}).get('lanes') or []
 if lanes and (lanes[0]['browser'],lanes[0]['profile'])!=(browser,profile if browser=='edge' else 'Default'):raise ValueError('Tab ChatGPT thứ nhất phải là trình duyệt/hồ sơ chính của dự án')
 youtube=bool((context or {}).get('studio_youtube_url'))
 # managerName lets a profile that does not list this project yet (new project, extra lane) open it by ID.
 launch=base+'?'+urllib.parse.urlencode({'managerProject':sid,'managerRun':nonce,'managerStage':'transcript' if youtube and 'analysis' in stages else 'analysis' if 'analysis' in stages else 'images',**({'managerName':name} if name else {}),**({'managerLaneId':__import__('re').sub(r'[^A-Za-z0-9_-]','_',browser+'_'+(profile if browser=='edge' else 'Default'))} if lanes else {})})
 def a(name,**kw):return dict(action=name,target_app=browser,**({'browser_profile':profile} if browser=='edge' else {}),**kw)
 if browser=='edge':
  # Open Studio by launching Edge with the profile and URL (no typing into an address bar, which can land in
  # another window when several profiles are open). The Studio tab itself then proves who it is (presence).
  target.update(studio_launch=True,studio_launch_url=launch)
  actions=[a('STUDIO_OPEN',timeout=60),a('STUDIO_READY')]
 else:
  actions=[a('OPEN_APP',timeout=25),a('WAIT_WINDOW',timeout=20),a('FOCUS_WINDOW'),a('NEW_TAB'),a('OPEN_URL',url=launch),a('WAIT_PAGE',url=launch,timeout=30),a('STUDIO_READY')]
 if len(lanes)>1:actions.append(a('STUDIO_LANES',timeout=90))
 if 'analysis' in stages:
  if not work_config or 'analysis' in work_config['tasks']:actions+=[a('STUDIO_TRANSCRIPT'),a('STUDIO_ANALYZE')]
 parallel=len(lanes)>1 and any(k in work_config['tasks'] for k in ('scenes','images'))
 if parallel:actions.append(a('STUDIO_PARALLEL'))
 else:
  if 'analysis' in stages and (not work_config or 'scenes' in work_config['tasks']):actions.append(a('STUDIO_SCENES'))
  if 'images' in stages:actions.append(a('STUDIO_IMAGES'))
 return actions,target

class StudioStep:
 def __init__(self,context,api=None,presence=None,clock=time.time):
  self.c=context;self.api=api or StudioAPI();self.clock=clock;self.sid=context['studio_project_id'];self.folder=Path(context['studio_folder']);self.presence=presence or self.read_presence
  self.path=self.folder/'analysis'/('manager_'+context['studio_run_id']+'.json')
  try:self.j=json.loads(self.path.read_text(encoding='utf8'))
  except FileNotFoundError:self.j={'session_id':self.sid,'commands':{},'stages':{}}
  from .work_ledger import WorkLedger
  self.ledger=WorkLedger(self.folder,context) if context.get('work_config') else None
  if self.j.get('session_id')!=self.sid:raise StudioReviewRequired('Checkpoint Studio ID không khớp')
 def save(self):atomic(self.path,self.j)
 def read_presence(self):
  query=urllib.parse.urlencode({'sessionId':self.sid,'runId':self.c['studio_run_id']})
  with urllib.request.urlopen('http://127.0.0.1:8765/api/studio-presence?'+query,timeout=3) as r:return json.load(r)
 def ready(self):
  p=self.presence();self.c['studio_state']='connected' if p.get('studio_tab_open') else 'disconnected';self.c['chatgpt_state']='connected' if p.get('chat_connected') else 'disconnected'
  return p.get('studio_tab_open') and p.get('chat_connected') and p.get('session_id')==self.sid and p.get('manager_run_id')==self.c['studio_run_id'] and p.get('origin')==self.c['studio_origin']
 def wait(self,name,limit,context=None):
  # A retry epoch gets a fresh watchdog; an old attempt's start time must not time out the new one.
  start=self.j['stages'].setdefault(self.stage_key(name),self.clock());self.save()
  # Time spent paused/stopped before a reconciled resume does not count against the watchdog.
  start=max(start,float(self.c.get('studio_resumed_at') or 0))
  if self.clock()-start>limit and self.ledger and name in ('connection','STUDIO_READY'):raise StudioReviewRequired('Mất Studio/ChatGPT quá thời gian. Tạm dừng và đối soát khi Resume.')
  if self.clock()-start>limit:
   why={'WAITING_CHATGPT':' — Studio đã mở nhưng ChatGPT/Extension chưa kết nối','WAITING_STUDIO':' — chưa thấy tab Studio của lượt chạy này'}.get(self.c.get('studio_ready_wait'),'')
   raise TimeoutError('Studio quá thời gian tại '+name+why+'; giữ checkpoint, không gửi lại prompt tự động')
  values=dict(context or {},studio_waiting_action=name)
  if self.ledger:
   values.update(workflow_id=self.c['studio_run_id'],last_successful_task=self.ledger.data.get('last_successful_task'),last_successful_subtask=self.ledger.data.get('last_successful_subtask'),task_id=self.ledger.data.get('current_task'),subtask_id=self.ledger.data.get('current_subtask'),work_status=self.ledger.data.get('status'),studio_state=self.c.get('studio_state'),chatgpt_state=self.c.get('chatgpt_state'),result_path=str(self.ledger.path))
  return {'waiting':True,'context':values}
 def command_key(self,key):return key+'#'+str(self.c.get('studio_retry_epoch',0))
 def stage_key(self,name):return self.command_key(name) if self.c.get('studio_retry_epoch') else name
 def observe(self,job,actual,stage,ledger_key=None):
  """A job the user started in Studio: watch it read-only until it ends. Never sent, adopted or replayed by Manager."""
  seen=self.j.setdefault('external_jobs',{})
  if job['id'] not in seen:seen[job['id']]={'type':job.get('type'),'part':job.get('partId'),'first_seen':self.clock()};self.save()
  message='Tác vụ do người dùng chạy trong Studio; Manager chỉ theo dõi, không gửi lệnh.'
  if self.ledger and ledger_key and self.ledger.get(*ledger_key).get('status') not in ('COMPLETED','SKIPPED'):self.ledger.update(*ledger_key,'WAITING_RESULT',reason=message,external_job=job['id'])
  return self.wait('external:'+str(job['id']),1800,dict(actual,studio_stage=stage,studio_external_job=job['id'],studio_message=message,studio_error_code=None))
 def script_wait(self,name,s,actual,facts):
  """No script on the Studio server yet: re-read every poll and wait (bounded) instead of failing on a stale read."""
  from .studio_reconcile import validate,SCRIPT_MISSING,SCRIPT_NOT_SYNCED
  draft=facts['script_draft_character_count']
  code=SCRIPT_NOT_SYNCED if draft else SCRIPT_MISSING
  if draft and facts.get('script_sync')=='unconfirmed':message='Studio có kịch bản nhập tay ('+str(draft)+' ký tự) chưa xác nhận thuộc dự án này. Kiểm tra kịch bản trong Studio rồi bấm "Lưu kịch bản này cho AI MANAGER".'
  elif draft:message='Studio có kịch bản nhập tay ('+str(draft)+' ký tự); đang chờ Studio lưu lên máy chủ.'
  else:message=validate(facts,'STUDIO_ANALYZE')[1]
  if self.ledger:self.ledger.update('analysis','structure','WAITING_STUDIO',error_code=code,reason=message)
  key=self.command_key('script');start=self.j['stages'].setdefault(key,self.clock());self.save()
  if self.clock()-start>SCRIPT_WAIT:raise StudioScriptMissing(SCRIPT_MISSING+': '+message)
  return {'waiting':True,'context':dict(actual,studio_waiting_action=name,studio_stage='Chờ kịch bản',studio_error_code=code,studio_message=message,studio_reconcile=facts)}
 def script_checkpoint(self,script):
  """SAVE -> VERIFY -> CHECKPOINT the exact script Studio holds before analysis is requested."""
  digest=hashlib.sha256(script.encode('utf8')).hexdigest()
  if (self.j.get('script') or {}).get('sha256')==digest:return
  path=self.folder/'analysis'/'studio_script.txt';path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
  with tmp.open('w',encoding='utf8',newline='') as f:f.write(script);f.flush();os.fsync(f.fileno())
  tmp.replace(path)
  if hashlib.sha256(path.read_text(encoding='utf8').encode('utf8')).hexdigest()!=digest:raise StudioReviewRequired('Lưu kịch bản không khớp checksum; dừng để kiểm tra')
  self.j['script']={'sha256':digest,'characters':len(script),'path':str(path),'at':self.clock()};self.j['stages'].pop(self.command_key('script'),None);self.save()
  if self.ledger:self.ledger.update('analysis','script','COMPLETED',result_path=str(path),characters=len(script))
 def transcript_pipeline(self,name,actual,facts,pipeline,s=None):
  """Ask the Studio tab to get the YouTube transcript (and rewrite it in the saved style), then watch its progress."""
  cmd=self.j.get('transcript_command')
  if not cmd or cmd.get('epoch')!=self.c.get('studio_retry_epoch',0):
   cmd={'type':'transcript_pipeline','id':self.c['studio_run_id'][:20]+'-'+str(self.c.get('studio_retry_epoch',0)),'url':self.c['studio_youtube_url'],'language':self.c.get('studio_language','vi'),'rewrite':bool(self.c.get('studio_rewrite',True)),'epoch':self.c.get('studio_retry_epoch',0)}
   if self.c.get('studio_rewrite_style'):cmd['style']=self.c['studio_rewrite_style']
   # Several ChatGPT tabs: Studio uploads the sections and Manager hands them out to the tabs.
   if len((self.c.get('work_config') or {}).get('lanes') or [])>1:cmd['parallel']=True
   self.j['transcript_command']=cmd;self.save()
  self.post_command({k:v for k,v in cmd.items() if k!='epoch'})
  mine=pipeline.get('id')==cmd['id']
  if mine and pipeline.get('stage')=='error':raise RuntimeError('Lấy transcript/viết lại lỗi: '+str(pipeline.get('error') or 'không rõ')+'. Sửa trong tab Get Transcript của Studio rồi bấm Chạy lại lỗi.')
  labels={'fetch':'Đang lấy transcript YouTube','partition':'Đang chia phần để viết lại','rewrite':'Đang viết lại kịch bản','done':'Đang lưu kịch bản'}
  stage=labels.get(pipeline.get('stage'),'Đã gửi yêu cầu lấy transcript cho Studio') if mine else 'Đã gửi yêu cầu lấy transcript cho Studio'
  if mine and pipeline.get('stage')=='rewrite':stage+=' '+str(pipeline.get('done',0))+'/'+str(pipeline.get('total',0))
  extra={}
  if mine and cmd.get('parallel') and s and (s.get('rewrite') or {}).get('sections'):
   from .studio_lanes import rewrite_round
   extra=rewrite_round(self,s);stage='Đang viết lại song song '+str(extra['studio_rewrite_done'])+'/'+str(extra['studio_rewrite_total'])+' trên '+str(extra['studio_lanes_live'])+' tab'
  if self.ledger:self.ledger.update('transcript','transcript','WAITING_RESULT',reason=stage)
  # Watchdog follows progress: each rewritten part restarts the clock.
  key='transcript:'+(str(pipeline.get('stage'))+':'+str(pipeline.get('done',0)) if mine else 'sent')
  if extra.get('studio_rewrite_total'):key='transcript:parallel:'+str(extra['studio_rewrite_done'])
  return self.wait(key,1200,dict(actual,studio_stage='Transcript',studio_message=stage,studio_reconcile=facts,**extra))
 def post_command(self,command):
  body=json.dumps({'sessionId':self.sid,'runId':self.c['studio_run_id'],'command':command}).encode()
  try:urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765/api/studio-command',body,{'Content-Type':'application/json'},method='POST'),timeout=3).read()
  except OSError:pass
 def receipt(self,key,job):
  return next((v for k,v in self.j['commands'].items() if k.startswith(key+'#') and v.get('job_id')==job.get('id')), {})
 def send(self,key,route,body,session):
  key=self.command_key(key)
  command=self.j['commands'].get(key)
  if command:
   # An uncertain POST is never automatically replayed.
   if command.get('state')=='intent':raise StudioReviewRequired('Lệnh Studio có kết quả chưa rõ sau gián đoạn. Kiểm tra Studio trước khi chạy lại; không gửi trùng.')
   return session
  if self.ledger:
   row=self.ledger.update('scenes' if route.startswith('/parts/') else 'images' if route=='/images' else 'analysis',key.rsplit('#',1)[0] if not key.startswith('scoped-image:') else key[len('scoped-image:'):].split(':attempt:')[0],'WAITING_RESULT')
   body=dict(body,operation_id=row['operation_id'],project_id=self.c.get('manager_project_id'),task_id=self.ledger.data['current_task'],subtask_id=key)
  self.j['commands'][key]={'state':'intent','at':self.clock(),'script_hash':hashlib.sha256(str(body.get('script','')).encode()).hexdigest()};self.save()
  try:result=self.api.request(self.sid,route,body)
  except Exception as exc:raise StudioReviewRequired('Chưa xác nhận Studio đã nhận lệnh. Đã giữ intent và chặn gửi lại để tránh trùng.') from exc
  self.j['commands'][key].update(state='accepted',job_id=(result.get('activeJob') or {}).get('id'));self.save();return result
 def open_studio(self,force=False):
  """Launch Edge with this profile and the run's Studio URL; again at most every 2 minutes while not seen."""
  key='open#'+str(self.c.get('studio_retry_epoch',0));last=float(self.j.get('studio_open',{}).get(key) or 0)
  if not force and self.clock()-last<120:return False
  from .studio_lanes import open_lane
  open_lane({'browser':'edge','profile':self.c.get('browser_profile') or 'Default'},self.c['studio_launch_url'])
  self.j.setdefault('studio_open',{})[key]=self.clock();self.save();return True
 def step(self,name):
  if name=='STUDIO_OPEN':
   if not self.ready():self.open_studio(force=not (self.j.get('studio_open') or {}).get('open#'+str(self.c.get('studio_retry_epoch',0))))
   return {'context':{'studio_stage':'Mở Studio'}}
  if name=='STUDIO_READY':
   if not self.ready():
    if self.c.get('studio_launch'):self.open_studio()
    self.c['studio_ready_wait']='WAITING_CHATGPT' if self.c.get('studio_state')=='connected' else 'WAITING_STUDIO'
    if self.ledger:self.ledger.update('connection','studio',self.c['studio_ready_wait'])
    return self.wait(name,300 if self.c.get('studio_launch') else 120,{'studio_stage':'Chờ ChatGPT/Extension' if self.c['studio_ready_wait']=='WAITING_CHATGPT' else 'Chờ tab Studio'})
   s=self.api.request(self.sid)
   job=s.get('activeJob')
   # A job the user started by hand is observed by the next step; an unknown kind still needs review.
   if job and job.get('type') not in ('script_structure','part_analysis','image_generation'):raise StudioReviewRequired('Studio đang có tác vụ không rõ loại trước khi Manager bắt đầu. Chờ hoàn tất rồi thử lại.')
   return {'context':{'studio_external_job':(job or {}).get('id'),'studio_ready':True,'studio_script_hash':hashlib.sha256(str(s.get('script','')).encode()).hexdigest()}}
  if not self.ready():
   # Nothing is sent while disconnected. While a Studio job is still running (ChatGPT tab reloading or
   # briefly hung), keep waiting for it like the job itself; otherwise give up after 120 s as before.
   try:running=bool(self.api.request(self.sid).get('activeJob'))
   except Exception:running=False
   return self.wait('connection',1800 if running else 120)
  self.j['stages'].pop(self.stage_key('connection'),None)
  if name=='STUDIO_LANES':
   from .studio_lanes import open_step
   return open_step(self)
  s=self.api.request(self.sid);parts=s.get('parts') or [];job=s.get('activeJob')
  if name=='STUDIO_PARALLEL':
   if job and job.get('type')!='image_generation':return self.observe(job,{},'Studio đang chạy tác vụ do người dùng bấm')
   from .studio_lanes import step as parallel
   return parallel(self,s)
  actual={'studio_total_parts':len(parts),'studio_completed_parts':sum(p.get('status')=='complete' for p in parts),'studio_total_scenes':sum(len(p.get('scenes') or []) for p in parts),'studio_current_part':job.get('partId') if job else None,'studio_message':None,'studio_external_job':None}
  if name=='STUDIO_TRANSCRIPT':
   # GET_TRANSCRIPT is decided by the real Studio state, never skipped by default.
   from .studio_reconcile import reconcile
   facts=reconcile(s,self.presence())
   pipeline=(self.presence().get('project_state') or {}).get('pipeline') or {}
   if self.c.get('studio_youtube_url') and not facts['analysis_completed'] and not facts['script_content_exists']:
    return self.transcript_pipeline(name,actual,facts,pipeline,s)
   if facts['analysis_completed']:state,reason='SKIPPED','Studio đã phân tích cấu trúc; không cần transcript'
   elif self.j.get('transcript_command') and pipeline.get('id')==self.j['transcript_command']['id'] and pipeline.get('stage')=='done':state,reason='COMPLETED','Đã lấy transcript'+(' và viết lại theo phong cách' if self.c.get('studio_rewrite',True) else '')+' ('+str(facts['script_character_count'])+' ký tự)'
   elif facts['transcript_exists']:state,reason='SKIPPED','Transcript đã có ('+str(facts['transcript_character_count'])+' ký tự); không lấy lại'
   elif facts['script_content_exists'] or str(self.c.get('studio_script') or '').strip():state,reason='SKIPPED','Kịch bản đã có ('+str(facts['script_character_count'] or len(str(self.c.get('studio_script')).strip()))+' ký tự); dùng kịch bản, không cần transcript'
   else:return self.script_wait(name,s,actual,facts)
   if self.ledger and not self.ledger.get('transcript','transcript').get('status') in ('COMPLETED','SKIPPED'):self.ledger.update('transcript','transcript',state,reason=reason)
   return {'context':dict(actual,studio_stage='Transcript',studio_transcript_state=reason,studio_error_code=None,studio_message=None,studio_reconcile=facts,studio_waiting_action=None)}
  if name=='STUDIO_ANALYZE':
   if parts:
    if self.ledger:self.ledger.update('analysis','structure','COMPLETED' if any(k.startswith('structure#') for k in self.j['commands']) else 'SKIPPED',reason='Studio đã có cấu trúc; không reset')
    atomic(self.folder/'analysis'/'studio_structure.json',{'project_id':self.sid,'parts':parts,'updated_at':self.clock()})
    return {'context':dict(actual,studio_stage='Phân cảnh',studio_waiting_action=None)}
   if job:
    receipt=self.receipt('structure',job)
    if job.get('id')!=receipt.get('job_id'):
     if job.get('type')!='script_structure':raise StudioReviewRequired('Tác vụ Studio không thuộc lệnh Manager đã xác nhận')
     return self.observe(job,actual,'Studio đang phân tích cấu trúc (người dùng chạy)',('analysis','structure'))
   else:
    if s.get('status')=='error' and not self.c.get('studio_retry_epoch'):raise RuntimeError('Studio lỗi: '+str(s.get('lastError') or 'Phân tích thất bại'))
    # Studio's server copy wins; the Manager project's own script is only a fallback.
    script=str(s.get('script') or self.c.get('studio_script') or '').strip()
    if not script:
     from .studio_reconcile import reconcile
     return self.script_wait(name,s,actual,reconcile(s,self.presence()))
    self.script_checkpoint(script)
    s=self.send('structure','/analysis',{'script':script,'confirmReset':False,'expectedWorkEpoch':s.get('workEpoch',0)},s)
   return self.wait(name,1800,dict(actual,studio_stage='Phân tích cấu trúc'))
  if name=='STUDIO_IMAGES':
   from .studio_images import step
   return step(self,s)
  if name!='STUDIO_SCENES':raise ValueError('Studio action không hợp lệ')
  cfg=self.c.get('work_config')
  if cfg:
   from .work_config import in_scope,validate_extent
   scope=cfg['scopes'].get('scenes',{'mode':'all'})
   if 'scene_plan' not in self.j:validate_extent(scope,len(parts))
   if 'scene_plan' not in self.j:self.j['scene_plan']=[p['id'] for i,p in enumerate(parts,1) if in_scope(i,scope)];self.save()
   by_id={p['id']:p for p in parts}
   if any(pid not in by_id for pid in self.j['scene_plan']):raise StudioReviewRequired('Phần đã chọn không còn tồn tại sau checkpoint')
   parts=[by_id[pid] for pid in self.j['scene_plan']]
  if not parts:raise RuntimeError('Không có phần trong phạm vi đã chọn')
  if self.ledger:
   for part in parts:
    if not self.ledger.get('scenes','part:'+str(part['id'])):self.ledger.update('scenes','part:'+str(part['id']),'READY',part=part['id'],part_number=next((i for i,p in enumerate(s.get('parts',[]),1) if p['id']==part['id']),None))
  # Save only real successful outputs, one file per immutable part ID.
  for p in parts:
   if p.get('status')=='complete':
    part_id=str(p['id'])
    filename=part_id if re.fullmatch(r'[A-Za-z0-9_-]{1,120}',part_id) else 'part_'+hashlib.sha256(part_id.encode('utf8')).hexdigest()
    atomic(self.folder/'scenes'/(filename+'.json'),p)
    if self.ledger:
     if not p.get('scenes'):raise ValueError('Studio báo complete nhưng chưa có scene hợp lệ')
     self.ledger.update('scenes','part:'+part_id,'COMPLETED' if any(v.get('job_id') for k,v in self.j['commands'].items() if k.startswith('part:'+part_id+'#')) else 'SKIPPED',result_path=str(self.folder/'scenes'/(filename+'.json')),part=part_id)
  atomic(self.folder/'analysis'/'studio_progress.json',dict(actual,project_id=self.sid,updated_at=self.clock()))
  if all(p.get('status')=='complete' for p in parts):return {'context':dict(actual,studio_stage='Hoàn tất phân cảnh',studio_waiting_action=None)}
  part=next(p for p in parts if p.get('status')!='complete');key='part:'+str(part['id'])
  if job:
   receipt=self.receipt(key,job)
   if job.get('id')!=receipt.get('job_id'):
    if job.get('type')!='part_analysis':raise StudioReviewRequired('Studio có tác vụ khác; không điều khiển nhầm')
    return self.observe(job,actual,'Studio đang phân cảnh phần do người dùng chạy',('scenes','part:'+str(job.get('partId'))) if job.get('partId') else None)
   if job.get('type')!='part_analysis' or job.get('partId')!=part['id']:raise StudioReviewRequired('Studio có tác vụ khác; không điều khiển nhầm')
  elif s.get('batchAnalysis') or s.get('analysisQueue'):
   # Studio's own "Phân cảnh toàn bộ" queue is between parts: wait, never interleave Manager commands.
   return self.wait('external:batch',1800,dict(actual,studio_stage='Studio đang phân cảnh toàn bộ (người dùng chạy)',studio_message='Hàng đợi phân cảnh của Studio đang chạy; Manager chỉ theo dõi.'))
  else:
   if part.get('status') in ('error','stopped') and not self.c.get('studio_retry_epoch'):
    if self.ledger:self.ledger.update('scenes','part:'+str(part['id']),'ERROR',error='Studio báo lỗi hoặc đã dừng')
    raise RuntimeError('Phần '+str(part.get('title'))+' lỗi/đã dừng. Giữ các phần đã hoàn tất.')
   self.send(key,'/parts/'+urllib.parse.quote(str(part['id']),safe='')+'/analysis',{'expectedWorkEpoch':s.get('workEpoch',0)},s)
  return self.wait(key,1800,dict(actual,studio_stage='Phân cảnh',studio_current_part=part['id']))
