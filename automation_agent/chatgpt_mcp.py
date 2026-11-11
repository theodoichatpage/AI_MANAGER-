"""ChatGPT operations over the existing Chrome DevTools MCP stdio transport.
No raw CDP socket and no Chrome launch. Fail closed on ambiguous accessibility.
"""
import json,subprocess,time,hashlib
from pathlib import Path
from urllib.parse import urlsplit

def _config(context,settings,url):
 c=dict(context.get('chrome_mcp_config') or settings.get('chrome_mcp') or {})
 if any(not c.get(k) for k in ('node','server','sdk_root','browser_url','profile_dir')):
  raise RuntimeError('CHROME_MCP_NOT_CONFIGURED')
 u=urlsplit(c['browser_url'])
 if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path not in ('','/') or u.username or u.password or u.query or u.fragment:
  raise RuntimeError('OWNED_LOOPBACK_CDP_REQUIRED')
 marker=Path(c['profile_dir'])/'DevToolsActivePort'
 if int(marker.read_text().splitlines()[0])!=u.port:raise RuntimeError('CHROME_PROFILE_ENDPOINT_MISMATCH')
 if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in ('chatgpt.com','chat.openai.com') or not urlsplit(url).path.startswith('/c/'):
  raise RuntimeError('CHATGPT_CONVERSATION_REQUIRED')
 if c.get('page_url')!=url:raise RuntimeError('EXACT_OWNED_PAGE_REQUIRED')
 return c

