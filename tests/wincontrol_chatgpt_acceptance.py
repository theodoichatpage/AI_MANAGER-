"""Windows-only acceptance: two ChatGPT turns using existing ActionExecutor/TaskStore.
Requires a dedicated, already-open ChatGPT conversation with an assistant reply.
Run from repo root: python -m tests.wincontrol_chatgpt_acceptance --url https://chatgpt.com/c/ID
Never use a conversation containing unsaved work. No reload or navigation.
"""
import argparse
import hashlib
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from automation_agent.action_executor import ActionExecutor
from automation_agent.task_store import TaskStore
from automation_agent import window_manager as wm

def acceptance_actions(url):
 actions=[]
 for i in (1,2):
  actions.extend([{'action':'OBSERVE_CHATGPT','target_app':'chrome','timeout':25},
   {'action':'SEND_CHATGPT','target_app':'chrome','exchange_id':'acceptance-'+str(i)+'-'+url.rsplit('/',1)[-1],
    'text':'WINCONTROL TEST ROUND '+str(i),'timeout':30}])
 actions.append({'action':'OBSERVE_CHATGPT','target_app':'chrome','timeout':25})
 return actions

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--url',required=True,help='Dedicated test conversation URL, not a development chat')
 parser.add_argument('--home',default=None,help='Existing isolated acceptance checkpoint folder')
 parser.add_argument('--mcp-config',required=True,help='JSON from existing owned Chrome MCP profile')
 parser.add_argument('--timeout',type=int,default=180)
 parser.add_argument('--hwnd',type=int,default=None)
 args=parser.parse_args()
 if sys.platform!='win32':raise SystemExit('BLOCKED: requires real Windows Chrome')
 if not args.url.startswith('https://chatgpt.com/c/'):raise SystemExit('BLOCKED: expected dedicated ChatGPT conversation URL')
 home=Path(args.home) if args.home else Path(tempfile.gettempdir())/'wincontrol-chatgpt-acceptance'
 home.mkdir(parents=True,exist_ok=True)
 store=TaskStore(home/'agent.sqlite3')
 executor=ActionExecutor(home)
 config=json.loads(Path(args.mcp_config).read_text(encoding='utf-8'))
 target={'target_app':'chrome','expected_url':args.url,'chrome_mcp_config':config}
 if args.hwnd is not None:
  windows=[w for w in wm.windows('chrome') if w['hwnd']==args.hwnd]
  if len(windows)!=1:raise SystemExit('BLOCKED: selected Chrome window is unavailable')
  target.update(windows[0])
 if config.get('page_url')!=args.url:raise SystemExit('BLOCKED: exact owned test conversation required')
 actions=acceptance_actions(args.url)
 existing=[t for t in store.list() if t.get('current_stage')=='ChatGPT acceptance']
 already_completed=False
 if existing:
  if len(existing)!=1:raise SystemExit('BLOCKED: ambiguous prior acceptance checkpoints')
  task=existing[0];tid=task['id']
  if task['actions']!=actions or task['context'].get('expected_url')!=args.url:raise SystemExit('BLOCKED: checkpoint scope or prompts differ; no resend')
  safe_observe_failure=(task['status']=='failed' and task['next_action']==0 and not task['in_flight'] and
   len(task['results'])==1 and task['results'][0].get('action')=='OBSERVE_CHATGPT' and not task['results'][0].get('success'))
  if task['status'] in ('needs_review','stopped') or (task['status']=='failed' and not safe_observe_failure):
   raise SystemExit('BLOCKED: prior send requires manual reconciliation; no retry')
  if task['status']=='completed':
   already_completed=True
  if not already_completed and task['status'] not in ('paused','waiting') and not safe_observe_failure:
   raise SystemExit('BLOCKED: prior task state '+task['status'])
  if task['status']=='paused' or safe_observe_failure:store.resume(tid)
 else:
  tid=store.submit(actions,stage='ChatGPT acceptance',context=target)
 if not already_completed:store.claim(tid)
 deadline=time.monotonic()+args.timeout
 while time.monotonic()<deadline:
  task=store.get(tid)
  if task['status']=='completed':
   rows=task['results']
   if len(rows)==6 and rows[0].get('action')=='OBSERVE_CHATGPT' and not rows[0].get('success'):
    rows=rows[1:]  # A recovered read-only preflight may remain in the journal.
   if len(rows)!=5:raise SystemExit('BLOCKED: incomplete exchange evidence')
   for i in (1,2):
    receipt=rows[i*2-1]['result'];answer=rows[i*2]['result'];prompt=actions[i*2-1]['text']
    if receipt.get('submission')!='received' or receipt.get('exchange_id')!=actions[i*2-1]['exchange_id'] or receipt.get('prompt_sha256')!=hashlib.sha256(prompt.encode()).hexdigest():
     raise SystemExit('BLOCKED: invalid receipt')
    if not answer.get('completion_verified') or not answer.get('lastAssistant','').strip() or answer.get('lastUserText')!=prompt or answer.get('url')!=args.url:raise SystemExit('BLOCKED: assistant evidence mismatch')
   store.close();reopened=TaskStore(home/'agent.sqlite3')
   try:
    saved=reopened.get(tid)
    if saved['status']!='completed' or saved['in_flight'] or saved['next_action']!=5:raise SystemExit('BLOCKED: checkpoint readback failed')
    report={'status':'WINCONTROL_CHATGPT_LIVE_PASS','rounds':2,'task_id':tid,'url':args.url,'checkpoint':str(home/'agent.sqlite3'),'ignored_failed_read_only_preflight':len(saved['results'])-len(rows),'results':saved['results']}
    (home/'live_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'rounds':2,'task_id':tid,'evidence':str(home/'live_acceptance.json')}));return
   finally:reopened.close()
  index=task['next_action'];action=task['actions'][index]
  if not store.mark_action(tid,index):raise SystemExit('BLOCKED: checkpoint not runnable')
  result=executor.run(tid,action,task['context'],threading.Event())
  if result['success'] and action['action']=='OBSERVE_CHATGPT' and not result['result'].get('completion_verified'):
   store.pending_action(tid,index,result)
   time.sleep(2)
   continue
  if result['success'] and action['action']=='OBSERVE_CHATGPT':
   expected=actions[index-1]['text'] if index>0 else None
   if expected and (result['result'].get('lastUserText')!=expected or result['result'].get('turnCount',0)<=task['results'][index-2]['result'].get('turnCount',0)):
    store.pending_action(tid,index,result)
    time.sleep(2)
    continue
  if not result['success'] and action['action']=='SEND_CHATGPT':result['status']='needs_review'
  store.complete_action(tid,index,result)
  if not result['success']:raise SystemExit('BLOCKED: '+str(result['error'])+'; checkpoint retained, do not resend')
 raise SystemExit('BLOCKED: timeout; checkpoint retained')

if __name__=='__main__':main()