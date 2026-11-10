"""Windows-only acceptance: two ChatGPT turns using existing ActionExecutor/TaskStore.
Requires a dedicated, already-open ChatGPT conversation with an assistant reply.
Run from repo root: python -m tests.wincontrol_chatgpt_acceptance --url https://chatgpt.com/c/ID
Never use a conversation containing unsaved work. No reload or navigation.
"""
import argparse
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from automation_agent.action_executor import ActionExecutor
from automation_agent.browser_controller import BrowserController
from automation_agent.task_store import TaskStore
from automation_agent import window_manager as wm

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--url',required=True,help='Dedicated test conversation URL, not a development chat')
 parser.add_argument('--home',default=None,help='Existing isolated acceptance checkpoint folder')
 parser.add_argument('--cdp-port',type=int,default=9222)
 parser.add_argument('--timeout',type=int,default=180)
 parser.add_argument('--hwnd',type=int,default=None)
 args=parser.parse_args()
 if sys.platform!='win32':raise SystemExit('BLOCKED: requires real Windows Chrome')
 if not args.url.startswith('https://chatgpt.com/c/'):raise SystemExit('BLOCKED: expected dedicated ChatGPT conversation URL')
 home=Path(args.home) if args.home else Path(tempfile.gettempdir())/'wincontrol-chatgpt-acceptance'
 home.mkdir(parents=True,exist_ok=True)
 store=TaskStore(home/'agent.sqlite3')
 executor=ActionExecutor(home)
 windows=[w for w in wm.windows('chrome') if args.hwnd is None or w['hwnd']==args.hwnd]
 if len(windows)!=1:raise SystemExit('BLOCKED: select one verified Chrome window using --hwnd')
 target=dict(windows[0],target_app='chrome')
 browser=BrowserController(target)
 if browser.read_url()!=args.url:raise SystemExit('BLOCKED: Chrome must already show dedicated test conversation')
 actions=[]
 for i in (1,2):
  actions.extend([{'action':'OBSERVE_CHATGPT','target_app':'chrome','cdp_port':args.cdp_port,'timeout':25},
                  {'action':'SEND_CHATGPT','target_app':'chrome','cdp_port':args.cdp_port,
                   'exchange_id':'acceptance-'+str(i)+'-'+args.url.rsplit('/',1)[-1],
                   'text':'Test round '+str(i)+': reply exactly ACK ROUND '+str(i),
                   'timeout':30}])
 actions.append({'action':'OBSERVE_CHATGPT','target_app':'chrome','cdp_port':args.cdp_port,'timeout':25})
 existing=[t for t in store.list() if t.get('current_stage')=='ChatGPT acceptance']
 if existing:
  if len(existing)!=1:raise SystemExit('BLOCKED: ambiguous prior acceptance checkpoints')
  task=existing[0];tid=task['id']
  if task['status'] in ('needs_review','failed','stopped'):raise SystemExit('BLOCKED: prior send requires manual reconciliation; no retry')
  if task['status']=='completed':
   print(json.dumps({'status':'ALREADY_COMPLETED','task_id':tid}));return
  if task['status'] not in ('paused','waiting'):raise SystemExit('BLOCKED: prior task state '+task['status'])
  if task['status']=='paused':store.resume(tid)
 else:
  tid=store.submit(actions,stage='ChatGPT acceptance',context=target)
 store.claim(tid)
 deadline=time.monotonic()+args.timeout
 while time.monotonic()<deadline:
  task=store.get(tid)
  if task['status']=='completed':
   print(json.dumps({'status':'PASS','rounds':2,'task_id':tid,'checkpoint':str(home/'agent.sqlite3')}));return
  index=task['next_action'];action=task['actions'][index]
  if not store.mark_action(tid,index):raise SystemExit('BLOCKED: checkpoint not runnable')
  result=executor.run(tid,action,task['context'],threading.Event())
  if result['success'] and action['action']=='OBSERVE_CHATGPT' and not result['result'].get('completion_verified'):
   store.pending_action(tid,index,result)
   time.sleep(2)
   continue
  if result['success'] and action['action']=='OBSERVE_CHATGPT':
   expected='ACK ROUND '+str(index//2) if index>0 else None
   if expected and expected not in result['result'].get('lastAssistant',''):
    store.pending_action(tid,index,result)
    time.sleep(2)
    continue
  if not result['success'] and action['action']=='SEND_CHATGPT':result['status']='needs_review'
  store.complete_action(tid,index,result)
  if not result['success']:raise SystemExit('BLOCKED: '+str(result['error'])+'; checkpoint retained, do not resend')
 raise SystemExit('BLOCKED: timeout; checkpoint retained')

if __name__=='__main__':main()
