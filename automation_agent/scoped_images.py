"""Scoped per-scene state machine; bounded known-error retry; unknown POST never replayed."""
from pathlib import Path
import hashlib,json
from PIL import Image
from .studio_images import rows,record_path
from .studio_images import save_image
from .project_files import layout,image_place
from .studio_lanes import backup_image
from .work_config import in_scope,validate_extent
from .studio_workflow import atomic,StudioReviewRequired

def step(w,s):
 cfg=w.c['work_config'];tasks=cfg['tasks'];allrows=rows(s);lookup=dict(allrows);now=w.clock()
 if not allrows:raise ValueError('Chưa có scene để xử lý')
 if 'image_plan' not in w.j:
  plan={}
  for kind in ('images','retry_images','sync'):
   if kind not in tasks:continue
   scope=cfg['scopes'][kind];validate_extent(scope,len(allrows))
   for index,(key,scene) in enumerate(allrows,1):
    if not in_scope(index,scope):continue
    complete=scene.get('imageStatus')=='complete' and bool(scene.get('imageResults'))
    if (kind=='retry_images' or scope['mode']=='errors') and scene.get('imageStatus')!='error':continue
    if scope['mode']=='missing' and complete:continue
    row=plan.setdefault(key,{'key':key,'ordinal':index,'generate':False,'save':False,'prompt_hash':hashlib.sha256(str(scene.get('prompt','')).encode()).hexdigest()})
    row['save' if kind=='sync' else 'generate']=True
  # When generating plus syncing, verify/save each generated scene before sending the next.
  if 'sync' in tasks:
   for row in plan.values():
    if row['generate']:row['save']=True
  w.j['image_plan']=list(plan.values());w.save()
  for unit in w.j['image_plan']:w.ledger.update('images',unit['key'],'READY',scene=unit['ordinal'])
 epoch=w.c.get('studio_retry_epoch',0)
 if epoch>w.j.get('scope_retry_epoch',0):
  for unit in w.j['image_plan']:
   if w.ledger.get('images',unit['key']).get('status')=='ERROR':w.ledger.update('images',unit['key'],'READY',retry_count=0,error=None)
  w.j['scope_retry_epoch']=epoch;w.save()
 plan=w.j['image_plan']
 if not plan:w.ledger.update('images','scope','SKIPPED',reason='Không có mục trong phạm vi cần xử lý')
 units=w.ledger.data['tasks'].get('images',{}).get('subtasks',{})
 counts={'studio_total_parts':len(s.get('parts',[])),'studio_completed_parts':sum(p.get('status')=='complete' for p in s.get('parts',[])),'studio_total_scenes':len(allrows),'studio_scope_total':len(plan),'studio_images_generated':sum(v.get('imageStatus')=='complete' for _,v in allrows),'studio_images_saved':sum(bool(v.get('result_path')) and v.get('status')=='COMPLETED' for v in units.values()),'studio_images_failed':sum(v.get('status')=='ERROR' for v in units.values()),'studio_stage':'Ảnh / Đồng bộ / Lưu theo phạm vi'}
 def report():atomic(w.folder/'analysis'/'studio_image_progress.json',counts)
 def pending(unit,status,**values):
  row=w.ledger.update('images',unit['key'],status,scene=unit['ordinal'],**values);report()
  return w.wait('image-unit:'+unit['key']+':'+str(row.get('retry_count',0)),1800,dict(counts,studio_current_scene=unit['key'],work_status=status,operation_id=row['operation_id'],work_retry_count=row.get('retry_count',0)))
 for unit in plan:
  key=unit['key'];scene=lookup.get(key)
  if scene and hashlib.sha256(str(scene.get('prompt','')).encode()).hexdigest()!=unit.get('prompt_hash'):raise StudioReviewRequired('Prompt scene thay đổi sau checkpoint; cần rà soát workflow mới')
  if scene is None:raise StudioReviewRequired('Scene trong checkpoint không còn tồn tại; không suy đoán scene thay thế')
  old=w.ledger.get('images',key);state=old.get('status')
  if state=='ERROR':continue
  if state in ('COMPLETED','SKIPPED'):
   # A missing local output must be reconciled, not silently trusted.
   if unit['save']:
    try:
     path=Path(old.get('result_path',''));rec=record_path(path.parent,key,True);rec=rec if rec.exists() else record_path(path.parent,key);record=json.loads(rec.read_text());assert record['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
     with Image.open(path) as image:image.verify()
     assert scene.get('imageStatus')=='complete' and scene.get('imageResults')
    except (OSError,ValueError,KeyError,AssertionError):w.ledger.update('images',key,'ERROR',error='Studio/file/checksum không khớp checkpoint; cần đối soát');counts['studio_images_failed']+=1
   continue
  commands=[v for k,v in w.j['commands'].items() if k.startswith('scoped-image:'+key+':') and k.endswith('#'+str(epoch))]
  if any(v.get('state')=='intent' for v in commands):raise StudioReviewRequired('POST ảnh chưa rõ kết quả; không resend')
  latest=commands[-1] if commands else None
  complete=scene.get('imageStatus')=='complete' and bool(scene.get('imageResults'))
  rerun=cfg['rerun'] and unit['generate']
  if rerun and latest:complete=complete and any(r.get('jobId')==latest.get('job_id') for r in scene.get('imageResults',[]))
  if old.get('retry_at',0)>now:return pending(unit,'RETRYING',retry_at=old['retry_at'],retry_count=old.get('retry_count',0))
  if complete and (not rerun or latest):
   if unit['save']:
    lay=layout(s)
    w.ledger.update('images',key,'SYNCING',scene=unit['ordinal'])
    try:
     if rerun:backup_image(image_place(w.folder,lay,key)[0],key,w.c['studio_run_id'])
     folder,name=image_place(w.folder,lay,key)
     path=save_image(folder,w.sid,key,scene['imageResults'][0],unit['ordinal'],name=name,project=w.folder)
    except Exception as exc:
     retry=old.get('retry_count',0)
     if retry<cfg['retry_limit']:
      return pending(unit,'RETRYING',retry_count=retry+1,retry_at=now+min(5*2**retry,30),error='Lưu ảnh: '+type(exc).__name__)
     w.ledger.update('images',key,'ERROR',error='Không xác minh/lưu được ảnh: '+type(exc).__name__);counts['studio_images_failed']+=1
     if cfg['error_policy']=='stop':raise RuntimeError('Dừng dự án do lưu ảnh lỗi')
     continue
    w.ledger.update('images',key,'COMPLETED',result_path=path,error=None);counts['studio_images_saved']+=1
   else:w.ledger.update('images',key,'COMPLETED' if latest else 'SKIPPED',reason='Studio đã xác nhận có ảnh')
   report();return w.wait('saved:'+key,120,dict(counts,studio_current_scene=key))
  if not unit['generate']:
   w.ledger.update('images',key,'ERROR',error='Studio chưa có ảnh; chỉ chọn Lưu nên không tạo mới');counts['studio_images_failed']+=1
   if cfg['error_policy']=='stop':raise RuntimeError('Không có ảnh để lưu')
   continue
  job=s.get('activeJob')
  if job:
   if not latest or job.get('id')!=latest.get('job_id') or job.get('sceneKey')!=key:raise StudioReviewRequired('Có tác vụ ngoài subtask hiện tại; không gửi trùng')
   return pending(unit,'WAITING_RESULT')
  if s.get('imageJobs'):raise StudioReviewRequired('Studio có hàng đợi ảnh khác')
  retry=old.get('retry_count',0)
  if old.get('retry_at',0)>now:return pending(unit,'RETRYING',retry_at=old['retry_at'],retry_count=retry)
  if latest:
   # Retry only an explicitly failed server job, never merely quiet/no response.
   if scene.get('imageStatus')!='error' or (s.get('lastJob') or {}).get('id')!=latest.get('job_id'):return pending(unit,'WAITING_RESULT')
   if len(commands)>=cfg['retry_limit']+1:
    w.ledger.update('images',key,'ERROR',error=str(scene.get('imageError') or 'Hết lượt retry'));counts['studio_images_failed']+=1
    if cfg['error_policy']=='stop':raise RuntimeError('Scene lỗi; chính sách dừng dự án')
    continue
   if state!='RETRYING':return pending(unit,'RETRYING',retry_count=retry+1,retry_at=now+min(5*2**retry,30))
  if not scene.get('prompt'):raise ValueError('Scene chưa có prompt; chạy Phân cảnh trước')
  if not str(s.get('stylePrompt') or '').strip():return w.wait('style',600,dict(counts,studio_message='Đang chờ tab Studio gửi prompt phong cách ảnh chung. Nếu ô phong cách trống, nhập trong tab Tạo ảnh của Studio.'))
  if rerun and not latest:atomic(w.folder/'analysis'/'backups'/(w.c['studio_run_id']+'_'+str(unit['ordinal'])+'.json'),scene)
  w.send('scoped-image:'+key+':attempt:'+str(retry),'/images',{'sceneKeys':[key],'stylePrompt':s['stylePrompt'],'ratio':w.c.get('studio_ratio','16:9'),'expectedWorkEpoch':s.get('workEpoch',0)},s)
  return pending(unit,'WAITING_RESULT',retry_count=retry,error=None)
 report()
 if counts['studio_images_failed']:raise RuntimeError(str(counts['studio_images_failed'])+' subtask ảnh cần xử lý; đã giữ kết quả các scene thành công')
 return {'context':dict(counts,studio_stage='Hoàn tất công việc ảnh đã chọn',work_status='COMPLETED',studio_waiting_action=None,result_path=str(w.ledger.path))}
