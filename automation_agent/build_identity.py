"""Actual process identity. Artifact commit is trusted only when source hash matches."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from functools import lru_cache
from importlib.metadata import version,PackageNotFoundError
VERSION='0.2.21'

def fingerprint():
 h=hashlib.sha256();root=Path(__file__).parent
 for p in sorted(root.rglob('*.py')):
  h.update(str(p.relative_to(root)).encode());h.update(b'\0');h.update(p.read_bytes())
 return h.hexdigest()

@lru_cache(maxsize=1)
def identity():
 root=Path(__file__).resolve().parent.parent;digest=fingerprint();commit=None;provenance='unknown'
 try:
  data=json.loads((root/'build_info.json').read_text())
  if data.get('version')==VERSION and data.get('source_sha256')==digest:commit=data.get('commit');provenance='verified artifact manifest'
 except (OSError,ValueError):pass
 if commit is None and (root/'.git').exists():
  try:
   status=subprocess.check_output(['git','status','--porcelain','--','automation_agent'],cwd=root,text=True,timeout=2)
   if not status.strip():commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True,timeout=2).strip();provenance='clean git checkout'
  except (OSError,subprocess.SubprocessError):pass
 try:pywin32=version('pywin32')
 except PackageNotFoundError:pywin32=None
 return {'version':VERSION,'commit':commit,'provenance':provenance,'source_sha256':digest,'source_root':str(root),'source_file':str(Path(__file__).resolve()),'pid':os.getpid(),'python_executable':sys.executable,'pywin32_version':pywin32}
