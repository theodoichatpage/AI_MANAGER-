"""One action per process: a hung UIA call cannot block STOP or the agent API."""
import json, sys, time, subprocess, os
from pathlib import Path
from . import window_manager as wm
from . import ui_automation as ui
from .browser_controller import BrowserController

def dispatch(a,context,home,settings):
 os.environ['AI_MANAGER_AGENT_HOME']=str(home)
 name=a['action'];app=a.get('target_app') or context.get('target_app')
 target=dict(context,target_app=app)
 if app=='edge':
  from .edge_controller import EdgeController,verified_windows
  if name=='EDGE_DIAGNOSTICS':
   from .edge_controller import diagnostics
   from .build_identity import identity
   return dict(diagnostics(a.get('browser_profile')),worker_identity=identity())
  if name=='LIST_EDGE_PROFILES':
   from .edge_profiles import list_profiles
   try:installed=bool(wm.executable('edge',settings))
   except RuntimeError:installed=False
   return {'profiles':list_profiles(),'installed':installed,'running':bool(wm.windows('edge'))}
  if name=='LIST_WINDOWS':return {'windows':verified_windows(a.get('browser_profile'))}
  if a.get('browser_profile') and target.get('browser_profile') and a['browser_profile']!=target['browser_profile']:raise RuntimeError('Edge Profile không khớp checkpoint/cửa sổ')
  if name=='OPEN_APP':
   if target.get('hwnd'):
    wm.validate_target(target);return {'context':target,'already_running':True}
   return EdgeController.open(a.get('browser_profile') or target.get('browser_profile'),settings)
 if a.get('hwnd') and name not in ('OPEN_APP','OPEN_TEST_WINDOW'):
  if target.get('hwnd')==int(a['hwnd']) and context.get('target_app')==app:
   wm.validate_target(target)
  else:
   rows=[w for w in wm.windows(app) if w['hwnd']==int(a['hwnd'])]
   if not rows:raise RuntimeError('HWND không thuộc ứng dụng đích')
   target.update(rows[0])
 if name=='WAIT':time.sleep(max(0,min(float(a.get('seconds',1)),300)));return {'waited':float(a.get('seconds',1))}
 if name=='LIST_PROCESSES':return {'processes':wm.processes()}
 if name=='LIST_WINDOWS':return {'windows':wm.windows(app,a.get('title'))}
 if name=='SCREENSHOT' and a.get('full_screen'):return ui.screenshot({},Path(home)/'screenshots',True)
 if name=='CHECK_PROCESS':
  if app not in wm.APPS:raise ValueError('Ứng dụng không hợp lệ')
  ps=[p for p in wm.processes() if (p['name'] or '').lower() in wm.APPS[app]['names']]
  return {'running':bool(ps),'processes':ps}
 if name=='OPEN_APP':
  if a.get('hwnd') and context.get('hwnd')==int(a['hwnd']):wm.validate_target(target)
  return wm.open_app(app,settings)
 if name=='OPEN_TEST_WINDOW':
  wm.require_windows()
  if not wm.windows('test'):subprocess.Popen([sys.executable,'-m','automation_agent.test_window'],shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  return {'context':{'target_app':'test'}}
 if app=='edge' and name=='RESTART_APP':
  wm.close(target);return EdgeController.open(target.get('browser_profile'),settings)
 if name in ('FIND_WINDOW','WAIT_WINDOW'):
  if app=='edge':
   if not target.get('hwnd'):
    rows=verified_windows(a.get('browser_profile') or target.get('browser_profile'))
    if len(rows)!=1:raise RuntimeError('Chọn duy nhất cửa sổ Edge đã xác minh profile')
    target.update(rows[0])
   wm.validate_target(target);return {'context':target,'window':target}
  if a.get('hwnd'):return {'context':target,'window':target}
  deadline=time.monotonic()+float(a.get('timeout',30))-.1
  while True:
   try:
    t=wm.find_window(app,a.get('title'));return {'context':dict(t,target_app=app),'window':t}
   except wm.WindowNotFoundError:
    if name=='FIND_WINDOW' or time.monotonic()>=deadline:raise
    time.sleep(.2)
 if not target.get('hwnd'):
  target.update(wm.find_window(app,a.get('title')))
 if name=='FOCUS_WINDOW':return wm.focus(target)
 if name in ('RESTORE','MAXIMIZE','MINIMIZE'):return wm.set_state(target,name)
 if name=='CLOSE_APP':return wm.close(target)
 if name=='RESTART_APP':
  wm.close(target);return wm.open_app(app,settings)
 if name=='SCREENSHOT':return ui.screenshot(target,Path(home)/'screenshots',bool(a.get('full_screen')))
 if name=='FIND_ELEMENT':return {'element':ui.describe(ui.element(target,a.get('selector')))}
 if name=='READ_ELEMENT':return {'element':ui.describe(ui.element(target,a.get('selector')))}
 if name in ('CLICK','DOUBLE_CLICK','RIGHT_CLICK'):return ui.click(target,a.get('selector'),'right' if name=='RIGHT_CLICK' else 'left',name=='DOUBLE_CLICK')
 if name=='TYPE_TEXT':return ui.type_text(target,a.get('selector'),a.get('text',''))
 if name=='HOTKEY':return ui.hotkey(target,a.get('keys'))
 if name=='SCROLL':return ui.scroll(target,a.get('selector'),a.get('direction','down'),a.get('amount',3))
 if name=='DRAG_DROP':return ui.drag_drop(target,a.get('selector'),a.get('destination'))
 if name in ('WAIT_ELEMENT','WAIT_ELEMENT_GONE'):return ui.wait_element(target,a.get('selector'),float(a.get('timeout',30))-.1,name=='WAIT_ELEMENT_GONE')
 if app not in ('chrome','edge'):raise ValueError('Action cần Chrome hoặc Edge')
 browser=EdgeController(target) if app=='edge' else BrowserController(target)
 if name=='OPEN_URL':return browser.open_url(a.get('url'))
 if name=='READ_URL':return {'url':browser.read_url()}
 if name=='WAIT_PAGE':return browser.wait_page(a.get('url') or context.get('expected_url'),float(a.get('timeout',30))-.1)
 key={'NEW_TAB':'CTRL+T','CLOSE_TAB':'CTRL+W','SWITCH_TAB':'CTRL+TAB','REFRESH':'F5'}.get(name)
 if key:return browser.key(key)
 raise ValueError('Action chưa được hỗ trợ')

def main():
 data=json.load(sys.stdin)
 try:
  result=dispatch(data['action'],data.get('context',{}),data['home'],data.get('settings',{}))
  print(json.dumps({'success':True,'result':result},ensure_ascii=True),flush=True)
 except Exception as e:print(json.dumps({'success':False,'error':str(e),'error_code':'WINDOW_LOST' if isinstance(e,wm.WindowLostError) else 'ACTION_ERROR'},ensure_ascii=True),flush=True)
if __name__=='__main__':main()
