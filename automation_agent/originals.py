"""Original pictures kept on this PC.

The ChatGPT extension sends each new picture straight to AI Manager (localhost) and puts only a small preview on
Studio's server, so full-size pictures never travel through Supabase (its egress quota). Manager keeps them in
<project>/.vis/goc/<job id>.<ext>; "Tải ảnh" and "Tách ảnh" read from here before downloading anything."""
import base64,binascii,io,re
from pathlib import Path

FOLDER=('.vis','goc')
JOB=re.compile(r'[A-Za-z0-9_-]{6,80}')
DATA_URL=re.compile(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)')
EXT={'png':'.png','jpeg':'.jpg','webp':'.webp'}
MAX_BYTES=8_388_608

def folder(project):return Path(project).joinpath(*FOLDER)

def _hide(path):
 try:
  import ctypes;ctypes.windll.kernel32.SetFileAttributesW(str(path),2)
 except Exception:pass

def save(project,job_id,data_url):
 """Verify and keep one original. Returns its path; the same picture sent twice is kept once."""
 if not JOB.fullmatch(str(job_id or '')):raise ValueError('Mã tác vụ ảnh không hợp lệ')
 m=DATA_URL.fullmatch(str(data_url or ''))
 if not m:raise ValueError('Cần ảnh PNG/JPEG/WebP dạng data URL')
 try:data=base64.b64decode(m.group(2),validate=True)
 except (binascii.Error,ValueError) as exc:raise ValueError('Dữ liệu ảnh hỏng') from exc
 if len(data)>MAX_BYTES:raise ValueError('Ảnh vượt giới hạn 8 MB')
 from PIL import Image
 with Image.open(io.BytesIO(data)) as image:
  if image.width*image.height>40_000_000:raise ValueError('Ảnh vượt giới hạn kích thước giải mã')
  image.verify()
 target=folder(project);target.mkdir(parents=True,exist_ok=True);_hide(target.parent)
 path=target/(job_id+EXT[m.group(1)])
 if path.exists() and path.read_bytes()==data:return path
 tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(data);tmp.replace(path)
 return path

def find(project,result):
 """The kept original for a Studio image result (by its job id), or None."""
 job=str((result or {}).get('jobId') or '')
 if not project or not JOB.fullmatch(job):return None
 for ext in EXT.values():
  path=folder(project)/(job+ext)
  if path.is_file():return path
 return None

def read(project,result):
 path=find(project,result)
 return path.read_bytes() if path else None

def require(project,result,fetch):
 """Bytes of the full picture: the local original first; a preview-only result is never taken as the original."""
 data=read(project,result)
 if data is not None:return data
 if (result or {}).get('local'):raise ValueError('Ảnh gốc chỉ lưu trên máy đã tạo ảnh; máy này chưa có (Studio chỉ giữ ảnh xem trước)')
 return fetch(result['url'])
