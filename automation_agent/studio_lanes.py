"""Parallel ChatGPT lanes: AI MANAGER gives each lane (one browser profile with its own Studio tab and
ChatGPT tab) its own Studio job. Scenes go to free lanes part by part; with 3+ lanes the last lane makes
images as soon as a part has scenes; when scenes are done every lane makes images.

Safety: a lane command is idempotent on the Studio server (same lane + same target returns the same job),
so an uncertain POST may be re-sent to the SAME lane only. A job on a lost lane is released before it is
given to another lane, so no part or scene is ever sent twice at the same time."""
import re,subprocess,urllib.parse
from .studio_workflow import atomic,StudioReviewRequired
from .studio_images import rows,save_image

LANE_LOST=180        # a lane whose Studio tab stopped reporting this long loses its job
JOB_LIMIT=1800       # one part/image may take this long before it is taken back
LIMIT_COOLDOWN=900   # ChatGPT said "limit reached": rest this lane's images
OPEN_WAIT=180        # how long to wait for extra lanes to connect before working with fewer
RATE=re.compile(r'limit|giới hạn|too many|quá nhiều|try again later|thử lại sau|rate',re.I)
MIN_VERSION=(0,5,0)

def version_ok(text):
 try:return tuple(int(x) for x in str(text).split('.')[:3])>=MIN_VERSION
 except ValueError:return False

def live_lanes(workers):
 """Lanes able to take work: Studio tab reporting, ChatGPT connected, extension new enough. One row per lane."""
 out={}
 for w in sorted(workers or [],key=lambda x:(not x.get('dispatcher'),-float(x.get('seen') or 0))):
  if w.get('chat_connected') and version_ok(w.get('extension_version')) and w['lane_id'] not in out:out[w['lane_id']]=w
 return out

def warnings(workers):
 """Plain-language problems the user should know about; none of them stops the run."""
 notes=[];by_lane={}
 for w in workers or []:by_lane.setdefault(w['lane_id'],[]).append(w)
 for lane,tabs in by_lane.items():
  label=(tabs[0].get('account_label') or lane)
  if len(tabs)>1:notes.append('Trình duyệt của '+label+' đang mở '+str(len(tabs))+' tab Studio cùng dự án; chỉ 1 tab gửi lệnh. Muốn chạy song song, dùng hồ sơ trình duyệt khác.')
  if max(t.get('chat_tabs') or 0 for t in tabs)>1:notes.append('Trình duyệt của '+label+' có nhiều tab ChatGPT; Extension chỉ dùng 1 tab. Muốn thêm tab chạy song song, mở ChatGPT ở hồ sơ/trình duyệt khác.')
  if tabs[0].get('chat_connected') and not version_ok(tabs[0].get('extension_version')):notes.append('Trình duyệt của '+label+' cần Extension 0.5.0 trở lên để chạy song song.')
  plan=str(tabs[0].get('account_plan') or '').lower()
  if plan and plan not in ('plus','pro','team','business','enterprise'):notes.append('Tài khoản '+label+' là gói '+plan+': tạo ảnh có thể bị giới hạn.')
 keys={}
 for lane,tabs in by_lane.items():
  key=tabs[0].get('account_key')
  if key:keys.setdefault(key,[]).append(tabs[0].get('account_label') or lane)
 for labels in keys.values():
  if len(labels)>1:notes.append(str(len(labels))+' tab ChatGPT dùng chung tài khoản '+labels[0]+': phân cảnh nhanh hơn, nhưng tạo ảnh dùng chung một hạn mức.')
 return notes

def lane_url(base,sid,run,name):
 return base+'?'+urllib.parse.urlencode({'managerProject':sid,'managerRun':run,'managerStage':'analysis','managerLane':'1','managerName':name or 'Dự án AI MANAGER'})

