"""Phase 2-only simulation. No Studio, ChatGPT, or image generation."""
import threading
class SimulationWorker:
 def __init__(self,manager,interval=3):
  self.manager=manager; self.interval=interval; self.stop_event=threading.Event(); self.thread=threading.Thread(target=self._loop,daemon=True); self.thread.start()
 def _loop(self):
  while not self.stop_event.wait(self.interval):
   try:
    p=next((x for x in self.manager.list() if x['status']=='running' and x.get('execution_mode','simulation')=='simulation'),None)
    if p:
     done=min(p['sim_done']+1,p['sim_total']); self.manager.progress(p['id'],done,p['sim_total'])
     if done==p['sim_total'] and self.manager.get(p['id'])['status']=='running': self.manager.finish(p['id'])
   except (ValueError,RuntimeError): pass
 def close(self): self.stop_event.set(); self.thread.join()