def _call_once(c,operation,text=None):
 payload=dict(c,operation='action',action={'action':'CHATGPT_SNAPSHOT' if operation=='snapshot' else 'CHATGPT_SEND','text':text})
 process=subprocess.run([c['node'],str(Path(__file__).with_name('chrome_mcp_bridge.mjs'))],
  input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,timeout=18,
  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 try:result=json.loads(process.stdout)
 except ValueError as exc:raise RuntimeError('MCP_RESPONSE_INVALID') from exc
 if process.returncode or result.get('error'):raise RuntimeError('MCP_ACTION_FAILED: '+str(result.get('error','unknown')))
 return result

SNAPSHOT_ATTEMPTS=3

def _call(c,operation,text=None):
 """A read-only snapshot reconnects (new bridge process) after a dropped MCP connection; a send never repeats."""
 if operation!='snapshot':return _call_once(c,operation,text)
 for attempt in range(SNAPSHOT_ATTEMPTS):
  try:return _call_once(c,operation,text)
  except (RuntimeError,subprocess.TimeoutExpired):
   if attempt+1==SNAPSHOT_ATTEMPTS:raise
   time.sleep(1+attempt)

def _same_prompt(seen,text):
 a=' '.join(str(seen or '').split());b=' '.join(str(text or '').split())
 return bool(a) and a==b

def parse_snapshot(raw,url):
 """Conservative parser: only explicitly attributed assistant turns qualify."""
 import re
 turns=[];current=None;composer=False;generating=False;end=False;saw_root=False
 for line in raw.splitlines():
  match=re.match(r'\s*uid=(\S+)\s+(\S+)(?:\s+("(?:[^"\\]|\\.)*"))?',line)
  if not match:continue
  if match[2].startswith('"'):
   # take_snapshot prints text verbatim (inner quotes are not escaped): a text line is everything between the
   # first and the last quote, so a JSON reply from ChatGPT is not cut at its first inner quote.
   plain=re.match(r'\s*uid=\S+\s+"(.*)"\s*$',line)
   if not plain:continue
   role='StaticText';name=plain[1]
  else:
   role=match[2]
   try:name=json.loads(match[3]) if match[3] else ''
   except ValueError:name=match[3][1:-1]
  if role=='RootWebArea':
   saw_root=True
   observed=re.search(r'\burl=("(?:[^"\\]|\\.)*")',line)
   if not observed or json.loads(observed[1])!=url:raise RuntimeError('MCP_SNAPSHOT_URL_MISMATCH')
  author={'You said:':'user','user message':'user','ChatGPT said:':'assistant','assistant message':'assistant'}.get(name)
  if author and role in ('heading','generic'):
   current={'role':author,'text':[]};turns.append(current);end=False;continue
  if role=='heading' and name=='Latest response':current=None
  if role=='textbox':
   composer=name in ('Ask anything','Ask ChatGPT','Message ChatGPT','Message','Send a message') and not re.search(r'\b(?:disabled|readonly)\b',line)
   current=None
  if role=='button':
   generating|=name.lower() in ('stop generating','stop responding','stop streaming','dừng tạo','dừng phản hồi')
   if current and current['role']=='assistant' and name in ('Copy','Copy response','Read aloud','Good response'):end=True
  if current and role=='StaticText':current['text'].append(name)
 if not saw_root:raise RuntimeError('MCP_SNAPSHOT_URL_MISSING')
 last=next((t for t in reversed(turns) if t['role']=='assistant'),None)
 text='\n'.join(last['text']) if last else ''
 return dict(url=url,lastAssistant=text,lastUserText=next(('\n'.join(t['text']) for t in reversed(turns) if t['role']=='user'),''),
  assistantCount=sum(t['role']=='assistant' for t in turns),turnCount=len(turns),lastRole=turns[-1]['role'] if turns else '',
  generating=generating,composerReady=composer,assistantEndControl=end,
  fingerprint=hashlib.sha256(text.encode()).hexdigest(),snapshot=raw)

def observe(context,settings,url,samples=3):
 c=_config(context,settings,url)
 samples=int(samples)
 if samples<3 or samples>8:raise ValueError('REQUIRE_3_TO_8_SAMPLES')
 rows=[]
 for i in range(samples):
  rows.append(parse_snapshot(_call(c,'snapshot')['snapshot'],url))
  if i+1<samples:time.sleep(.5)
 last=rows[-1]
 stable=bool(last['lastAssistant']) and len({r['fingerprint'] for r in rows})==1
 ready=all(not r['generating'] and r['composerReady'] and r['assistantEndControl'] and r['lastRole']=='assistant' for r in rows)
 completed=stable and ready and all(r['turnCount']==last['turnCount'] for r in rows)
 return {k:v for k,v in dict(last,stable=stable,completion_verified=completed,state='completed' if completed else 'unverified').items() if k!='snapshot'}

def send(context,settings,url,text,exchange_id,verified,fresh=False):
 if not isinstance(text,str) or not text.strip() or len(text)>12000:raise ValueError('INVALID_PROMPT')
 if not isinstance(exchange_id,str) or len(exchange_id)<8:raise ValueError('INVALID_EXCHANGE_ID')
 # The bridge verifies the composer value line by line, so a multi-line prompt can never be verified (and is never sent).
 text=' '.join(text.splitlines())
 tagged=exchange_id in text
 state=observe(context,settings,url)
 digest=hashlib.sha256(text.encode()).hexdigest()
 # A prompt that carries its exchange id and is already the latest user turn was delivered before an interruption:
 # report it as received instead of sending a duplicate.
 if tagged and exchange_id in state.get('lastUserText',''):
  return {'exchange_id':exchange_id,'submission':'received','url':url,'turnCount':state['turnCount'],'prompt_sha256':digest,'recovered':True}
 # fresh (WinControl): the page is checked now (idle, reply complete) instead of against an earlier observation, so a
 # task resumed after an interruption can send; its exchange id above already prevents a second copy.
 stale=not fresh and (not verified.get('completed') or verified.get('url')!=url or state['fingerprint']!=verified.get('fingerprint') or state['turnCount']!=verified.get('turn_count'))
 if not state['completion_verified'] or stale:
  raise RuntimeError('CHATGPT_UNVERIFIED_NO_SEND')
 c=_config(context,settings,url)
 _call(c,'fill_click',text)
 # Click alone is not receipt. A snapshot must show exact user text.
 for _ in range(8):
  snap=_call(c,'snapshot')['snapshot']
  receipt=parse_snapshot(snap,url)
  seen=receipt['lastUserText']
  # ChatGPT virtualizes older turns, so the visible turn count can stay flat
  # even after a successful send. The verified click/fill above plus a changed
  # latest user turn containing the exact prompt (or its unique exchange id) is also a receipt.
  changed=receipt['turnCount']>state['turnCount'] or state.get('lastUserText')!=seen
  if changed and (_same_prompt(seen,text) or (tagged and exchange_id in seen)):
   return {'exchange_id':exchange_id,'submission':'received','url':url,'turnCount':receipt['turnCount'],
           'prompt_sha256':digest}
  time.sleep(.5)
 raise RuntimeError('CHATGPT_RECEIPT_UNVERIFIED_NO_RETRY')
