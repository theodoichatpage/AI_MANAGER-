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
