"""Even out the brightness/contrast of a project's pictures (ChatGPT drifts between light and dark from one image to the next).

Only the luminance (Y of YCbCr) is changed, so the colours, including the dark-red accent, keep their hue. Every picture is moved
toward one target look: the median mean/standard deviation of the project's own pictures, fixed once and kept in
<project>/.vis/tone.json so later pictures match the earlier ones. The untouched original goes to <project>/.vis/tone_backup/
(same relative path) before the first change; running again never stacks adjustments (a picture already near the target is left)."""
import hashlib,json,os,statistics,tempfile
from pathlib import Path

IMAGES=('.png','.jpg','.jpeg','.webp')
STATE='tone.json'
BACKUP='tone_backup'
SOURCE='Anh'
MIN_REF=8                # pictures needed before the target is fixed from the project itself
DEFAULT=(124.0,59.0)     # used until then: the median look measured on the first project
GAIN=(0.75,1.35)         # contrast change is limited so a flat picture is not blown up
STRENGTH=0.7            # how far each picture moves toward the target: the spread shrinks a lot but light/dark scenes stay a little different

def pictures(project):
 root=Path(project)/SOURCE
 if not root.is_dir():return []
 out=[]
 for dirpath,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if not d.startswith(('_','.'))]
  out+=[Path(dirpath)/f for f in sorted(files) if f.lower().endswith(IMAGES) and not f.startswith('.')]
 return out

def measure(path):
 """(mean, standard deviation) of the luminance, on a small copy."""
 from PIL import Image,ImageStat
 with Image.open(path) as im:y=im.convert('YCbCr').resize((256,144)).split()[0]
 stat=ImageStat.Stat(y);return stat.mean[0],stat.stddev[0]

def _state_path(project):return Path(project)/'.vis'/STATE
def load(project):
 try:return json.loads(_state_path(project).read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}
def save(project,data):
 p=_state_path(project);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')

def target(project,files=None):
 """The look every picture is moved to: fixed once from the project's own pictures, kept afterwards."""
 st=load(project)
 if st.get('target'):return tuple(st['target'])
 files=files if files is not None else pictures(project)
 if len(files)<MIN_REF:return DEFAULT
 step=max(1,len(files)//60);stats=[measure(f) for f in files[::step]]
 t=(round(statistics.median(m for m,_ in stats),1),round(statistics.median(s for _,s in stats),1))
 st['target']=list(t);save(project,st);return t

def reset(project):
 st=load(project);st.pop('target',None);save(project,st)

def _refresh_record(path):
 """The download step keeps a checksum next to each picture: keep it true after the change."""
 try:
  digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
  for rec in (Path(path).parent/'.vis').glob('*.json'):
   try:data=json.loads(rec.read_text(encoding='utf-8'))
   except (OSError,ValueError):continue
   if data.get('file')==Path(path).name:
    data.update(sha256=digest,tone=True);rec.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
 except OSError:pass

def adjust(project,path,goal):
 """'ok' when the picture already has the target look, 'adjusted' after moving it there."""
 from PIL import Image
 path=Path(path);tm,ts=goal;rel=str(path.relative_to(Path(project)/SOURCE)).replace(os.sep,'/')
 state=load(project);done=state.setdefault('done',{})
 # A picture already moved by this tool is left alone, so running again never stacks adjustments.
 if done.get(rel)==hashlib.sha256(path.read_bytes()).hexdigest():return 'ok'
 mean,std=measure(path)
 backup=Path(project)/'.vis'/BACKUP/path.relative_to(Path(project)/SOURCE)
 if not backup.exists():
  backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(path.read_bytes())
 gain=min(GAIN[1],max(GAIN[0],1+STRENGTH*(ts/max(std,1.0)-1)))
 centre=mean+STRENGTH*(tm-mean)
 lut=[min(255,max(0,round((v-mean)*gain+centre))) for v in range(256)]
 with Image.open(path) as im:
  im.load();fmt=im.format or 'PNG'
  y,cb,cr=im.convert('YCbCr').split()
  out=Image.merge('YCbCr',(y.point(lut),cb,cr)).convert('RGB')
 fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.tmp-',suffix=path.suffix)
 os.close(fd)
 try:
  out.save(tmp,format=fmt);os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 _refresh_record(path)
 done[rel]=hashlib.sha256(path.read_bytes()).hexdigest();save(project,state);return 'adjusted'

def balance_file(project,path):
 """For the download step: even out one freshly saved picture."""
 return adjust(project,path,target(project))

def balance_project(project):
 """All pictures of the project: {'adjusted':n,'ok':n,'failed':[names],'target':(mean,std)}."""
 files=pictures(project);goal=target(project,files);result={'adjusted':0,'ok':0,'failed':[],'target':goal}
 for f in files:
  try:result[adjust(project,f,goal)]+=1
  except Exception:result['failed'].append(f.name)
 return result

def restore(project):
 """Put the untouched originals back."""
 root=Path(project)/'.vis'/BACKUP;n=0
 if not root.is_dir():return 0
 for f in root.rglob('*'):
  if f.is_file():
   dest=Path(project)/SOURCE/f.relative_to(root)
   if dest.parent.is_dir():dest.write_bytes(f.read_bytes());_refresh_record(dest);n+=1
 return n
