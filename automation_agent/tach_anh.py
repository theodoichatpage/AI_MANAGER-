"""Scenes separated by hand in Studio land as <project>/Tach anh/<scene>/. Manager's own separation (and the later Video
Parallax step) uses <project>/Tach anh/Phan N - <title>/Canh M - <title>/. The picture folders in <project>/Anh/ already
carry that part/scene naming, so a scene is filed under the part that holds its picture."""
from pathlib import Path

SEPARATED='Tach anh'
IMAGES=('.png','.jpg','.jpeg','.webp')

def scene_parts(project):
 """{scene name (lower case, no extension): part folder name} from <project>/Anh/<part>/<scene picture or folder>."""
 anh=Path(project)/'Anh';found={}
 if not anh.is_dir():return found
 for part in sorted(p for p in anh.iterdir() if p.is_dir() and not p.name.startswith(('_','.'))):
  for item in sorted(part.iterdir()):
   if item.name.startswith(('_','.')):continue
   if item.is_file() and item.suffix.lower() in IMAGES:found.setdefault(item.stem.lower(),part.name)
   elif item.is_dir():found.setdefault(item.name.lower(),part.name)
 return found

def done_scenes(project):
 """Lower-case names of scenes that already have separated layers, directly in Tach anh/ or under a part."""
 root=Path(project)/SEPARATED;names=set()
 if not root.is_dir():return []
 def has_layers(d):return any(f.is_file() and f.suffix.lower()=='.png' and f.name[:3] in ('00_','01_','02_','03_') for f in d.iterdir())
 for top in (p for p in root.iterdir() if p.is_dir() and not p.name.startswith(('_','.'))):
  if has_layers(top):names.add(top.name.lower())
  else:names.update(s.name.lower() for s in top.iterdir() if s.is_dir() and not s.name.startswith(('_','.')) and has_layers(s))
 return sorted(names)
