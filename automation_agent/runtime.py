import threading,time
from .task_store import TaskStore,UNSAFE
from .action_executor import ActionExecutor
from .automation_log import AutomationLog

def may_recover(action,result,count):
 return action['action'] not in UNSAFE and result.get('error_code')=='WINDOW_LOST' and count<3

SLOW_GRACE=900  # seconds of consecutive slow Studio rounds before the run stops for review

def slow_round(action,result,task):
 """A Studio round that ran out of time (the worker was stopped), not a failure the round reported itself."""
 name=action.get('action','')
 return result.get('status')=='timeout' and bool(task.get('context',{}).get('studio_project_id')) and name.startswith('STUDIO_') and name!='STUDIO_OPEN'

class AgentRuntime:
 def __init__(self,home,settings=None):
  self.store=TaskStore(home/'agent.sqlite3');self.executor=ActionExecutor(home,settings);self.log=AutomationLog(home,self.store)
  self.cancel=threading.Event();self.shutdown=threading.Event();self.lock=threading.RLock();self.enabled=False;self.current=None
  self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
 def start(self):
  with self.lock:
   if self.current and self.enabled and not self.cancel.is_set():return
   if self.current:raise ValueError('Đợi action hiện tại dừng hoàn toàn trước khi chạy tiếp')
   self.cancel.clear();self.enabled=True
 def cancel_task(self,tid):
  with self.lock:
   task=self.store.get(tid)
   if not task.get('context',{}).get('wincontrol_task'):raise ValueError('Chi co the huy task WinControl tu giao dien nay')
   if self.current==tid:
    self.store.stop_task(tid);self.enabled=False;self.cancel.set();self.executor.cancel()
   else:self.store.stop_task(tid)
  self.log.write(self.store.get(tid),'CANCEL',message='Huy task WinControl don le; giu nguyen cac task khac')
  return {'ok':True,'task_id':tid,'status':self.store.get(tid)['status']}
 def stop(self):
  with self.lock:
   self.enabled=False;self.cancel.set();self.store.stop_all();self.executor.cancel()
  self.suspend_ledgers('STOPPED')
  contexts=[t.get('context',{}) for t in self.store.list() if t.get('context',{}).get('studio_project_id') and t['status'] not in ('completed','held')]
  threading.Thread(target=self.release_idle_resources,args=(contexts,),daemon=True).start()
  self.log.write({},'STOP',message='Agent và các task đã dừng')
 def release_idle_resources(self,contexts):
  from .studio_workflow import StudioAPI
  from .resource_lock import StudioResource
  import json
  from pathlib import Path
  for _ in range(20):
   with self.lock:
    if self.enabled:return
    if self.current is None:break
   time.sleep(.1)
  for c in contexts:
   try:
    path=Path(c['studio_folder'])/'analysis'/('manager_'+c['studio_run_id']+'.json')
    journal=json.loads(path.read_text()) if path.exists() else {'commands':{}}
    if any(v.get('state')=='intent' for v in journal.get('commands',{}).values()):continue
    current=StudioAPI().request(c['studio_project_id'])
    if not current.get('activeJob') and not current.get('imageJobs'):
     with self.lock:
      if not self.enabled and not self.current:StudioResource(self.executor.home).release(c)
   except Exception:pass
 def pause(self):
  with self.lock:
   self.enabled=False;self.cancel.set();self.executor.cancel()
   with self.store.lock,self.store.db:
    for task in self.store.list():
     if task['status'] in ('running','waiting'):
      task['status']='needs_review' if task.get('in_flight') and task.get('current_action') in UNSAFE else 'paused';self.store.save(task)
   self.suspend_ledgers('PAUSED')
  self.log.write({},'PAUSE',message='Tạm dừng; giữ vị trí hiện tại, không chuyển dự án')
 def suspend_ledgers(self,status):
  from .work_ledger import WorkLedger
  for task in self.store.list():
   c=task.get('context',{})
   if not c.get('work_config') or task['status'] in ('completed','held'):continue
   ledger=WorkLedger(c['studio_folder'],c)
   for stage,record in list(ledger.data['tasks'].items()):
    for key,row in list(record['subtasks'].items()):
     if row['status'] not in ('COMPLETED','SKIPPED','ERROR'):ledger.update(stage,key,status)
 def loop(self):
  while not self.shutdown.wait(.1):
   with self.lock:
    if not self.enabled:continue
    candidates=[t for t in self.store.list() if t['status']=='waiting']
    if not candidates:continue
    task=candidates[0];self.store.claim(task['id']);self.current=task['id']
   tid=task['id']
   try:
    while True:
     with self.lock:
      task=self.store.get(tid)
      if self.cancel.is_set() or task['status']!='running' or task['next_action']>=len(task['actions']):break
      idx=task['next_action'];action=task['actions'][idx]
     maximum=0 if action['action'] in UNSAFE else int(action.get('retries',0))
     for retry in range(maximum+1):
      with self.lock:
       if self.cancel.is_set() or not self.store.mark_action(tid,idx,retry):break
      if not task['context'].get('studio_waiting_action'):self.log.write(self.store.get(tid),action['action'],message='Bắt đầu action' if retry==0 else 'Thử lại action')
      if action['action']=='SEND_CHATGPT' and action.get('wincontrol_feedback'):
       from .wincontrol_chat_loop import feedback_prompt
       start=int(action.get('feedback_start',idx));observed=[]
       for offset,entry in enumerate(task.get('results',[])[start:idx],start):
        prior=task['actions'][offset]
        observed.append({'action':prior.get('action'),'success':bool(entry.get('success')),'error':entry.get('error'),'result':entry.get('result')})
       action=dict(action,text=feedback_prompt(task.get('context',{}).get('wincontrol_command',''),task.get('context',{}).get('wincontrol_last_summary',''),observed))
       with self.store.lock,self.store.db:
        persisted=self.store.get(tid);persisted['actions'][idx]['text']=action['text'];self.store.save(persisted)
      result=self.executor.run(tid,action,task['context'],self.cancel,retry)
      if not result.get('result',{}).get('waiting'):self.log.write(self.store.get(tid),action['action'],result)
      if result.get('success') and action['action']=='WINCONTROL_DECIDE':
       decision=result.get('result',{}).get('decision') or {}
       if decision.get('status')=='blocked':
        result.update(success=False,status='needs_review',error=decision.get('summary') or 'ChatGPT cannot safely continue')
       elif decision.get('status')=='continue':
        from .wincontrol_chat_loop import validate_actions
        try:
         next_action=validate_actions(decision.get('actions'))[0]
         round_number=int(result.get('result',{}).get('context',{}).get('wincontrol_round',task.get('context',{}).get('wincontrol_round',0)+1))
         from .wincontrol_chat_loop import MAX_ROUNDS
         if round_number>MAX_ROUNDS:raise ValueError('WINCONTROL_MAX_ROUNDS_REACHED')
         exchange_id='wincontrol-'+tid+'-'+str(round_number)
         with self.store.lock,self.store.db:
          current=self.store.get(tid)
          if current['status']!='running' or current['next_action']!=idx:raise ValueError('WINCONTROL_CHECKPOINT_MOVED')
          existing={a.get('exchange_id') for old in self.store.list() for a in old.get('actions',[]) if a.get('action')=='SEND_CHATGPT'}
          if exchange_id in existing:raise ValueError('WINCONTROL_DUPLICATE_EXCHANGE')
          feedback={'action':'SEND_CHATGPT','exchange_id':exchange_id,'wincontrol_feedback':True,'feedback_start':idx+1,'timeout':30,'retries':0}
          current['actions'][idx+1:idx+1]=[next_action,feedback,{'action':'WINCONTROL_DECIDE','timeout':30,'retries':0}]
          result.setdefault('result',{}).setdefault('context',{})['wincontrol_last_summary']=str(decision.get('summary') or '')[:1000]
          self.store.save(current)
        except Exception as exc:
         result.update(success=False,status='needs_review',error=str(exc))
      if result['success'] or self.cancel.is_set():break
      if retry<maximum and self.cancel.wait(min(2**retry,8)):break
     if self.cancel.is_set():break
     if slow_round(action,result,task):
      since=float(task['context'].get('studio_slow_since') or 0) or time.time()
      if time.time()-since<SLOW_GRACE:
       # One slow round (Studio or Supabase answering slowly) is waited out like a network drop: the next round
       # reconciles from the journal, which never re-sends a command whose outcome is unknown.
       self.store.pending_action(tid,idx,{'result':{'context':{'studio_slow_since':since,'studio_message':'Một lượt Studio chạy quá %d giây; Manager đang thử lại'%int(float(action.get('timeout',30)))}}})
       self.log.write(task,action['action'],message='Quá thời gian một lượt; thử lại');self.cancel.wait(4);continue
     if result['success'] and task['context'].get('studio_slow_since'):
      result.setdefault('result',{}).setdefault('context',{})['studio_slow_since']=None
     if task['context'].get('studio_project_id') and result.get('error_code')=='WINDOW_LOST' and task.get('recoveries',0)<2:
      self.recover_studio(task);continue
     if may_recover(action,result,task.get('recoveries',0)) and task['context'].get('target_app') in ('chrome','capcut'):
      self.recover(task);continue
     if result['success'] and result.get('result',{}).get('waiting'):
      previous=task.get('context',{});fresh=result.get('result',{}).get('context',{})
      if fresh.get('subtask_id')!=previous.get('subtask_id') or fresh.get('work_status')!=previous.get('work_status'):self.log.write(task,action['action'],result,message='Cập nhật task/subtask/checkpoint')
      self.store.pending_action(tid,idx,result);self.cancel.wait(4);continue
     if result.get('error_code')=='STUDIO_REVIEW':result['status']='needs_review'
     if not result['success'] and action['action'] in UNSAFE:result['status']='needs_review'
     self.store.complete_action(tid,idx,result)
     if self.store.get(tid)['status']!='running':break
   except Exception as e:
    with self.store.lock,self.store.db:
     t=self.store.get(tid);t.update(status='needs_review',error=str(e));self.store.save(t)
    self.log.write(task,'ERROR',message='Worker lỗi; kiểm tra task trước khi tiếp tục')
   finally:self.current=None
 def recover_studio(self,task):
  tid=task['id'];context=dict(task['context']);app=context['target_app'];url=context.get('expected_url')
  if not url:
   with self.store.lock,self.store.db:
    current=self.store.get(tid);current.update(status='needs_review',error='Không có URL đã xác minh để phục hồi Studio');self.store.save(current)
   return
  for key in ('hwnd','pid','process_started','profile_proof','binding_schema'):context.pop(key,None)
  with self.store.lock,self.store.db:
   current=self.store.get(tid);current['recoveries']=current.get('recoveries',0)+1;self.store.save(current)
  steps=[{'action':name,'target_app':app,'browser_profile':context.get('browser_profile'),**({'url':url} if name=='OPEN_URL' else {})} for name in ('OPEN_APP','WAIT_WINDOW','FOCUS_WINDOW','NEW_TAB','OPEN_URL')]
  for action in steps:
   if self.cancel.is_set():return
   result=self.executor.run(tid,action,context,self.cancel);self.log.write(task,action['action'],result,message='Phục hồi đúng browser/profile/Studio nonce')
   if not result['success']:
    with self.store.lock,self.store.db:
     current=self.store.get(tid)
     if current['status']=='running':current.update(status='needs_review',error='Không phục hồi được Studio; giữ checkpoint');self.store.save(current)
    return
   context.update(result.get('result',{}).get('context',{}))
  with self.store.lock,self.store.db:
   current=self.store.get(tid)
   if current['status']=='running':current['context'].update(context);self.store.save(current)
 def recover(self,task):
  tid=task['id'];app=task['context']['target_app'];context={'target_app':app}
  with self.store.lock,self.store.db:
   t=self.store.get(tid);t['recoveries']=t.get('recoveries',0)+1;self.store.save(t)
  steps=[{'action':'OPEN_APP','target_app':app},{'action':'WAIT_WINDOW','target_app':app,'timeout':45},{'action':'FOCUS_WINDOW','target_app':app}]
  if app=='chrome' and task['context'].get('expected_url'):steps += [{'action':'OPEN_URL','target_app':app,'url':task['context']['expected_url']}]
  for a in steps:
   if self.cancel.is_set():return
   self.log.write(task,a['action'],message='Phục hồi cửa sổ bị mất')
   result=self.executor.run(tid,a,context,self.cancel)
   self.log.write(task,a['action'],result)
   if not result['success']:
    with self.store.lock,self.store.db:
     t=self.store.get(tid)
     if t['status']=='running':t.update(status='failed',error='Không phục hồi được cửa sổ: '+str(result.get('error')));self.store.save(t)
    return
   context.update(result.get('result',{}).get('context',{}))
  with self.store.lock,self.store.db:
   t=self.store.get(tid)
   if t['status']=='running':t['context'].update(context);self.store.save(t)
 def close(self):self.stop();self.shutdown.set();self.thread.join(5);self.store.close()
