"""Readable files in the project folder, one folder per part:
  <project>/Anh/Phan 1 - <title>/Canh 1 - <title>.png       (pictures made in Studio)
  <project>/Tach anh/Phan 1 - <title>/Canh 1 - <title>/      (layers from the Local Engine)
Names drop Vietnamese accents (đ -> d) and characters Windows does not allow."""
import re,unicodedata
from pathlib import Path

IMAGES='Anh'
SEPARATED='Tach anh'
NAME_LIMIT=60  # keeps <project>\Tach anh\<part>\<scene>\<layer> well under Windows' 260-character path limit

def plain(text,limit=NAME_LIMIT):
 text=str(text or '').replace('đ','d').replace('Đ','D')
 text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode()
 text=re.sub(r'[<>:"/\\|?*\x00-\x1f]+','_',text)
 text=re.sub(r'\s+',' ',text).strip().strip('.')
 return text[:limit].rstrip(' .')

def titled(prefix,number,title):
 """'Phần 1 - Từ đáy' -> 'Phan 1 - Tu day' (Studio's own number is kept); a title without one gets 'Phan 1 - '."""
 text=plain(title)
 if re.match(r'(?i)%s\s*\d+(\D|$)'%prefix,text):return text
 return (prefix+' '+str(number)+(' - '+text if text else ''))[:NAME_LIMIT].rstrip(' .')

def layout(session):
 """Scene key -> (part folder, scene name). Two scenes with one name in the same part get ' (2)'."""
 out={}
 for pi,part in enumerate(session.get('parts') or [],1):
  folder=titled('Phan',pi,part.get('title'));used={}
  for si,scene in enumerate(part.get('scenes') or [],1):
   name=titled('Canh',si,scene.get('title'));n=used.get(name.lower(),0)+1;used[name.lower()]=n
   out[str(part['id'])+':'+str(si-1)]=(folder,name if n==1 else name+' ('+str(n)+')')
 return out

def image_place(project,lay,key):
 """(folder, file name without extension) for a scene picture."""
 part,name=lay[key];return Path(project)/IMAGES/part,name

def separation_dir(project,lay,key):
 part,name=lay[key];return Path(project)/SEPARATED/part/name

def save_scene_image(project,sid,lay,key,result,ordinal,fetch=None):
 from . import studio_images
 folder,name=image_place(project,lay,key)
 return studio_images.save_image(folder,sid,key,result,ordinal,**({'fetch':fetch} if fetch else {}),name=name,project=project)
