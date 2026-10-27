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
 def _running(self): return self.db.execute("SELECT id FROM projects WHERE status='running'").fetchone()
 def _account(self,p): return p['elapsed_time'] + max(0,time.time()-p['running_since']) if p['running_since'] else p['elapsed_time']
 def _launch(self,p):
  if self._running(): raise ValueError('Một dự án khác đang chạy')
  self._set(p['id'],status='running',current_stage='Mô phỏng',started_at=p['started_at'] or now(),running_since=time.time()); self._log(p['id'],'Bắt đầu hoặc tiếp tục mô phỏng')
 def _next(self):
  if not self._enabled() or self._running(): return
  # A paused project blocks automatic advancement until explicitly resumed/stopped.
  if self.db.execute("SELECT 1 FROM projects WHERE status='paused'").fetchone(): return
  p=self.db.execute("SELECT * FROM projects WHERE status='waiting' ORDER BY position LIMIT 1").fetchone()
  if p: self._launch(dict(p))
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
