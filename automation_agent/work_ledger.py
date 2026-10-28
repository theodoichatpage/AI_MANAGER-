"""Durable hierarchical task/subtask checkpoint."""
import hashlib,json,time
from pathlib import Path
STATES={'PENDING','READY','WAITING_RESOURCE','RUNNING','WAITING_STUDIO','WAITING_CHATGPT','WAITING_RESULT','SYNCING','RETRYING','PAUSED','COMPLETED','SKIPPED','ERROR','STOPPED'}
class WorkLedger:
 def __init__(self,folder,context):
  self.c=context;self.path=Path(folder)/'analysis'/('workflow_'+context['studio_run_id']+'.json')
  try:self.data=json.loads(self.path.read_text(encoding='utf8'))
  except FileNotFoundError:self.data={'workflow_id':context['studio_run_id'],'project_id':context.get('manager_project_id'),'project_name':context.get('project_name'),'studio_project_id':context['studio_project_id'],'tasks':{}}
  if self.data['studio_project_id']!=context['studio_project_id']:raise RuntimeError('Ledger sai Studio ID')
 def update(self,stage,key,status,**values):
  if status not in STATES:raise ValueError('State không hợp lệ')
  task=self.data['tasks'].setdefault(stage,{'task_id':stage,'subtasks':{}});row=task['subtasks'].setdefault(key,{'subtask_id':key,'status':'PENDING','retry_count':0})
  if row['status'] in ('COMPLETED','SKIPPED') and status not in ('COMPLETED','SKIPPED','ERROR'):raise ValueError('Không tự chạy lại subtask hoàn tất')
  op=hashlib.sha256((self.data['workflow_id']+'|'+stage+'|'+key).encode()).hexdigest()
  row.update(values,status=status,operation_id=op,updated_at=time.time())
  statuses=[r['status'] for r in task['subtasks'].values()]
  terminal={'COMPLETED','SKIPPED','ERROR'}
  task['status']=('ERROR' if 'ERROR' in statuses else 'COMPLETED' if 'COMPLETED' in statuses else 'SKIPPED') if all(x in terminal for x in statuses) else status if status not in terminal else 'RUNNING'
  self.data.update(current_task=stage,current_subtask=key,status=task['status'],updated_at=time.time(),studio_state=self.c.get('studio_state'),chatgpt_state=self.c.get('chatgpt_state'),browser=self.c.get('browser'),browser_profile=self.c.get('browser_profile'))
  if status=='COMPLETED':self.data.update(last_successful_task=stage,last_successful_subtask=key)
  from .studio_workflow import atomic
  atomic(self.path,self.data);return row
 def get(self,stage,key):return self.data['tasks'].get(stage,{}).get('subtasks',{}).get(key,{})
