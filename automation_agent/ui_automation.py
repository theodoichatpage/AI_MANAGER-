import time, uuid
from pathlib import Path
from .window_manager import require_windows, validate_target

SELECTORS={'title','title_re','auto_id','control_type','class_name','control_id'}

def root(target):
 require_windows();from pywinauto import Desktop
 return Desktop(backend='uia').window(handle=validate_target(target))

def element(target,selector):
 if not isinstance(selector,dict) or not selector or any(k not in SELECTORS for k in selector):raise ValueError('Cần selector UIA hợp lệ; không chọn phần tử tùy ý')
 win=root(target);spec=win.child_window(**selector)
 if not spec.exists(timeout=.2):raise RuntimeError('Không tìm thấy UI element')
 return spec.wrapper_object()

def describe(control):
 info=control.element_info
 return {'text':control.window_text(),'control_type':info.control_type,'automation_id':info.automation_id,'enabled':control.is_enabled(),'visible':control.is_visible()}

def click(target,selector,button='left',double=False):
 control=element(target,selector)
 if not control.is_enabled() or not control.is_visible():raise RuntimeError('UI element bị vô hiệu hóa hoặc không hiển thị')
 validate_target(target,True)
 if button=='left' and not double:
  try:control.invoke();return {'method':'UIA Invoke'}
  except (AttributeError,NotImplementedError):pass
  except Exception as exc:
   # A timed-out Invoke may already have acted. Do not click a second time.
   raise RuntimeError('UIA Invoke không xác nhận được kết quả: '+str(exc)) from exc
 control.click_input(button=button,double=double);return {'method':'element-relative input'}

def type_text(target,selector,text):
 if not isinstance(text,str) or len(text)>100000:raise ValueError('Text quá dài hoặc không hợp lệ')
 control=element(target,selector)
 if control.element_info.control_type!='Edit':raise RuntimeError('Chỉ nhập text vào UIA Edit được chỉ định')
 if not control.is_enabled():raise RuntimeError('Ô nhập bị vô hiệu hóa')
 validate_target(target,True);control.set_edit_text(text)
 # Do not return/log user text.
 if control.window_text()!=text:raise RuntimeError('Ô nhập không trả lại đúng text; cần kiểm tra trước khi nhập lại')
 return {'characters':len(text),'verified':True}

def hotkey(target,keys):
 from pywinauto.keyboard import send_keys
 aliases={'CTRL+A':'^a','CTRL+C':'^c','CTRL+V':'^v','ENTER':'{ENTER}','ESCAPE':'{ESC}','CTRL+L':'^l','CTRL+T':'^t','CTRL+W':'^w','CTRL+TAB':'^{TAB}','CTRL+SHIFT+TAB':'^+{TAB}','F5':'{F5}'}
 key=str(keys).upper()
 if key not in aliases:raise ValueError('Hotkey chưa nằm trong danh sách hỗ trợ')
 validate_target(target,True)
 # Explicit key release is handled by send_keys; each action is isolated.
 send_keys(aliases[key],pause=.02);return {'hotkey':key}

def wait_element(target,selector,timeout,gone=False):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  validate_target(target)
  found=root(target).child_window(**selector).exists(timeout=.1)
  if found!=gone:return {'found':found}
  time.sleep(.1)
 raise TimeoutError('Hết thời gian chờ UI element')

def screenshot(target,directory,full=False):
 require_windows();directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);name=str(uuid.uuid4())+'.png'
 if full:
  from PIL import ImageGrab
  image=ImageGrab.grab(all_screens=True)
 else:
  validate_target(target,True);image=root(target).capture_as_image()
 image.save(directory/name);return {'screenshot':name,'width':image.width,'height':image.height}

def scroll(target,selector,direction='down',amount=3):
 control=element(target,selector);validate_target(target,True)
 if direction not in ('up','down','left','right'):raise ValueError('Hướng scroll không hợp lệ')
 control.scroll(direction,amount=max(1,min(int(amount),20)));return {'scrolled':direction}

def drag_drop(target,source,destination):
 src=element(target,source);dst=element(target,destination);validate_target(target,True)
 # Coordinates are derived from live UIA element bounds, never screen constants.
 src.drag_mouse_input(dst=dst.rectangle().mid_point());return {'dragged':True,'method':'UIA bounds'}
