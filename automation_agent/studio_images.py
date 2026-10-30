"""One-scene image orchestration through existing Studio endpoints and file verification."""
import hashlib,io,json,urllib.request,urllib.parse
from pathlib import Path
from PIL import Image

def rows(session):
 return [(str(part['id'])+':'+str(i),scene) for part in session.get('parts',[]) for i,scene in enumerate(part.get('scenes') or [])]

def fetch_image(url):
 p=urllib.parse.urlparse(url)
 if p.scheme!='https' or p.hostname!='wtxgjsorpqjanxoevxuw.supabase.co' or not p.path.startswith('/storage/v1/object/') or p.username or p.password:raise ValueError('Ảnh không thuộc kho Studio; đã chặn tải')
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):raise ValueError('Kho ảnh chuyển hướng ngoài yêu cầu; dừng tải')
 with urllib.request.build_opener(NoRedirect).open(url,timeout=10) as response:data=response.read(8_388_609)
 if len(data)>8_388_608:raise ValueError('Tệp ảnh quá lớn')
 return data

def save_image(folder,sid,key,result,ordinal=0,fetch=fetch_image):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 record=folder/(hashlib.sha256(key.encode()).hexdigest()+'.json')
 try:
  old=json.loads(record.read_text());path=folder/old['file']
  if path.parent==folder and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==old['sha256']:
   with Image.open(path) as image:image.verify()
   return str(path)
 except (OSError,ValueError,KeyError):pass
 data=fetch(result['url'])
 with Image.open(io.BytesIO(data)) as image:
  fmt=image.format
  if image.width*image.height>40_000_000:raise ValueError('Ảnh vượt giới hạn kích thước giải mã')
  image.verify()
 with Image.open(io.BytesIO(data)) as image:image.load()
 ext={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}.get(fmt)
 if not ext:raise ValueError('Định dạng ảnh không hỗ trợ')
 filename=sid[:8]+'_Scene_'+str(ordinal).zfill(4)+'_'+hashlib.sha256(key.encode()).hexdigest()[:24]+ext;path=folder/filename
 if path.exists() and path.read_bytes()!=data:raise RuntimeError('Ảnh đã có nhưng khác nội dung; không ghi đè')
 from .studio_workflow import atomic
 tmp=path.with_suffix('.download');tmp.write_bytes(data);tmp.replace(path)
 atomic(record,{'scene_key':key,'file':filename,'sha256':hashlib.sha256(data).hexdigest()})
 return str(path)

def step(worker,session):
 if worker.c.get('work_config'):
  from .scoped_images import step as scoped
  return scoped(worker,session)
 if any(p.get('status')!='complete' for p in session.get('parts',[])):raise ValueError('Phân cảnh chưa hoàn tất. Chọn công đoạn 2 trước khi chạy ảnh.')
 scenes=rows(session)
 if not scenes:raise ValueError('Chưa có scene; chọn Phân tích/Phân cảnh trước')
 missing=[key for key,s in scenes if not s.get('prompt')]
 if missing:raise ValueError('Scene thiếu prompt; chưa gửi lệnh ảnh')
 counts={'studio_total_parts':len(session.get('parts',[])),'studio_completed_parts':sum(p.get('status')=='complete' for p in session.get('parts',[])),'studio_images_generated':sum(s.get('imageStatus')=='complete' for _,s in scenes),'studio_images_saved':0,'studio_images_failed':sum(s.get('imageStatus')=='error' for _,s in scenes),'studio_total_scenes':len(scenes),'studio_stage':'Tạo ảnh / Đồng bộ / Lưu ảnh'}
 def report():
  from .studio_workflow import atomic
  atomic(worker.folder/'analysis'/'studio_image_progress.json',counts)
 for ordinal,(key,scene) in enumerate(scenes,1):
  if scene.get('imageStatus')=='complete' and scene.get('imageResults'):
   save_image(worker.folder/'images',worker.sid,key,scene['imageResults'][0],ordinal);counts['studio_images_saved']+=1
   # One download per worker cycle keeps STOP/timeout responsive.
   record_key='saved:'+key
   if not worker.j.get(record_key):worker.j[record_key]=True;worker.save();report();return worker.wait('save:'+key,120,counts)
 report()
 if counts['studio_images_saved']==len(scenes):return {'context':dict(counts,studio_stage='Hoàn tất ảnh đã lưu',studio_waiting_action=None)}
 key,scene=next((k,s) for k,s in scenes if not(s.get('imageStatus')=='complete' and s.get('imageResults')))
 job=session.get('activeJob');pending=session.get('imageJobs') or []
 if job:
  receipt=worker.receipt('image:'+key,job)
  if job.get('type')!='image_generation' or job.get('sceneKey')!=key or not receipt:raise RuntimeError('Studio có tác vụ khác; không gửi trùng ảnh')
 elif pending:raise RuntimeError('Studio có hàng đợi ảnh ngoài Manager; chờ hoàn tất trước')
 else:
  if scene.get('imageStatus') in ('error','stopped') and not worker.c.get('studio_retry_epoch'):raise RuntimeError('Scene ảnh lỗi/đã dừng; dùng Chạy lại lỗi sau khi kiểm tra Studio')
  style=str(session.get('stylePrompt') or '').strip()
  # The run's Studio tab saves the style kept in its browser into the project; wait for it (10 minutes).
  if not style:return worker.wait('style',600,dict(counts,studio_message='Đang chờ tab Studio gửi prompt phong cách ảnh chung. Nếu ô phong cách trống, nhập trong tab Tạo ảnh của Studio.'))
  worker.send('image:'+key,'/images',{'sceneKeys':[key],'stylePrompt':style,'ratio':worker.c.get('studio_ratio','16:9'),'expectedWorkEpoch':session.get('workEpoch',0)},session)
 return worker.wait('image:'+key,1800,dict(counts,studio_current_scene=key))
