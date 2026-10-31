"""Read a Studio project cheaply (Supabase egress): ask for the small version stamp first and download the
whole project only when it changed. Replies are requested gzip-compressed."""
import copy,json,os,re,threading,time,urllib.error,urllib.parse,urllib.request,zlib
from pathlib import Path

API='https://gqzolyrdhlabcvjewlpo.supabase.co/functions/v1/studio-api'
LIMIT=5_000_000
_lock=threading.Lock();_cache={}

def decode(raw,encoding):
 if 'gzip' in (encoding or ''):
  d=zlib.decompressobj(16+zlib.MAX_WBITS);raw=d.decompress(raw,4*LIMIT)
  if d.unconsumed_tail:raise ValueError('Studio response quá lớn')
 if len(raw)>4*LIMIT:raise ValueError('Studio response quá lớn')
 return json.loads(raw)

def call(path,body=None,timeout=10):
 url=API+'?'+urllib.parse.urlencode({'path':path})
 headers={'Accept-Encoding':'gzip',**({'Content-Type':'application/json'} if body is not None else {})}
 req=urllib.request.Request(url,None if body is None else json.dumps(body).encode(),headers,method='GET' if body is None else 'POST')
 with urllib.request.urlopen(req,timeout=timeout) as r:
  raw=r.read(LIMIT+1);encoding=r.headers.get('Content-Encoding','')
 if len(raw)>LIMIT:raise ValueError('Studio response quá lớn')
 return decode(raw,encoding)

DISK_MAX_AGE=1800  # signed image links in a saved copy stay fresh: re-read at least every 30 minutes

def _disk(sid):
 """Each Manager step runs in its own short process, so the copy is also kept on disk (agent home), otherwise
 every step would download the whole project again."""
 home=os.environ.get('AI_MANAGER_AGENT_HOME')
 return Path(home)/'studio_cache'/(sid+'.json') if home and re.fullmatch(r'[A-Za-z0-9-]{16,64}',sid) else None

def remember(session):
 if isinstance(session,dict) and session.get('id'):
  entry=(session.get('updatedAt'),session.get('workEpoch') or 0,copy.deepcopy(session))
  with _lock:_cache[session['id']]=entry
  path=_disk(session['id'])
  if path:
   try:
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'at':time.time(),'session':session},ensure_ascii=False),encoding='utf8');tmp.replace(path)
   except OSError:pass
 return session

def _from_disk(sid):
 path=_disk(sid)
 if not path:return None
 try:saved=json.loads(path.read_text(encoding='utf8'))
 except (OSError,ValueError):return None
 s=saved.get('session') if isinstance(saved,dict) else None
 if not isinstance(s,dict) or s.get('id')!=sid or time.time()-float(saved.get('at') or 0)>DISK_MAX_AGE:return None
 return (s.get('updatedAt'),s.get('workEpoch') or 0,s)

def session(sid,timeout=10):
 """The project as Studio holds it. Unchanged since the last read: served from memory (or disk) after a tiny check."""
 with _lock:cached=_cache.get(sid)
 if not cached:cached=_from_disk(sid)
 if cached:
  try:v=call('sessions/'+sid+'/version',timeout=timeout).get('version')
  except (urllib.error.URLError,OSError,ValueError):v=None
  if v and not v.get('full') and v.get('updatedAt')==cached[0] and (v.get('workEpoch') or 0)==cached[1]:return copy.deepcopy(cached[2])
 return remember(call('sessions/'+sid,timeout=timeout).get('session'))
