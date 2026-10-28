import threading,time
from .task_store import TaskStore,UNSAFE
from .action_executor import ActionExecutor
from .automation_log import AutomationLog

def may_recover(action,result,count):
 return action['action'] not in UNSAFE and result.get('error_code')=='WINDOW_LOST' and count<3

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
      result=self.executor.run(tid,action,task['context'],self.cancel,retry)
      if not result.get('result',{}).get('waiting'):self.log.write(self.store.get(tid),action['action'],result)
      if result['success'] or self.cancel.is_set():break
      if retry<maximum and self.cancel.wait(min(2**retry,8)):break
     if self.cancel.is_set():break
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
     if not result['success']:break
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
