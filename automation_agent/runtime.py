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
  self.log.write({},'STOP',message='Agent và các task đã dừng')
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
     if may_recover(action,result,task.get('recoveries',0)) and task['context'].get('target_app') in ('chrome','capcut'):
      self.recover(task);continue
     if result['success'] and result.get('result',{}).get('waiting'):
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
