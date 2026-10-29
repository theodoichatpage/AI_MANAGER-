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
