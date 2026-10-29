"""Coordinator: existing project queue owns scheduling of attached agent workflows."""
import threading,json
from pathlib import Path

class QueueBridge:
 def __init__(self,queue,agent):
  self.queue=queue;self.agent=agent;self.stop_event=threading.Event();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
 def loop(self):
  while not self.stop_event.wait(.5):
   try:
    with self.queue.lock:
     p=next((p for p in self.queue.list() if p['status']=='running' and p.get('execution_mode')=='automation'),None)
     if not p:continue
     state=self.agent.snapshot()
     if not state.get('online'):
      self.queue.pause(p['id']);continue
     task=next((t for t in state.get('tasks',[]) if t['id']==p.get('automation_task_id')),None)
     if not task:continue
     if task['status'] in ('held','paused','stopped'):
      self.agent.request('/release',{'task_id':task['id']},timeout=1);continue
     stage=task.get('context',{}).get('studio_stage') or task.get('current_action') or task.get('current_stage','Automation')
     if task.get('context',{}).get('studio_project_id'):
      c=task['context'];self.queue.studio_progress(p['id'],c.get('studio_total_parts',0),c.get('studio_completed_parts',0),c.get('studio_total_scenes',0))
     if task['status']=='needs_review' and task.get('context',{}).get('studio_project_id'):
      self.queue.pause(p['id']);self.agent.stop();continue
     if task['status']=='running' or task['status'] in ('completed','failed','needs_review','timeout'):
      self.queue.automation_update(p['id'],task['next_action'],len(task['actions']),stage,task['status'],task.get('error'))
      # Mirror a project-local checkpoint without touching project.json or scene data.
      path=Path(p['folder'])/'automation_checkpoint.json';tmp=path.with_suffix('.tmp')
      checkpoint={k:task.get(k) for k in ('current_project','current_stage','current_action','target_app','target_window','current_part','current_scene','retry_count','last_successful_action','last_successful_checkpoint','error','updated_at','next_action','status')}
      checkpoint.update(task.get('context',{}));checkpoint['status']=task['status']
      tmp.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(path)
   except (ValueError,OSError,RuntimeError):continue
 def close(self):
  self.stop_event.set();self.thread.join(3)
  if self.thread.is_alive():raise RuntimeError('Queue bridge chưa dừng; không đóng database đang dùng')
