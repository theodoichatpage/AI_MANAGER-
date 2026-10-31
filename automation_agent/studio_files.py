"""STUDIO_FILES: keep Studio pictures in the project folder and separate them into layers, without a browser.

- "Tải ảnh về máy" (task 'sync'):  <project>/Anh/Phan N - .../Canh M - ....png
- "Tách ảnh"       (task 'separate'): <project>/Tach anh/Phan N - .../Canh M - .../ (layers from the Local Engine)
Pictures come straight from Studio's storage. When they are not downloaded, separation reads them in memory only.
The Local Engine handles one picture at a time, so this step sends one, polls it, saves its layers, then the next."""
import io,json,re,shutil,time,uuid,zipfile,urllib.error,urllib.request
from pathlib import Path
from .studio_images import rows,fetch_image
from .project_files import layout,image_place,separation_dir,save_scene_image,plain,SEPARATED
from .work_config import in_scope,validate_extent

ENGINE='http://127.0.0.1:17841'
JOB_LIMIT=1800        # one picture may take this long in the Local Engine
ROUND_SECONDS=20      # downloads per round stop after this, so STOP stays responsive
MAX_ZIP=200_000_000
MIME={b'\x89PNG':'image/png',b'\xff\xd8\xff':'image/jpeg',b'RIFF':'image/webp'}

class EngineDown(Exception):pass
class EngineBusy(Exception):pass

def _call(method,path,data=None,headers=None,timeout=30,limit=MAX_ZIP):
 req=urllib.request.Request(ENGINE+path,data=data,method=method,headers=headers or {})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:
   body=r.read(limit+1)
   if len(body)>limit:raise ValueError('Kết quả từ Local Engine quá lớn')
   return body
 except urllib.error.HTTPError as exc:
  text=exc.read(4000).decode('utf8','replace')
  try:message=json.loads(text).get('error') or text
  except ValueError:message=text
  if exc.code==409 and '/separate' in path:raise EngineBusy(message) from exc
  raise RuntimeError('Local Engine %d: %s'%(exc.code,message)) from exc
 except (urllib.error.URLError,ConnectionError,TimeoutError,OSError) as exc:
  raise EngineDown('Local Engine chưa chạy') from exc

class Engine:
 """Small client for the Local Engine's HTTP API (the same one the Tách ảnh tab uses)."""
 def health(self):return json.loads(_call('GET','/v1/health',timeout=5))
 def start(self,data,filename,project,layers):
  mime=next((v for k,v in MIME.items() if data.startswith(k)),None)
  if not mime:raise ValueError('Ảnh không phải PNG/JPG/WebP')
  boundary=uuid.uuid4().hex;parts=[]
  for name,value in (('fill','1'),('mode','parallax'),('layers',str(layers)),('project',project)):
   parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'%(boundary,name,value)).encode('utf8'))
  safe=re.sub(r'["\r\n]','_',filename)
  parts.append(('--%s\r\nContent-Disposition: form-data; name="image"; filename="%s"\r\nContent-Type: %s\r\n\r\n'%(boundary,safe,mime)).encode('utf8')+data+b'\r\n')
  parts.append(('--%s--\r\n'%boundary).encode())
  body=_call('POST','/v1/separate',b''.join(parts),{'Content-Type':'multipart/form-data; boundary='+boundary},timeout=60)
  return json.loads(body)['jobId']
 def status(self,job):
  try:return json.loads(_call('GET','/v1/jobs/'+job,timeout=15))
  except RuntimeError as exc:
   if ' 404:' in str(exc):return {'status':'lost'}
   raise
 def layers_zip(self,job):return _call('GET','/v1/jobs/'+job+'/zip',timeout=120)

