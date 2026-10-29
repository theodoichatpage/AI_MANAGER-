"""Read a Studio project cheaply (Supabase egress): ask for the small version stamp first and download the
whole project only when it changed. Replies are requested gzip-compressed."""
import copy,json,threading,urllib.error,urllib.parse,urllib.request,zlib

API='https://wtxgjsorpqjanxoevxuw.supabase.co/functions/v1/studio-api'
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

def remember(session):
 if isinstance(session,dict) and session.get('id'):
  with _lock:_cache[session['id']]=(session.get('updatedAt'),session.get('workEpoch') or 0,copy.deepcopy(session))
 return session

def session(sid,timeout=10):
 """The project as Studio holds it. Unchanged since the last read: served from memory after a tiny check."""
 with _lock:cached=_cache.get(sid)
 if cached:
  try:v=call('sessions/'+sid+'/version',timeout=timeout).get('version')
  except (urllib.error.URLError,OSError,ValueError):v=None
  if v and not v.get('full') and v.get('updatedAt')==cached[0] and (v.get('workEpoch') or 0)==cached[1]:return copy.deepcopy(cached[2])
 return remember(call('sessions/'+sid,timeout=timeout).get('session'))
