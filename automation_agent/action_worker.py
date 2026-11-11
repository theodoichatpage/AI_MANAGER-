"""One action per process: a hung UIA call cannot block STOP or the agent API."""
import json, sys, time, subprocess, os
from pathlib import Path
from . import window_manager as wm
from . import ui_automation as ui
from .browser_controller import BrowserController

NET_GRACE=900

def network_error(exc):
 """True for a connection problem (timeout, refused, DNS, SSL, cut-off or garbled reply, 5xx gateway),
 not for a Studio answer we refused or a local file problem."""
 import http.client,json,urllib.error,zlib
 if str(exc).startswith('Studio quá thời gian'):return False  # the progress watchdog, not the network
 if isinstance(exc,urllib.error.HTTPError):return exc.code>=500 or exc.code==429
 if isinstance(exc,(FileNotFoundError,PermissionError,IsADirectoryError,NotADirectoryError,FileExistsError)):return False
 return isinstance(exc,(OSError,http.client.HTTPException,zlib.error,json.JSONDecodeError))

def wincontrol_notepad(name,a,target,settings):
 """WinControl's Notepad: always its own new window (never a Notepad the user already has open), and Save As only
 into the WinControl temp folder, never over an existing file."""
 deadline=time.monotonic()+min(60,float(a.get('timeout',30)))
 if name=='OPEN_APP':
  proc=subprocess.Popen([wm.executable('notepad',settings)],shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  while time.monotonic()<deadline:
   rows=[r for r in wm.windows('notepad') if r['pid']==proc.pid]
   if rows:
    row=dict(rows[0],target_app='notepad')
    try:wm.focus(row)
    except Exception:pass
    return {'launched_pid':proc.pid,'window':rows[0]['title'],'context':row}
   time.sleep(.15)
  raise TimeoutError('Notepad window did not appear')
 from .wincontrol_chat_loop import _safe_temp_path
 from pywinauto import Desktop
 from pywinauto.keyboard import send_keys
 path=Path(_safe_temp_path(a.get('path')))
 if path.exists():raise FileExistsError('FILE_ALREADY_EXISTS_CHOOSE_NEW_NAME: '+str(path))
 path.parent.mkdir(parents=True,exist_ok=True)
 wm.focus(target);hwnd=wm.validate_target(target,True);pid=int(target['pid'])
 send_keys('^+s',pause=.02)
 dialog=None
 while time.monotonic()<deadline and dialog is None:
  found=[w for w in Desktop(backend='win32').windows(process=pid,class_name='#32770',visible_only=True) if w.handle!=hwnd]
  if found:dialog=Desktop(backend='uia').window(handle=found[0].handle)
  else:time.sleep(.2)
 if dialog is None:raise TimeoutError('Save As dialog did not open')
 name_box=dialog.child_window(auto_id='1001',control_type='Edit').wrapper_object()
 name_box.set_edit_text(str(path))
 try:typed=name_box.get_value()
 except Exception:typed=name_box.window_text()
 if typed!=str(path):raise RuntimeError('Save As file name was not accepted')
 dialog.child_window(auto_id='1',control_type='Button').wrapper_object().invoke()
 while time.monotonic()<deadline:
  titles=[r['title'].casefold() for r in wm.windows('notepad') if r['pid']==pid]
  if path.is_file() and any(path.stem.casefold() in t for t in titles):
   return {'saved':True,'path':str(path),'bytes':path.stat().st_size}
  time.sleep(.2)
 if path.is_file():return {'saved':True,'path':str(path),'bytes':path.stat().st_size,'title_unconfirmed':True}
 raise TimeoutError('Notepad did not save the file')

def dispatch(a,context,home,settings):
 os.environ['AI_MANAGER_AGENT_HOME']=str(home)
 name=a['action'];app=a.get('target_app') or context.get('target_app')
 target=dict(context,target_app=app)
 if name=='MAN_STATUS':
  import urllib.request
  from .wincontrol_chat_loop import man_health
  with urllib.request.urlopen(str(context.get('man_state_url') or 'http://127.0.0.1:8765/api/state'),timeout=min(20,float(a.get('timeout',30)))) as r:
   return man_health(json.load(r))
 if context.get('wincontrol_task') and app=='notepad' and name in ('OPEN_APP','SAVE_AS'):
  return wincontrol_notepad(name,a,target,settings)
 if name in ('ENSURE_TEMP_DIR','VERIFY_FILE','OPEN_FILE'):
  import tempfile
  root=(Path(tempfile.gettempdir())/'WinControl').resolve()
  if name=='ENSURE_TEMP_DIR':
   existed=root.is_dir();root.mkdir(parents=True,exist_ok=True)
   return {'created':not existed,'exists':existed,'path':str(root)}
  path=Path(str(a.get('path') or '')).expanduser().resolve()
  try:path.relative_to(root)
  except ValueError as exc:raise ValueError('FILE_PATH_OUTSIDE_WINCONTROL_TEMP') from exc
  if path==root:raise ValueError('FILE_PATH_REQUIRED')
  if name=='VERIFY_FILE':
   expected=a.get('expected_text')
   if not isinstance(expected,str):raise ValueError('FILE_EXPECTATION_REQUIRED')
   actual=path.read_text(encoding='utf-8-sig')
   if actual!=expected:raise ValueError('FILE_CONTENT_MISMATCH')
   return {'verified':True,'path':str(path),'characters':len(actual)}
  if app!='notepad':raise ValueError('OPEN_FILE_REQUIRES_NOTEPAD')
  if not path.is_file():raise FileNotFoundError(str(path))
  subprocess.Popen([wm.executable('notepad',settings),str(path)],shell=False,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  deadline=time.monotonic()+min(20,float(a.get('timeout',30)))
  while time.monotonic()<deadline:
   rows=wm.windows('notepad',path.stem)
   if rows:return {'opened':True,'path':str(path),'window':rows[0],'context':dict(rows[0],target_app='notepad')}
   time.sleep(.15)
  raise TimeoutError('Notepad did not show the requested file window')
 if target.get('studio_project_id'):
  from .resource_lock import StudioResource
  StudioResource(home).acquire(target,name)
 if name in ('STUDIO_FILES','STUDIO_OPEN','STUDIO_READY','STUDIO_TRANSCRIPT','STUDIO_ANALYZE','STUDIO_SCENES','STUDIO_IMAGES','STUDIO_LANES','STUDIO_PARALLEL'):
  from .studio_workflow import StudioReviewRequired
  # Launched Studio runs are identified by the Studio tab itself (project + run nonce + origin), not a window handle.
  if not target.get('studio_launch'):
   try:wm.validate_target(target)
   except wm.WindowLostError:raise
   except (RuntimeError,ValueError) as exc:raise StudioReviewRequired('Chưa xác minh đúng cửa sổ/profile; giữ checkpoint') from exc
  from .studio_workflow import StudioStep
  from .resource_lock import StudioResource
  resource=StudioResource(home);resource.acquire(target,name)
  step=StudioStep(target)
  try:
   result=step.step(name)
   if target.get('studio_net_since') and result.get('waiting'):result.setdefault('context',{})['studio_net_since']=None
   if not result.get('waiting'):
    current=step.api.request(step.sid)
    if not current.get('activeJob') and not current.get('imageJobs'):resource.release(target)
   return result
  except Exception as exc:
   from .studio_workflow import StudioReviewRequired
   # A short network drop (Vercel/Supabase slow or unreachable) is waited out: reads are safe to repeat, and an
   # unconfirmed command is never resent (send() keeps its 'intent' and asks for review instead).
   now=time.time();since=float(target.get('studio_net_since') or now)
   if now-float(target.get('studio_net_last') or 0)>120:since=now  # an old drop that recovered does not count
   if network_error(exc) and now-since<NET_GRACE:
    return {'waiting':True,'context':{'studio_net_since':since,'studio_net_last':now,'studio_waiting_action':name,'studio_message':'Mất kết nối Studio tạm thời, đang thử lại'}}
   why=type(exc).__name__+': '+str(exc)[:160]
   try:current=step.api.request(step.sid)
   except Exception:raise StudioReviewRequired('Không đọc được Studio để đối soát ('+why+'); giữ khóa và checkpoint') from exc
   if current.get('activeJob') or current.get('imageJobs') or any(v.get('state')=='intent' for v in step.j['commands'].values()):raise StudioReviewRequired('Còn tác vụ hoặc lệnh chưa rõ kết quả; giữ khóa và checkpoint') from exc
   resource.release(target)
   raise
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
 if not target.get('hwnd') and name not in ('OBSERVE_CHATGPT','SEND_CHATGPT','WINCONTROL_DECIDE'):
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
 if name=='OBSERVE_CHATGPT':
  from . import chatgpt_mcp
  url=context.get('expected_url') or (context.get('chrome_mcp_config') or {}).get('page_url')
  if not url:raise RuntimeError('EXACT_CHATGPT_URL_REQUIRED')
  observed=chatgpt_mcp.observe(context,settings,url,a.get('samples',3))
  return dict(observed,context={'chatgpt_verified':{'url':observed['url'],'fingerprint':observed['fingerprint'],'turn_count':observed['turnCount'],'completed':observed['completion_verified']}})
 if name=='SEND_CHATGPT':
  from . import chatgpt_mcp
  verified=context.get('chatgpt_verified') or {}
  url=context.get('expected_url') or (context.get('chrome_mcp_config') or {}).get('page_url')
  result=chatgpt_mcp.send(context,settings,url,a.get('text'),a.get('exchange_id'),verified,fresh=bool(context.get('wincontrol_task')))
  return dict(result,context={'chatgpt_exchange_id':result['exchange_id'],'chatgpt_submission':'received','chatgpt_verified':None})
 if name=='WINCONTROL_DECIDE':
  if not context.get('wincontrol_task'):raise RuntimeError('WINCONTROL_TASK_CONTEXT_REQUIRED')
  from .chatgpt_mcp import observe
  from .wincontrol_chat_loop import parse_decision
  url=context.get('expected_url') or (context.get('chrome_mcp_config') or {}).get('page_url')
  if not url:raise RuntimeError('EXACT_CHATGPT_URL_REQUIRED')
  since=float(context.get('wincontrol_wait_since') or 0) or time.time()
  limit=float(a.get('response_limit',context.get('wincontrol_response_limit',600)))
  try:observed=observe(context,settings,url,3)
  except RuntimeError as exc:
   # Reading is safe to repeat: a dropped MCP connection or a half-rendered page is waited out, not failed.
   if time.time()-since>limit:raise TimeoutError('CHATGPT_RESPONSE_TIMEOUT: '+str(exc)) from exc
   return {'waiting':True,'context':{'wincontrol_wait_since':since,'wincontrol_wait_reason':str(exc)[:300]}}
  if not observed.get('completion_verified') or observed.get('lastRole')!='assistant':
   if time.time()-since>limit:raise TimeoutError('CHATGPT_RESPONSE_TIMEOUT')
   return {'waiting':True,'context':{'wincontrol_wait_since':since,'wincontrol_wait_reason':'generating' if observed.get('generating') else 'unverified'}}
  # Only the reply to this round's prompt counts: the latest user turn must carry this round's exchange id.
  if a.get('exchange_id') and a['exchange_id'] not in str(observed.get('lastUserText') or ''):
   if time.time()-since>limit:raise TimeoutError('CHATGPT_REPLY_FOR_THIS_ROUND_NOT_FOUND')
   return {'waiting':True,'context':{'wincontrol_wait_since':since,'wincontrol_wait_reason':'other_turn'}}
  verified={'completed':True,'url':url,'fingerprint':observed['fingerprint'],'turn_count':observed['turnCount']}
  done={'chatgpt_verified':verified,'wincontrol_round':int(context.get('wincontrol_round',0))+1,'wincontrol_wait_since':None,'wincontrol_wait_reason':None}
  try:decision=parse_decision(observed.get('lastAssistant'))
  except ValueError as exc:
   # The reply is complete but unusable: hand it back to the runtime, which asks ChatGPT for a corrected reply.
   decision={'status':'invalid','summary':str(exc),'actions':[],'reply':str(observed.get('lastAssistant') or '')[:800]}
  return {'decision':decision,'context':done}
 if name=='WAIT_PAGE':return browser.wait_page(a.get('url') or context.get('expected_url'),float(a.get('timeout',30))-.1)
 key={'NEW_TAB':'CTRL+T','CLOSE_TAB':'CTRL+W','SWITCH_TAB':'CTRL+TAB','REFRESH':'F5'}.get(name)
 if key:return browser.key(key)
 raise ValueError('Action chưa được hỗ trợ')

def main():
 data=json.load(sys.stdin)
 try:
  result=dispatch(data['action'],data.get('context',{}),data['home'],data.get('settings',{}))
  print(json.dumps({'success':True,'result':result},ensure_ascii=True),flush=True)
 except Exception as e:print(json.dumps({'success':False,'error':str(e),'error_code':'WINDOW_LOST' if isinstance(e,wm.WindowLostError) else 'SCRIPT_MISSING' if type(e).__name__=='StudioScriptMissing' else 'STUDIO_REVIEW' if type(e).__name__=='StudioReviewRequired' or (data.get('context',{}).get('studio_project_id') and not str(data.get('action',{}).get('action','')).startswith('STUDIO_')) else 'ACTION_ERROR'},ensure_ascii=True),flush=True)
if __name__=='__main__':main()
