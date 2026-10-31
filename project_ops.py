"""Copy, rename and delete Manager projects, and keep each project's own inputs (link, prompts, options).

A project is a folder <root>/<NNN>_<name>/ with project.json. Delete never erases: the folder moves to
<root>/_Thung_rac/ and can be moved back. Rename also renames the folder when nothing holds it open."""
import json,re,shutil,time
from pathlib import Path

TRASH='_Thung_rac'
INPUTS=('use_link','use_script','youtube_url','language','rewrite','rewrite_style','image_style','images','download','separate','separate_layers','lanes')
MAX_PROMPT=20000

def load(folder):return json.loads((Path(folder)/'project.json').read_text(encoding='utf8'))

def find(projects,pid):
 p=next((x for x in projects if x.get('id')==pid),None)
 if not p:raise ValueError('Không tìm thấy dự án')
 return p

def clean_name(name):
 name=re.sub(r'\s+',' ',str(name or '')).strip()
 if not name:raise ValueError('Nhập tên dự án')
 return name[:120]

def inputs(data):
 """The per-project inputs a user may set (validated); unknown keys are ignored."""
 out={}
 if 'youtube_url' in data:out['youtube_url']=str(data['youtube_url'] or '').strip()[:500]
 if 'language' in data:out['language']='en' if data['language']=='en' else 'vi'
 for k in ('rewrite','images','download','separate','use_link','use_script'):
  if k in data:out[k]=bool(data[k])
 for k in ('rewrite_style','image_style'):
  if k in data:
   text=str(data[k] or '')
   if len(text)>MAX_PROMPT:raise ValueError('Prompt quá dài (tối đa 20.000 ký tự)')
   out[k]=text
 if 'script' in data:
  text=str(data['script'] or '')
  if len(text)>2_000_000:raise ValueError('Kịch bản quá dài')
  out['script']=text
 if 'separate_layers' in data:out['separate_layers']=4 if data['separate_layers']==4 else 3
 return out

def update(p,data,atomic):
 """Save inputs (prompts, link, options) into project.json."""
 meta=load(p['folder']);meta.update(inputs(data));atomic(Path(p['folder'])/'project.json',meta);return meta

def rename(p,name,slug,queue,atomic):
 """New display name; the folder becomes <NNN>_<new name> when possible. Studio gets the name on its next report."""
 name=clean_name(name);folder=Path(p['folder']);meta=load(folder)
 if name==meta.get('name'):return meta
 if queue.get(p['id'])['status'] in ('running','paused'):raise ValueError('Dừng dự án trước khi đổi tên')
 number=(re.match(r'^(\d+)_',folder.name) or [None,''])[1]
 target=folder.parent/((number+'_' if number else '')+slug(name))
 moved=False
 if target!=folder and not target.exists():
  try:folder.rename(target);folder=target;moved=True
  except OSError:pass  # a file in the folder is open (e.g. in Explorer): keep the folder name, change only the name
 meta.update(name=name,folder=str(folder))
 if meta.get('studio_project_id'):meta['name_pending']=True
 atomic(folder/'project.json',meta)
 queue.relocate(p['id'],name,folder)
 return dict(meta,folder_renamed=moved)

def copy(p,create_project,queue,atomic):
 """A new project with the same inputs (script, link, prompts, options). Results are not copied, and the copy has
 no Studio project yet: deploying it starts fresh."""
 meta=load(p['folder'])
 new=create_project(meta.get('name','')+' (bản sao)',meta.get('script',''))
 for k in INPUTS:
  if k in meta:new[k]=meta[k]
 new['copied_from']=p['id'];atomic(Path(new['folder'])/'project.json',new);queue.add(new)
 return new

def trashed_studio_ids(root):
 """Studio project ids of the projects in the trash."""
 ids=set()
 for f in (Path(root)/TRASH).glob('*/project.json'):
  try:m=json.loads(f.read_text(encoding='utf8'))
  except (OSError,ValueError):continue
  ids.update(x for x in (m.get('studio_project_id'),m.get('studio_import_id'),(m.get('studio_source') or {}).get('id')) if x)
 return ids

def delete(p,queue,root):
 """Move the project folder to <root>/_Thung_rac/ (not erased)."""
 if queue.get(p['id'])['status'] in ('running','paused'):raise ValueError('Dừng dự án trước khi xoá')
 queue.remove(p['id'])
 folder=Path(p['folder']);trash=Path(root)/TRASH;trash.mkdir(exist_ok=True)
 target=trash/(folder.name+'-'+time.strftime('%Y%m%d-%H%M%S'))
 shutil.move(str(folder),str(target))
 return {'ok':True,'trash':str(target)}
