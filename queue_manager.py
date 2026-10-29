import json, sqlite3, threading, time
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()

class QueueManager:
 def __init__(self,root):
  self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock()
  self.db=sqlite3.connect(self.root/'.ai_manager_queue.sqlite3',check_same_thread=False); self.db.row_factory=sqlite3.Row
  self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL')
  self.db.executescript('''CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, folder TEXT NOT NULL, position INTEGER NOT NULL, status TEXT NOT NULL, current_stage TEXT NOT NULL DEFAULT 'Chờ', current_part INTEGER NOT NULL DEFAULT 0, current_scene INTEGER NOT NULL DEFAULT 0, total_parts INTEGER NOT NULL DEFAULT 0, total_scenes INTEGER NOT NULL DEFAULT 0, completed_scenes INTEGER NOT NULL DEFAULT 0, failed_scenes INTEGER NOT NULL DEFAULT 0, retry_count INTEGER NOT NULL DEFAULT 0, started_at TEXT, updated_at TEXT NOT NULL, elapsed_time REAL NOT NULL DEFAULT 0, running_since REAL, sim_done INTEGER NOT NULL DEFAULT 0, sim_total INTEGER NOT NULL DEFAULT 10); CREATE TABLE IF NOT EXISTS log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, project_id TEXT, message TEXT NOT NULL); CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);''')
  self.db.execute('CREATE TABLE IF NOT EXISTS studio_links(project_id TEXT PRIMARY KEY, studio_project_id TEXT UNIQUE NOT NULL, origin TEXT NOT NULL, browser TEXT NOT NULL, profile TEXT NOT NULL)')
  columns={r[1] for r in self.db.execute('PRAGMA table_info(projects)')}
  if 'execution_mode' not in columns and self.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]:
   backup_path=self.root/'.ai_manager_queue.before_phase4.sqlite3'
   if not backup_path.exists():
    backup=sqlite3.connect(backup_path)
    try:self.db.backup(backup)
    finally:backup.close()
  if 'browser' not in columns and self.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]:
   backup_path=self.root/'.ai_manager_queue.before_edge.sqlite3'
   if not backup_path.exists():
    backup=sqlite3.connect(backup_path)
    try:self.db.backup(backup)
    finally:backup.close()
  for key,definition in [('browser',"TEXT NOT NULL DEFAULT 'chrome'"),('browser_profile',"TEXT NOT NULL DEFAULT 'Default'"),('browser_profile_name',"TEXT NOT NULL DEFAULT 'Default'"),('execution_mode',"TEXT NOT NULL DEFAULT 'simulation'"),('automation_task_id','TEXT'),('action_done','INTEGER NOT NULL DEFAULT 0'),('action_total','INTEGER NOT NULL DEFAULT 0')]:
   if key not in columns:self.db.execute('ALTER TABLE projects ADD COLUMN '+key+' '+definition)
  self.db.commit()
  with self.lock,self.db:
   for row in self.db.execute("SELECT * FROM projects WHERE status='running'").fetchall(): self._set(row['id'],status='paused',current_stage='Tạm dừng – Chờ tiếp tục',elapsed_time=self._account(dict(row)),running_since=None); self._log(row['id'],'Khôi phục sau khi đóng: tạm dừng, chờ tiếp tục')
   self._enabled(False)
 def close(self): self.db.close()
 def _enabled(self,value=None):
  if value is not None: self.db.execute("INSERT OR REPLACE INTO settings VALUES('enabled',?)",('1' if value else '0',))
  r=self.db.execute("SELECT value FROM settings WHERE key='enabled'").fetchone(); return bool(r and r[0]=='1')
 def _log(self,pid,message): self.db.execute('INSERT INTO log(at,project_id,message) VALUES(?,?,?)',(now(),pid,message))
 def logs(self):
  with self.lock: return [dict(x) for x in self.db.execute('SELECT log.*, projects.name FROM log LEFT JOIN projects ON projects.id=log.project_id ORDER BY log.id DESC LIMIT 500')]
 def _set(self,pid,**kw):
  kw['updated_at']=now(); self.db.execute('UPDATE projects SET '+','.join(k+'=?' for k in kw)+' WHERE id=?',(*kw.values(),pid))
 def add(self,p):
  with self.lock,self.db:
   if self.db.execute('SELECT 1 FROM projects WHERE id=?',(p['id'],)).fetchone(): return
   pos=self.db.execute('SELECT COALESCE(MAX(position),0)+1 FROM projects').fetchone()[0]
   self.db.execute('INSERT INTO projects(id,name,folder,position,status,updated_at) VALUES(?,?,?,?,?,?)',(p['id'],p['name'],p['folder'],pos,'waiting',now())); self._log(p['id'],'Đã thêm vào hàng đợi')
 def list(self):
  with self.lock: return [dict(x) for x in self.db.execute('SELECT * FROM projects ORDER BY position')]
 def get(self,pid):
  with self.lock:
   x=self.db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
   if not x: raise ValueError('Không tìm thấy dự án trong hàng đợi')
   return dict(x)
 def set_browser(self,pid,browser,profile,name):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status'] in ('running','paused'):raise ValueError('Dừng dự án trước khi đổi trình duyệt')
   self._set(pid,browser=browser,browser_profile=profile,browser_profile_name=name)
   path=Path(p['folder'])/'project.json'
   if path.exists():
    data=json.loads(path.read_text(encoding='utf8'));data.update(browser=browser,browser_profile=profile,browser_profile_name=name)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');temp.replace(path)
   self._log(pid,'Đã lưu trình duyệt/profile: '+browser+' / '+profile)
 def _running(self): return self.db.execute("SELECT id FROM projects WHERE status='running'").fetchone()
 def _account(self,p): return p['elapsed_time'] + max(0,time.time()-p['running_since']) if p['running_since'] else p['elapsed_time']
 def _launch(self,p):
  if self._running(): raise ValueError('Một dự án khác đang chạy')
  self._set(p['id'],status='running',current_stage='Automation' if p.get('execution_mode')=='automation' else 'Mô phỏng',started_at=p['started_at'] or now(),running_since=time.time()); self._log(p['id'],('Tiếp tục Studio workflow' if p['status']=='paused' else 'Bắt đầu Studio workflow') if p.get('execution_mode')=='automation' else ('Tiếp tục mô phỏng' if p['status']=='paused' else 'Bắt đầu mô phỏng'))
 def _next(self):
  if not self._enabled() or self._running(): return
  # A paused project blocks automatic advancement until explicitly resumed/stopped.
  if self.db.execute("SELECT 1 FROM projects WHERE status='paused'").fetchone(): return
  p=self.db.execute("SELECT * FROM projects WHERE status='waiting' ORDER BY position LIMIT 1").fetchone()
  if p: self._launch(dict(p))
 def start_selected(self,pid):
  with self.lock,self.db:
   p=self.get(pid)
   if p['execution_mode']!='automation' or not p['automation_task_id']:raise ValueError('Lưu liên kết Studio trước khi chạy')
   if p['status'] not in ('waiting','stopped'):raise ValueError('Dự án không ở trạng thái chờ/đã dừng')
   if any(x['id']!=pid and x['status'] in ('waiting','running','paused') for x in self.list()):raise ValueError('Dừng các dự án khác trong hàng đợi trước khi chạy riêng dự án này')
   self._set(pid,status='waiting');self._enabled(True);self._next()
 def order_prepared(self,ids):
  with self.lock,self.db:
   if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):raise ValueError('Thứ tự dự án không hợp lệ')
   if any(p['status'] in ('running','paused') for p in self.list()):raise ValueError('Không đổi thứ tự khi đang chạy/tạm dừng')
   for pid in ids:self.get(pid)
   for pos,pid in enumerate(ids,1):self._set(pid,position=pos)
   for pos,p in enumerate([p for p in self.list() if p['id'] not in ids],len(ids)+1):self._set(p['id'],position=pos)
 def batch(self):
  with self.lock:
   row=self.db.execute("SELECT value FROM settings WHERE key='studio_batch'").fetchone()
   return json.loads(row[0]) if row else []
 def start_batch(self,ids):
  with self.lock,self.db:
   if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):raise ValueError('Chọn danh sách dự án không trùng')
   if any(p['status'] in ('running','paused') for p in self.list()):raise ValueError('Dừng hoặc tiếp tục dự án hiện tại trước')
   selected=[self.get(pid) for pid in ids]
   invalid=[p['name'] for p in selected if p['execution_mode']!='automation' or not p['automation_task_id'] or p['status'] not in ('waiting','stopped')]
   if invalid:raise ValueError('Chưa chuẩn bị workflow hoặc trạng thái không hợp lệ: '+', '.join(invalid))
   self._enabled(False)
   for p in self.list():
    if p['id'] not in ids and p['status']=='waiting':self._set(p['id'],status='stopped')
   for pos,p in enumerate(selected,1):self._set(p['id'],position=pos,status='waiting')
   for pos,p in enumerate([p for p in self.list() if p['id'] not in ids],len(ids)+1):self._set(p['id'],position=pos)
   self.db.execute("INSERT OR REPLACE INTO settings VALUES('studio_batch',?)",(json.dumps(ids),));self._enabled(True);self._next()
 def start_all(self):
  with self.lock,self.db:
   self._enabled(True)
   self.db.execute("UPDATE projects SET status='waiting', current_stage='Chờ', updated_at=? WHERE status='stopped'",(now(),)); self._next()
 def pause(self,pid):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status']!='running': raise ValueError('Chỉ có thể tạm dừng dự án đang chạy')
   self._set(pid,status='paused',current_stage='Tạm dừng',elapsed_time=self._account(p),running_since=None); self._enabled(False); self._log(pid,'Tạm dừng')
 def resume(self,pid):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status']!='paused': raise ValueError('Dự án không ở trạng thái tạm dừng')
   self._launch(p); self._enabled(True)
 def stop(self,pid):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status'] not in ('running','paused','waiting'): raise ValueError('Không thể dừng dự án này')
   self._set(pid,status='stopped',current_stage='Đã dừng',elapsed_time=self._account(p),running_since=None); self._log(pid,'Đã dừng'); self._next()
 def stop_all(self):
  with self.lock,self.db:
   self._enabled(False)
   for p in self.list():
    if p['status'] in ('running','paused','waiting'): self._set(p['id'],status='stopped',current_stage='Đã dừng',elapsed_time=self._account(p),running_since=None); self._log(p['id'],'Dừng tất cả')
 def progress(self,pid,done,total):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status']!='running': return
   if total<1 or done<p['sim_done'] or done>total: raise ValueError('Tiến độ không hợp lệ')
   self._set(pid,sim_done=done,sim_total=total,current_scene=done,completed_scenes=done,total_scenes=total,current_stage='Mô phỏng')
 def finish(self,pid):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status']!='running': raise ValueError('Dự án không chạy')
   self._set(pid,status='completed',current_stage='Mô phỏng hoàn tất',sim_done=p['sim_total'],current_scene=p['sim_total'],completed_scenes=p['sim_total'],total_scenes=p['sim_total'],elapsed_time=self._account(p),running_since=None); self._log(pid,'Mô phỏng hoàn tất'); self._next()
 def fail(self,pid,message):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status']!='running': raise ValueError('Dự án không chạy')
   self._set(pid,status='failed',current_stage='Mô phỏng lỗi',elapsed_time=self._account(p),running_since=None); self._log(pid,'Lỗi mô phỏng: '+message); self._next()
 def retry_errors(self,pid=None):
  with self.lock,self.db:
   for p in self.list():
    if p['status']=='failed' and (pid is None or p['id']==pid): self._set(p['id'],status='waiting',current_stage='Chờ chạy lại',retry_count=p['retry_count']+1); self._log(p['id'],'Đã đưa lỗi trở lại hàng đợi')
   self._next()
 def move(self,pid,direction):
  with self.lock,self.db:
   items=self.list(); idx=next((i for i,p in enumerate(items) if p['id']==pid),-1)
   if idx<0: raise ValueError('Không tìm thấy dự án')
   j=idx+direction
   if direction not in (-1,1) or j<0 or j>=len(items): raise ValueError('Không thể di chuyển')
   if items[idx]['status']!='waiting' or items[j]['status']!='waiting': raise ValueError('Chỉ đổi thứ tự giữa các dự án đang chờ')
   self._set(items[idx]['id'],position=items[j]['position']); self._set(items[j]['id'],position=items[idx]['position']); self._log(pid,'Đã thay đổi thứ tự hàng đợi')

 def bind_studio(self,pid,sid,origin,browser,profile):
  with self.lock,self.db:
   if self.get(pid)['status'] in ('running','paused'):raise ValueError('Dừng dự án trước khi đổi liên kết Studio')
   other=self.db.execute('SELECT project_id FROM studio_links WHERE studio_project_id=?',(sid,)).fetchone()
   if other and other[0]!=pid:raise ValueError('Studio ID đã được gán cho dự án khác')
   self.db.execute('INSERT OR REPLACE INTO studio_links VALUES(?,?,?,?,?)',(pid,sid,origin,browser,profile))
 def studio_rename(self,pid,name):
  with self.lock,self.db:
   if self.get(pid)['name']!=name:self._set(pid,name=name)
 def studio_progress(self,pid,total,done,scenes):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status']!='running':return
   self._set(pid,total_parts=total,current_part=done,total_scenes=scenes,completed_scenes=scenes)
 def attach_automation(self,pid,tid):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status'] in ('running','paused'):raise ValueError('Dừng dự án trước khi gắn workflow')
   self._set(pid,execution_mode='automation',automation_task_id=tid,status='waiting',current_stage='Chờ Automation',action_done=0,action_total=0)
   self._log(pid,'Đã gắn workflow Windows Agent '+tid)
 def automation_update(self,pid,done,total,stage,status,error=None):
  with self.lock,self.db:
   p=self.get(pid)
   if p['status']!='running' or p['execution_mode']!='automation':return
   updates={'action_done':done,'action_total':total,'current_stage':stage}
   if status in ('completed','failed','needs_review','timeout'):
    updates.update(status='completed' if status=='completed' else 'failed',elapsed_time=self._account(p),running_since=None)
    self._log(pid,'Automation '+status+(': '+str(error) if error else ''))
   self._set(pid,**updates)
   if status in ('completed','failed','needs_review','timeout'):self._next()
