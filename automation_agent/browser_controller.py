from urllib.parse import urlparse
from . import window_manager as wm
from . import ui_automation as ui
import time

class BrowserController:
 def __init__(self,target):self.target=target
 def address_bar(self):
  controls=ui.root(self.target).descendants(control_type='Edit')
  for c in controls:
   info=c.element_info
   if info.class_name=='OmniboxViewViews' or info.automation_id in ('addressEditBox','view_1020') or c.window_text() in ('Address and search bar','Thanh địa chỉ và tìm kiếm') or info.name in ('Address and search bar','Thanh địa chỉ và tìm kiếm'):
    return c
  raise RuntimeError('Chrome chưa cung cấp thanh địa chỉ qua UIA; không đoán ô nhập trên trang')
 def read_url(self):return self.address_bar().get_value()
 def open_url(self,url):
  p=urlparse(str(url))
  if p.scheme not in ('http','https') or not p.netloc:raise ValueError('Chỉ mở URL http/https')
  wm.focus(self.target);bar=self.address_bar();wm.validate_target(self.target,True)
  try:bar.set_edit_text(url)
  except Exception:
   import win32clipboard,win32con
   ui.hotkey(self.target,'CTRL+L');wm.validate_target(self.target,True)
   win32clipboard.OpenClipboard()
   try:win32clipboard.EmptyClipboard();win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT,url)
   finally:win32clipboard.CloseClipboard()
   ui.hotkey(self.target,'CTRL+V')
  ui.hotkey(self.target,'ENTER');return {'requested_url':url,'context':dict(self.target,expected_url=url)}
 def wait_page(self,url=None,timeout=25):
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   wm.validate_target(self.target)
   current=self.read_url()
   # UIA documents prove renderer accessibility, not network-idle or app readiness.
   same=not url or current.rstrip('/')==url.rstrip('/') or current.removeprefix('https://').rstrip('/')==url.removeprefix('https://').rstrip('/')
   docs=ui.root(self.target).descendants(control_type='Document')
   if same and docs:return {'url':current,'page_accessible':True,'verification':'UIA URL + Document; không xác nhận network-idle'}
   time.sleep(.25)
  raise TimeoutError('Chrome chưa hiển thị đúng URL/Document trong thời hạn')
 def key(self,key):
  wm.focus(self.target);return ui.hotkey(self.target,key)

 def chatgpt_snapshot(self):
  """Read a guarded UIA snapshot; no navigation or reload."""
  import hashlib
  current=self.read_url()
  parsed=urlparse(current)
  if parsed.scheme!='https' or parsed.hostname not in ('chatgpt.com','chat.openai.com') or not parsed.path.startswith('/c/'):
   raise ValueError('Chỉ đọc hội thoại ChatGPT có URL /c/ đã xác minh')
  wm.validate_target(self.target)
  documents=ui.root(self.target).descendants(control_type='Document')
  if len(documents)!=1:raise RuntimeError('Không xác minh được duy nhất một Document của hội thoại')
  document=documents[0]
  text=document.window_text() or ''
  if not text.strip():raise RuntimeError('Chưa đọc được nội dung hội thoại qua UIA')
  buttons=document.descendants(control_type='Button')
  labels=[(button.window_text() or '').strip().lower() for button in buttons]
  stop=any(label in ('stop generating','stop responding','dừng tạo','dừng phản hồi') for label in labels)
  send=any(label in ('send prompt','send message','gửi tin nhắn','gửi') for label in labels)
  # A stable document is only evidence of stability, not a server receipt.
  return {'url':current,'text':text,'fingerprint':hashlib.sha256(text.encode('utf-8')).hexdigest(),
          'generating':stop,'state':'generating' if stop else 'unverified',
          'send_control_visible':send,'completion_verified':False}

 def chatgpt_observe(self,samples=3,interval=1):
  """Stable DOM samples; require explicit assistant end controls before completion."""
  import time as _time
  samples=int(samples)
  if samples<3 or samples>8:raise ValueError('Cần ít nhất 3 mẫu UIA')
  observed=[]
  for index in range(samples):
   snap=self.chatgpt_snapshot()
   observed.append(snap)
   if index+1<samples:_time.sleep(max(.2,min(float(interval),5)))
  last=observed[-1]
  stable=all(s['url']==last['url'] and s['fingerprint']==last['fingerprint'] and not s['generating'] for s in observed)
  # The current UIA reader cannot distinguish assistant content from user/page chrome,
  # so stability must not authorize sending the next prompt.
  return dict(last,stable=stable,observations=samples,completion_verified=False,
              state='generating' if any(s['generating'] for s in observed) else 'unverified',
              reason='UIA document lacks a verified last-assistant completion marker')

 def chatgpt_dom(self,port=9222):
  """Read only an explicitly attached local Chrome DevTools target (no reload)."""
  import json,urllib.request
  port=int(port)
  if not 1024<=port<=65535:raise ValueError('Cổng CDP không hợp lệ')
  url=self.read_url()
  parsed=urlparse(url)
  if parsed.scheme!='https' or parsed.hostname not in ('chatgpt.com','chat.openai.com') or not parsed.path.startswith('/c/'):
   raise ValueError('Không phải hội thoại ChatGPT đã xác minh')
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json/list',timeout=2) as response:
    targets=json.load(response)
  except Exception as exc:raise RuntimeError('Chrome DevTools chưa kết nối; không reload') from exc
  matching=[target for target in targets if target.get('type')=='page' and target.get('url','').split('#')[0].rstrip('/')==url.split('#')[0].rstrip('/')]
  if len(matching)!=1:raise RuntimeError('Không xác minh được duy nhất một tab ChatGPT qua CDP')
  target=matching[0]
  wsurl=target.get('webSocketDebuggerUrl','')
  if not wsurl.startswith('ws://127.0.0.1:') and not wsurl.startswith('ws://localhost:'):
   raise RuntimeError('CDP endpoint không thuộc localhost')
  try:import websocket
  except ImportError as exc:raise RuntimeError('Thiếu websocket-client để đọc Chrome DevTools') from exc
  expression=r"""(() => {
    const turns=[...document.querySelectorAll('[data-message-author-role]')];
    const assistants=turns.filter(x=>x.getAttribute('data-message-author-role')==='assistant');
    const last=assistants.at(-1);
    const stop=!!document.querySelector('button[aria-label*="Stop"],button[data-testid="stop-button"]');
    const composer=document.querySelector('#prompt-textarea,[data-testid="composer-text-input"]');
    const send=document.querySelector('button[data-testid="send-button"],button[aria-label="Send prompt"]');
    return {url:location.href,assistantCount:assistants.length,
      lastAssistant:last?.innerText||'',lastAssistantId:last?.getAttribute('data-message-id')||'',
      generating:stop,composerReady:!!composer&&!composer.hasAttribute('disabled'),
      sendControlPresent:!!send,turnCount:turns.length};
  })()"""
  ws=websocket.create_connection(wsurl,timeout=4,origin='http://localhost')
  try:
   ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True}}))
   while True:
    data=json.loads(ws.recv())
    if data.get('id')==1:break
   value=data.get('result',{}).get('result',{}).get('value')
   if not isinstance(value,dict):raise RuntimeError('DOM ChatGPT không trả kết quả hợp lệ')
   if value.get('url','').split('#')[0].rstrip('/')!=url.split('#')[0].rstrip('/'):
    raise RuntimeError('CDP đã chuyển sang hội thoại khác')
   return value
  finally:ws.close()

 def chatgpt_dom_observe(self,port=9222,samples=3,interval=.5):
  import hashlib
  if not 3<=int(samples)<=8:raise ValueError('Cần 3–8 mẫu')
  values=[]
  for index in range(int(samples)):
   values.append(self.chatgpt_dom(port))
   if index+1<int(samples):time.sleep(max(.2,min(float(interval),5)))
  last=values[-1]
  fingerprints=[hashlib.sha256(str(v.get('lastAssistant','')).encode()).hexdigest() for v in values]
  stable=len(set(fingerprints))==1 and bool(last.get('lastAssistant','').strip())
  same=all(v.get('url')==last.get('url') and v.get('assistantCount')==last.get('assistantCount') and v.get('turnCount')==last.get('turnCount') for v in values)
  ready=all(not v.get('generating') and v.get('composerReady') and v.get('sendControlPresent') for v in values)
  verified=bool(stable and same and ready and last.get('assistantCount',0)>0)
  return dict(last,stable=stable,completion_verified=verified,state='completed' if verified else 'unverified',fingerprint=fingerprints[-1])

 def chatgpt_send_verified(self,text,exchange_id,expected_url,expected_fingerprint,port=9222):
  """Single-attempt UIA send guarded by fresh CDP observation; caller journals in_flight first."""
  import hashlib
  if not isinstance(text,str) or not text.strip() or len(text)>12000:raise ValueError('Yêu cầu tiếp tục trống hoặc quá dài')
  if not isinstance(exchange_id,str) or not 8<=len(exchange_id)<=128:raise ValueError('Thiếu định danh lượt trao đổi')
  if not isinstance(expected_fingerprint,str) or len(expected_fingerprint)!=64:raise ValueError('Thiếu dấu vân tay phản hồi đã xác minh')
  state=self.chatgpt_dom_observe(port)
  if not state['completion_verified'] or state['url']!=expected_url or state['fingerprint']!=expected_fingerprint:
   raise RuntimeError('ChatGPT chưa xác minh hoàn tất hoặc đã thay đổi; không gửi')
  edits=ui.root(self.target).descendants(control_type='Edit')
  candidates=[control for control in edits if getattr(control.element_info,'automation_id','') in ('prompt-textarea','composer-text-input')]
  if len(candidates)!=1:raise RuntimeError('Không xác minh được duy nhất ô nhập ChatGPT; không gửi')
  wm.validate_target(self.target,True)
  control=candidates[0]
  if not control.is_enabled() or not control.is_visible():raise RuntimeError('Ô nhập ChatGPT chưa sẵn sàng')
  control.set_edit_text(text)
  if control.window_text()!=text:raise RuntimeError('Không xác minh được nội dung đã nhập; không gửi')
  # Enter may have been delivered even if the worker loses connection; never auto-retry.
  ui.hotkey(self.target,'ENTER')
  return {'exchange_id':exchange_id,'submission':'uncertain','expected_url':expected_url,
          'prompt_sha256':hashlib.sha256(text.encode()).hexdigest()}