def unpack_layers(data,dest,backups):
 """Write the engine's ZIP into dest (via a temp folder, then rename). An existing folder goes to backups."""
 files={}
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  for info in z.infolist():
   if info.is_dir():continue
   name=info.filename
   if name.startswith('/') or '\\' in name or any(p in ('','.','..') for p in name.split('/')) or not re.fullmatch(r'[A-Za-z0-9_./-]+',name):raise ValueError('Tên tệp lạ trong kết quả tách: '+name)
   if len(files)>=40 or info.file_size>100_000_000:raise ValueError('Kết quả tách quá lớn')
   files[name]=z.read(info)
 if 'vi_tri.json' not in files:raise ValueError('Kết quả tách thiếu vi_tri.json')
 dest=Path(dest);tmp=dest.parent/('.tmp-'+dest.name[:40]+'-'+uuid.uuid4().hex[:6])
 for name,content in files.items():
  path=tmp/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
 if dest.exists():
  Path(backups).mkdir(parents=True,exist_ok=True);shutil.move(str(dest),str(Path(backups)/(dest.name+'-'+time.strftime('%Y%m%d-%H%M%S'))))
 tmp.rename(dest)
 return str(dest)

def step(w,s,engine=None,fetch=fetch_image):
 engine=engine or Engine()
 cfg=w.c['work_config'];tasks=cfg['tasks'];limit=int(cfg.get('retry_limit',2))+1;now=w.clock()
 allrows=rows(s);lay=layout(s);st=w.j.setdefault('files',{'saved':{},'sep':{},'job':None})
 def scope(kind):
  if kind not in tasks:return []
  sc=cfg['scopes'].get(kind,{'mode':'all'});validate_extent(sc,len(allrows))
  return [(i,k,scene) for i,(k,scene) in enumerate(allrows,1) if in_scope(i,sc)]
 has=lambda scene:scene.get('imageStatus')=='complete' and bool(scene.get('imageResults'))
 saves=scope('sync');seps=scope('separate');run=w.c.get('studio_run_id') or 'run'
 ledger=lambda kind,key,state,**v:w.ledger.update(kind,key,state,**v) if w.ledger else None
 # 1. Downloads (a few per round).
 began=time.monotonic()
 for i,k,scene in saves:
  if st['saved'].get(k):continue
  if not has(scene):st['saved'][k]='no-image';ledger('images',k,'SKIPPED',reason='Studio chưa có ảnh cho cảnh này',scene=i);continue
  if time.monotonic()-began>ROUND_SECONDS:break
  try:st['saved'][k]=save_scene_image(w.folder,w.sid,lay,k,scene['imageResults'][0],i,fetch=fetch);ledger('images',k,'COMPLETED',result_path=st['saved'][k],scene=i)
  except Exception as exc:
   tries=st.setdefault('save_tries',{});tries[k]=tries.get(k,0)+1
   if tries[k]>=limit:st['saved'][k]='error';ledger('images',k,'ERROR',error='Không tải được ảnh: '+str(exc)[:200],scene=i)
  w.save()
 # 2. Separation, one picture at a time.
 sep=st['sep'];job=st.get('job');message=None
 def fail(k,i,error):
  row=sep.setdefault(k,{});row.update(state='error',error=str(error)[:300],tries=row.get('tries',0)+1)
  if row['tries']<limit:row['state']='retry'
  else:ledger('separate',k,'ERROR',error=row['error'],scene=i)
 if job:
  k=job['key'];i=job['ordinal']
  try:
   info=engine.status(job['id'])
   if info.get('status')=='complete':
    dest=separation_dir(w.folder,lay,k)
    path=unpack_layers(engine.layers_zip(job['id']),dest,w.folder/SEPARATED/'_backups'/re.sub(r'[^A-Za-z0-9_-]','_',run)[:64])
    sep[k]={'state':'done','path':path};st['job']=None;ledger('separate',k,'COMPLETED',result_path=path,scene=i)
   elif info.get('status') in ('error','lost'):
    fail(k,i,info.get('error') or info.get('message') or 'Local Engine mất tác vụ (có thể đã khởi động lại)');st['job']=None
   elif now-float(job['at'])>JOB_LIMIT:
    fail(k,i,'Quá %d phút chưa tách xong'%(JOB_LIMIT//60));st['job']=None
   else:message='Đang tách %s: %s'%(lay[k][1],info.get('message') or str(info.get('progress') or 0)+'%')
  except EngineDown:message='Local Engine chưa chạy. Mở Local Engine (cửa sổ start_engine) để tách tiếp; Manager đang chờ.'
  w.save()
 if not st.get('job') and not message:
  todo=[(i,k,scene) for i,k,scene in seps if (sep.get(k) or {}).get('state') not in ('done','error','no-image')]
  for i,k,scene in todo:
   dest=separation_dir(w.folder,lay,k)
   if not cfg.get('rerun') and (dest/'vi_tri.json').exists():
    sep[k]={'state':'done','path':str(dest),'existing':True};ledger('separate',k,'SKIPPED',reason='Đã tách trước đó',result_path=str(dest),scene=i);continue
   if not has(scene):sep[k]={'state':'no-image'};ledger('separate',k,'SKIPPED',reason='Studio chưa có ảnh',scene=i);continue
   try:
    saved=st['saved'].get(k)
    data=Path(saved).read_bytes() if saved and Path(saved).is_file() else fetch(scene['imageResults'][0]['url'])
    part,name=lay[k]
    project=(plain(w.c.get('project_name') or 'du_an',40)+' - '+part)[:80]
    jid=engine.start(data,name+'.png',project,4 if cfg.get('separate_layers')==4 else 3)
    st['job']={'key':k,'ordinal':i,'id':jid,'at':now};sep.setdefault(k,{})['state']='running'
    ledger('separate',k,'WAITING_RESULT',scene=i);message='Đã gửi %s sang Local Engine'%name
   except EngineBusy:message='Local Engine đang tách một ảnh khác (có thể từ tab Tách ảnh). Manager chờ rồi gửi tiếp.'
   except EngineDown:message='Local Engine chưa chạy. Mở Local Engine (cửa sổ start_engine) để tách tiếp; Manager đang chờ.'
   except Exception as exc:fail(k,i,exc);continue
   break
  w.save()
 # 3. Report.
 saved_ok=sum(1 for _,k,_ in saves if st['saved'].get(k) not in (None,'error','no-image'))
 sep_done=sum(1 for _,k,_ in seps if (sep.get(k) or {}).get('state')=='done')
 failed=[lay[k][1] for _,k,_ in saves if st['saved'].get(k)=='error']+[lay[k][1] for _,k,_ in seps if (sep.get(k) or {}).get('state')=='error']
 ctx={'studio_stage':'Tải ảnh / Tách ảnh','studio_files_total':len(saves),'studio_files_saved':saved_ok,'studio_separate_total':len(seps),'studio_separated':sep_done,
      'studio_files_failed':failed or None,'studio_message':message,'studio_folder_images':str(w.folder/'Anh') if saves else None,'studio_folder_separated':str(w.folder/SEPARATED) if seps else None}
 downloads_left=any(not st['saved'].get(k) for _,k,_ in saves)
 seps_left=any((sep.get(k) or {}).get('state') not in ('done','error','no-image') for _,k,_ in seps)
 if not downloads_left and not seps_left and not st.get('job'):
  if failed and cfg.get('error_policy')=='stop':raise RuntimeError('Dừng: %d mục lỗi (%s)'%(len(failed),', '.join(failed[:5])))
  return {'context':dict(ctx,studio_stage='Hoàn tất tải ảnh / tách ảnh'+(' · %d mục lỗi'%len(failed) if failed else ''),studio_waiting_action=None)}
 # Watchdog keyed on progress: every saved picture or separated scene restarts the clock.
 return w.wait('files:%d:%d'%(saved_ok,sep_done),JOB_LIMIT+600,ctx)
