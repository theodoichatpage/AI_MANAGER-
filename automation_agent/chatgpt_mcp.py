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
 if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path not in ('','/') or u.username or u.password:
  raise RuntimeError('OWNED_LOOPBACK_CDP_REQUIRED')
 marker=Path(c['profile_dir'])/'DevToolsActivePort'
 if int(marker.read_text().splitlines()[0])!=u.port:raise RuntimeError('CHROME_PROFILE_ENDPOINT_MISMATCH')
 if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in ('chatgpt.com','chat.openai.com') or not urlsplit(url).path.startswith('/c/'):
  raise RuntimeError('CHATGPT_CONVERSATION_REQUIRED')
 if c.get('page_url')!=url:raise RuntimeError('EXACT_OWNED_PAGE_REQUIRED')
 return c

def _call(c,operation,text=None):
 payload=dict(c,operation=operation,text=text)
 process=subprocess.run([c['node'],str(Path(__file__).with_name('chatgpt_mcp_bridge.mjs'))],
  input=json.dumps(payload),text=True,capture_output=True,timeout=18,
  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 try:result=json.loads(process.stdout)
 except ValueError as exc:raise RuntimeError('MCP_RESPONSE_INVALID') from exc
 if process.returncode or result.get('error'):raise RuntimeError('MCP_ACTION_FAILED: '+str(result.get('error','unknown')))
 return result

def parse_snapshot(raw,url):
 """Conservative parser: only explicitly attributed assistant turns qualify."""
 import re
 lines=raw.splitlines()
 # The MCP accessibility tree does not guarantee a stable author-role identifier.
 # Do not infer assistant text from a generic paragraph or page-wide text.
 assistant=[]
 for i,line in enumerate(lines):
  if re.search(r'\b(?:assistant message|ChatGPT said:)\b',line,re.I):
   chunk=[]
   for item in lines[i+1:]:
    if re.search(r'\b(?:user message|You said:|assistant message|ChatGPT said:)\b',item,re.I):break
    chunk.append(item)
   if chunk:assistant.append('\n'.join(chunk).strip())
 generating=any(re.search(r'\b(?:Stop generating|Stop responding|Dừng tạo|Dừng phản hồi)\b',line,re.I) for line in lines)
 composer=any(re.search(r'\btextbox\b.*(?:Message ChatGPT|Ask anything|Message|Send a message)',line,re.I) for line in lines)
 send=any(re.search(r'\bbutton\b.*(?:Send prompt|Send message|Send)',line,re.I) for line in lines)
 last=assistant[-1] if assistant else ''
 return {'url':url,'lastAssistant':last,'assistantCount':len(assistant),'generating':generating,
         'composerReady':composer,'sendControlPresent':send,
         'fingerprint':hashlib.sha256(last.encode()).hexdigest(),
         'snapshot':raw}

def observe(context,settings,url,samples=3):
 c=_config(context,settings,url)
 samples=int(samples)
 if samples<3 or samples>8:raise ValueError('Cần 3–8 mẫu')
 rows=[]
 for i in range(samples):
  rows.append(parse_snapshot(_call(c,'snapshot')['snapshot'],url))
  if i+1<samples:time.sleep(.5)
 last=rows[-1]
 stable=bool(last['lastAssistant']) and len({r['fingerprint'] for r in rows})==1
 ready=all(not r['generating'] and r['composerReady'] and r['sendControlPresent'] for r in rows)
 completed=stable and ready and all(r['assistantCount']==last['assistantCount'] for r in rows)
 return {k:v for k,v in dict(last,stable=stable,completion_verified=completed,state='completed' if completed else 'unverified').items() if k!='snapshot'}

def send(context,settings,url,text,exchange_id,verified):
 if not isinstance(text,str) or not text.strip() or len(text)>12000:raise ValueError('INVALID_PROMPT')
 if not isinstance(exchange_id,str) or len(exchange_id)<8:raise ValueError('INVALID_EXCHANGE_ID')
 state=observe(context,settings,url)
 if not state['completion_verified'] or not verified.get('completed') or verified.get('url')!=url or state['fingerprint']!=verified.get('fingerprint'):
  raise RuntimeError('CHATGPT_UNVERIFIED_NO_SEND')
 c=_config(context,settings,url)
 _call(c,'fill_click',text)
 # Click alone is not receipt. A snapshot must show exact user text.
 for _ in range(5):
  snap=_call(c,'snapshot')['snapshot']
  # Require a user-authored turn marker, not text left in the composer.
  import re
  user_turns=re.findall(r'(?:You said:|user message)(.*?)(?=ChatGPT said:|assistant message|You said:|user message|\\Z)',snap,re.I|re.S)
  if any(text.strip()==turn.strip() for turn in user_turns):
   return {'exchange_id':exchange_id,'submission':'received','prompt_sha256':hashlib.sha256(text.encode()).hexdigest()}
  time.sleep(.5)
 raise RuntimeError('CHATGPT_RECEIPT_UNVERIFIED_NO_RETRY')
