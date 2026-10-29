"""Read profile names only. Never open Cookies, Login Data or credential stores."""
import json,os,re,ntpath
from pathlib import Path

def user_data_root():
 return Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft/Edge/User Data'

def list_profiles(root=None):
 root=Path(root) if root is not None else user_data_root()
 if not root.is_dir():return []
 try:cache=json.loads((root/'Local State').read_text(encoding='utf-8')).get('profile',{}).get('info_cache',{})
 except (OSError,ValueError):cache={}
 rows=[]
 for p in sorted(root.iterdir(),key=lambda p:p.name):
  if not re.fullmatch(r'Default|Profile [0-9]+',p.name) or p.is_symlink() or not (p/'Preferences').is_file():continue
  meta=cache.get(p.name,{})
  rows.append({'directory':p.name,'name':str(meta.get('name') or p.name)[:150]})
 return rows

def require_profile(directory,root=None):
 for p in list_profiles(root):
  if p['directory']==directory:return p
 raise ValueError('Profile Edge không tồn tại. Làm mới và chọn profile có sẵn; không tạo profile mới.')

def matches_profile_path(texts,expected):
 expected=ntpath.normcase(ntpath.normpath(str(expected)))
 return any(ntpath.normcase(ntpath.normpath(str(t).strip()))==expected for t in texts)
