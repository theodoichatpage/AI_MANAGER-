import json, threading, time
from pathlib import Path
class AutomationLog:
 def __init__(self,home,store):self.path=Path(home)/'automation.jsonl';self.store=store;self.lock=threading.Lock()
 def write(self,task,action,result=None,message=None):
  # Do not write typed text, selector text, tokens or clipboard contents.
  row={'timestamp':time.time(),'project':task.get('project'),'task_id':task.get('id'),'application':task.get('target_app'),'window':task.get('target_window'),'action':action,'result':(result or {}).get('status'),'duration':(result or {}).get('duration'),'retry':(result or {}).get('retry_count',0),'error':(result or {}).get('error'),'message':message}
  context=dict(task.get('context',{}));context.update((result or {}).get('result',{}).get('context',{}))
  row.update({k:context.get(k) for k in ('workflow_id','subtask_id','work_status','studio_current_part','studio_current_scene','operation_id','result_path')})
  with self.lock:
   self.path.parent.mkdir(parents=True,exist_ok=True)
   with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
   self.store.event(row)