def open_lane(lane,url,launch=None):
 """Open ChatGPT + this project's Studio tab in another browser profile. Never closes anything."""
 if launch:return launch(lane,url)
 from . import window_manager as wm
 exe=wm.executable(lane['browser'])
 subprocess.Popen([exe,'--profile-directory='+lane['profile'],'--new-window','https://chatgpt.com/',url],shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_BREAKAWAY_FROM_JOB',0))

def open_step(w,launch=None):
 """STUDIO_LANES: open every extra lane once, then wait (bounded) until they connect."""
 extra=(w.c.get('work_config') or {}).get('lanes',[])[1:]
 st=w.j.setdefault('lanes',{'items':{},'cooldown':{},'seen':{},'opened':{}})
 st.setdefault('opened',{})
 for lane in extra:
  key=lane['browser']+':'+lane['profile']
  if key not in st['opened']:
   open_lane(lane,lane_url(w.c['studio_origin']+'/',w.sid,w.c['studio_run_id'],w.c.get('project_name')),launch);st['opened'][key]=w.clock();w.save()
 pres=w.presence();workers=pres.get('workers') or []
 live=live_lanes(workers)
 notes=warnings(workers)
 ctx={'studio_stage':'Mở '+str(len(extra)+1)+' tab ChatGPT','studio_lanes_live':len(live),'studio_lanes_wanted':len(extra)+1,'studio_warnings':notes}
 if len(live)>=len(extra)+1:return {'context':dict(ctx,studio_waiting_action=None)}
 first=min(st['opened'].values()) if st['opened'] else w.clock()
 if w.clock()-first>=OPEN_WAIT:
  return {'context':dict(ctx,studio_waiting_action=None,studio_message='Chỉ '+str(len(live))+'/'+str(len(extra)+1)+' tab ChatGPT kết nối; chạy với số tab hiện có. Kiểm tra đăng nhập ChatGPT và Extension ở hồ sơ còn thiếu.')}
 return w.wait('lanes:open',OPEN_WAIT+120,dict(ctx,studio_message='Đang chờ ChatGPT ở các hồ sơ trình duyệt kết nối với dự án.'))

def scoped_parts(w,parts):
 cfg=w.c.get('work_config') or {}
 scope=(cfg.get('scopes') or {}).get('scenes',{'mode':'all'})
 from .work_config import in_scope,validate_extent
 if 'scene_plan' not in w.j:
  validate_extent(scope,len(parts))
  w.j['scene_plan']=[p['id'] for i,p in enumerate(parts,1) if in_scope(i,scope)];w.save()
 by_id={p['id']:p for p in parts}
 if any(pid not in by_id for pid in w.j['scene_plan']):raise StudioReviewRequired('Phần đã chọn không còn tồn tại sau checkpoint')
 return [by_id[pid] for pid in w.j['scene_plan']]

def image_scope(w,s):
 cfg=w.c.get('work_config') or {}
 if 'images' not in cfg.get('tasks',[]):return []
 from .work_config import in_scope
 scope=(cfg.get('scopes') or {}).get('images',{'mode':'all'})
 allowed={p['id'] for p in scoped_parts(w,s.get('parts') or [])}
 return [(i,key,scene) for i,(key,scene) in enumerate(rows(s),1) if key.rsplit(':',1)[0] in allowed and in_scope(i,scope)]

def save_part(w,part):
 pid=str(part['id']);name=pid if re.fullmatch(r'[A-Za-z0-9_-]{1,120}',pid) else 'part_'+__import__('hashlib').sha256(pid.encode()).hexdigest()
 path=w.folder/'scenes'/(name+'.json');atomic(path,part)
 if w.ledger:w.ledger.update('scenes','part:'+pid,'COMPLETED',result_path=str(path),part=pid)
 return str(path)

def step(w,s,post=None):
 """STUDIO_PARALLEL: one allocation round. Returns a wait (keep polling) or the finished context."""
 post=post or (lambda route,body:w.api.request(w.sid,route,body))
 cfg=w.c.get('work_config') or {};tasks=cfg.get('tasks',['analysis','scenes']);limit=int(cfg.get('retry_limit',2))+1
 now=w.clock();st=w.j.setdefault('lanes',{'items':{},'cooldown':{},'seen':{},'opened':{}})
 items=st['items'];pres=w.presence();workers=pres.get('workers') or [];live=live_lanes(workers)
 for lane in live:st['seen'][lane]=now
 parts=scoped_parts(w,s.get('parts') or []);lane_jobs=s.get('laneJobs') or [];busy={j.get('lane'):j for j in lane_jobs}
 attention=[]
 # 1. Results the server recorded per lane (errors, completions, releases).
 for lane,r in (s.get('laneLast') or {}).items():
  key=('part:'+str(r.get('partId'))) if r.get('type')=='part_analysis' else 'image:'+str(r.get('sceneKey'))
  item=items.get(key)
  if not item or item.get('job')!=r.get('jobId') or item.get('state')!='sent':continue
  item['state']=r.get('status');item['error']=r.get('error') or None
  if r.get('status')=='error' and r.get('type')=='image_generation' and RATE.search(str(r.get('error') or '')):
   st['cooldown'][lane]=now+LIMIT_COOLDOWN;attention.append('ChatGPT báo hết lượt/giới hạn ở '+((live.get(lane) or {}).get('account_label') or lane)+'; tab này nghỉ tạo ảnh 15 phút.')
 # 2. Take jobs back from lost or stuck lanes so another lane can do them.
 for job in lane_jobs:
  lane=job.get('lane');key=('part:'+str(job.get('partId'))) if job.get('type')=='part_analysis' else 'image:'+str(job.get('sceneKey'))
  item=items.get(key) or {}
  lost=lane not in live and now-float(st['seen'].get(lane) or item.get('at') or now)>=LANE_LOST
  stuck=item.get('job')==job.get('id') and now-float(item.get('at') or now)>=JOB_LIMIT
  if lost or stuck:
   post('/lanes/'+lane+'/release',{'jobId':job['id'],'reason':'Tab mất kết nối' if lost else 'Quá thời gian','expectedWorkEpoch':s.get('workEpoch',0)})
   if item.get('job')==job.get('id'):item.update(state='released',error='Tab ChatGPT mất kết nối' if lost else 'Quá thời gian chờ')
   busy.pop(lane,None)
 # 3. Keep real outputs: scene JSON per part, then one image download per round.
 saved=w.j.setdefault('lane_saved',{})
 for p in parts:
  if p.get('status')=='complete' and p.get('scenes') and saved.get('part:'+str(p['id']))!=len(p['scenes']):save_part(w,p);saved['part:'+str(p['id'])]=len(p['scenes'])
 images=image_scope(w,s) if 'images' in tasks else []
 for ordinal,key,scene in images:
  if scene.get('imageStatus')=='complete' and scene.get('imageResults') and not saved.get('image:'+key):
   path=save_image(w.folder/'images',w.sid,key,scene['imageResults'][0],ordinal);saved['image:'+key]=path
   if w.ledger:w.ledger.update('images',key,'COMPLETED',result_path=path,scene=ordinal)
   break
 w.save()
 # 4. What is left to do.
 def open_item(key):
  item=items.get(key) or {}
  return item.get('state')=='sent' and any(j.get('id')==item.get('job') for j in lane_jobs)
 failed=lambda key:(items.get(key) or {}).get('tries',0)>=limit and (items.get(key) or {}).get('state') in ('error','released')
 part_todo=[p for p in parts if p.get('status')!='complete' and not open_item('part:'+str(p['id'])) and not failed('part:'+str(p['id']))] if 'scenes' in tasks else []
 parts_left=[p for p in parts if p.get('status')!='complete' and not failed('part:'+str(p['id']))] if 'scenes' in tasks else []
 style=str(s.get('stylePrompt') or '').strip()
 image_todo=[(o,k) for o,k,sc in images if not (sc.get('imageStatus')=='complete' and sc.get('imageResults')) and sc.get('prompt') and not open_item('image:'+k) and not failed('image:'+k)]
 if image_todo and not style:attention.append('Studio chưa lưu prompt phong cách ảnh; chưa tạo ảnh. Lưu trong tab Tạo ảnh của Studio.');image_todo=[]
 # 5. Give work to free lanes, main lane first. With 3+ lanes the last one prefers images.
 order=list(live);image_lane=order[-1] if images and len(order)>=3 and parts_left else None
 sent=0
 for lane in order:
  if lane in busy or (live[lane].get('extension_job') and live[lane]['extension_job'] not in {j.get('id') for j in lane_jobs}):continue
  cool=float(st['cooldown'].get(lane) or 0)>now
  pick=None
  if lane==image_lane and image_todo and not cool:pick=('image',image_todo.pop(0))
  elif part_todo:pick=('part',part_todo.pop(0))
  elif image_todo and not cool:pick=('image',image_todo.pop(0))
  if not pick:continue
  if pick[0]=='part':
   part=pick[1];key='part:'+str(part['id']);route='/lanes/'+lane+'/parts/'+urllib.parse.quote(str(part['id']),safe='');body={'expectedWorkEpoch':s.get('workEpoch',0)}
  else:
   ordinal,skey=pick[1];key='image:'+skey;route='/lanes/'+lane+'/images';body={'sceneKey':skey,'stylePrompt':style,'ratio':w.c.get('studio_ratio','16:9'),'expectedWorkEpoch':s.get('workEpoch',0)}
  item=items.setdefault(key,{'tries':0})
  item.update(state='intent',lane=lane,at=now,tries=item.get('tries',0)+1);w.save()
  try:result=post(route,body)
  except Exception as exc:
   message=str(exc)
   # Refused (409/422): nothing was created. Count it as a failed try; another round decides again.
   item.update(state='error',error=message[:300]);w.save();continue
  command=(result or {}).get('command') or {}
  item.update(state='sent',job=command.get('id'),error=None);w.save();sent+=1
  if w.ledger:
   if pick[0]=='part':w.ledger.update('scenes',key,'WAITING_RESULT',lane=lane)
   else:w.ledger.update('images',pick[1][1],'WAITING_RESULT',lane=lane,scene=pick[1][0])
 # 6. Report and decide.
 lanes_view=[{'lane':lane,'label':live[lane].get('account_label') or lane,'plan':live[lane].get('account_plan'),'job':(busy.get(lane) or {}).get('partId') or (busy.get(lane) or {}).get('sceneKey'),'kind':(busy.get(lane) or {}).get('type'),'cooldown':float(st['cooldown'].get(lane) or 0)>now} for lane in order]
 done_parts=sum(p.get('status')=='complete' for p in parts);done_images=sum(1 for _,k,_ in images if saved.get('image:'+k))
 failed_items=[k for k in items if failed(k)]
 ctx={'studio_stage':'Chạy song song '+str(len(order))+' tab ChatGPT','studio_total_parts':len(parts),'studio_completed_parts':done_parts,
  'studio_total_scenes':sum(len(p.get('scenes') or []) for p in parts),'studio_scope_total':len(images),'studio_images_saved':done_images,
  'studio_images_generated':sum(1 for _,_,sc in images if sc.get('imageStatus')=='complete'),'studio_lanes':lanes_view,'studio_warnings':warnings(workers),
  'studio_attention':attention or None,'studio_failed_items':failed_items or None}
 atomic(w.folder/'analysis'/'studio_lanes.json',dict(ctx,items=items,updated_at=now))
 in_flight=any(open_item(k) for k in items)
 scenes_done='scenes' not in tasks or not parts_left
 images_done=not images or all(saved.get('image:'+k) or failed('image:'+k) for _,k,_ in images)
 if scenes_done and images_done and not in_flight:
  if failed_items and cfg.get('error_policy')=='stop':raise RuntimeError('Dừng: '+str(len(failed_items))+' mục lỗi sau '+str(limit)+' lần thử ('+', '.join(failed_items[:5])+')')
  return {'context':dict(ctx,studio_stage='Hoàn tất chạy song song'+(' · '+str(len(failed_items))+' mục lỗi' if failed_items else ''),studio_waiting_action=None)}
 if not live:
  ctx['studio_message']='Chưa có tab ChatGPT nào kết nối (cần Extension 0.5.0+). Manager chờ, không gửi lệnh.'
 if not live and not in_flight:return w.wait('lanes:connection',1800,ctx)
 # Watchdog keyed on progress: any finished part/image restarts the clock.
 return w.wait('lanes:'+str(done_parts)+':'+str(done_images),JOB_LIMIT+LANE_LOST+300,ctx)

def rewrite_round(w,s,post=None):
 """Get Transcript on several tabs: give each free lane the next rewrite section the Studio tab uploaded.
 Same safety as scenes: lost/stuck lanes are released first, a failed section is retried up to the limit."""
 post=post or (lambda route,body:w.api.request(w.sid,route,body))
 cfg=w.c.get('work_config') or {};limit=int(cfg.get('retry_limit',2))+1;now=w.clock()
 st=w.j.setdefault('lanes',{'items':{},'cooldown':{},'seen':{},'opened':{}});items=st['items']
 live=live_lanes(w.presence().get('workers') or [])
 for lane in live:st['seen'][lane]=now
 sections=(s.get('rewrite') or {}).get('sections') or [];lane_jobs=s.get('laneJobs') or [];busy={j.get('lane'):j for j in lane_jobs}
 for lane,r in (s.get('laneLast') or {}).items():
  if r.get('type')!='transcript_rewrite':continue
  item=items.get('rewrite:'+str(r.get('sectionId')))
  if item and item.get('job')==r.get('jobId') and item.get('state')=='sent':item.update(state=r.get('status'),error=r.get('error') or None)
 for job in lane_jobs:
  if job.get('type')!='transcript_rewrite':continue
  lane=job.get('lane');item=items.get('rewrite:'+str(job.get('sectionId'))) or {}
  lost=lane not in live and now-float(st['seen'].get(lane) or item.get('at') or now)>=LANE_LOST
  stuck=item.get('job')==job.get('id') and now-float(item.get('at') or now)>=JOB_LIMIT
  if lost or stuck:
   post('/lanes/'+lane+'/release',{'jobId':job['id'],'reason':'Tab mất kết nối' if lost else 'Quá thời gian','expectedWorkEpoch':s.get('workEpoch',0)})
   if item.get('job')==job.get('id'):item.update(state='released')
   busy.pop(lane,None)
 open_ids={j.get('sectionId') for j in lane_jobs if j.get('type')=='transcript_rewrite' and j.get('lane') in busy}
 failed=lambda sid:(items.get('rewrite:'+sid) or {}).get('tries',0)>=limit and (items.get('rewrite:'+sid) or {}).get('state') in ('error','released')
 todo=[x for x in sections if x.get('status')!='done' and x['id'] not in open_ids and not failed(x['id'])]
 for lane in live:
  if lane in busy or not todo:continue
  sec=todo.pop(0);key='rewrite:'+sec['id'];item=items.setdefault(key,{'tries':0})
  item.update(state='intent',lane=lane,at=now,tries=item.get('tries',0)+1);w.save()
  try:result=post('/lanes/'+lane+'/rewrite/'+urllib.parse.quote(sec['id'],safe=''),{'expectedWorkEpoch':s.get('workEpoch',0)})
  except Exception as exc:item.update(state='error',error=str(exc)[:300]);w.save();continue
  item.update(state='sent',job=((result or {}).get('command') or {}).get('id'),error=None);w.save()
 w.save()
 bad=[x['id'] for x in sections if failed(x['id'])]
 return {'studio_lanes_live':len(live),'studio_rewrite_done':sum(x.get('status')=='done' for x in sections),'studio_rewrite_total':len(sections),'studio_failed_items':bad or None,'studio_warnings':warnings(w.presence().get('workers') or [])}
