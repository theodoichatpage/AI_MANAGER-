import json, sqlite3, threading, time, uuid
from pathlib import Path

ACTIONS={'LIST_EDGE_PROFILES','OPEN_APP','CLOSE_APP','RESTART_APP','LIST_PROCESSES','LIST_WINDOWS','CHECK_PROCESS','FIND_WINDOW','WAIT_WINDOW','FOCUS_WINDOW','RESTORE','MAXIMIZE','MINIMIZE','OPEN_URL','NEW_TAB','CLOSE_TAB','SWITCH_TAB','REFRESH','READ_URL','WAIT_PAGE','FIND_ELEMENT','READ_ELEMENT','CLICK','DOUBLE_CLICK','RIGHT_CLICK','TYPE_TEXT','HOTKEY','SCROLL','DRAG_DROP','WAIT','WAIT_ELEMENT','WAIT_ELEMENT_GONE','SCREENSHOT','OPEN_TEST_WINDOW'}
UNSAFE={'CLICK','DOUBLE_CLICK','RIGHT_CLICK','TYPE_TEXT','HOTKEY','SCROLL','DRAG_DROP','CLOSE_APP','RESTART_APP','NEW_TAB','CLOSE_TAB','SWITCH_TAB','REFRESH','OPEN_URL'}

class TaskStore:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
  self.db=sqlite3.connect(self.path,check_same_thread=False);self.db.row_factory=sqlite3.Row
  self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
  self.db.executescript('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, at REAL, payload TEXT);')
  with self.lock,self.db:
   for t in self.list():
    if t['status']=='running':
     a=t['actions'][t['next_action']] if t['next_action']<len(t['actions']) else {}
     t['status']='needs_review' if t.get('in_flight') and a.get('action') in UNSAFE else 'paused'
     t['error']='Agent/Manager đã đóng. Kiểm tra Windows rồi Tiếp tục; thao tác có thể đã xảy ra.' if t['status']=='needs_review' else 'Khôi phục checkpoint, chờ Tiếp tục'
     t['in_flight']=False;self.save(t)
 def close(self):self.db.close()
 def save(self,t):
  t['updated_at']=time.time();self.db.execute('INSERT OR REPLACE INTO tasks VALUES(?,?)',(t['id'],json.dumps(t,ensure_ascii=False)))
 def submit(self,actions,project=None,stage='Automation',context=None,initial_status='waiting'):
  if initial_status not in ('waiting','held'):raise ValueError('Initial status không hợp lệ')
  if not isinstance(actions,list) or not 1<=len(actions)<=100:raise ValueError('Workflow cần 1–100 action')
  for a in actions:
   if not isinstance(a,dict) or a.get('action') not in ACTIONS:raise ValueError('Action không được hỗ trợ')
   if not 0<float(a.get('timeout',30))<=300:raise ValueError('Timeout phải từ 0 đến 300 giây')
   if not 0<=int(a.get('retries',0))<=3:raise ValueError('Retry tối đa 3')
  t={'id':str(uuid.uuid4()),'task_id':None,'project':project,'current_project':project,'current_stage':stage,'current_part':0,'current_scene':0,'status':initial_status,'actions':actions,'next_action':0,'current_action':None,'target_app':None,'target_window':None,'retry_count':0,'last_successful_action':None,'last_successful_checkpoint':None,'context':context or {},'results':[],'in_flight':False,'error':None,'created_at':time.time()};t['task_id']=t['id']
  with self.lock,self.db:self.save(t)
  return t['id']
 def list(self):
  with self.lock:return [json.loads(r['payload']) for r in self.db.execute('SELECT payload FROM tasks ORDER BY rowid')]
 def get(self,tid):
  with self.lock:
   row=self.db.execute('SELECT payload FROM tasks WHERE id=?',(tid,)).fetchone()
   if not row:raise ValueError('Không tìm thấy task')
   return json.loads(row['payload'])
 def claim(self,tid):
  with self.lock,self.db:
   if any(t['status']=='running' for t in self.list()):raise ValueError('Agent đang xử lý task khác')
   t=self.get(tid)
   if t['status'] not in ('waiting','paused','failed','stopped'):raise ValueError('Task cần kiểm tra thủ công trước khi tiếp tục')
   t.update(status='running',error=None);self.save(t)
 def mark_action(self,tid,index,retry=0):
  with self.lock,self.db:
   t=self.get(tid)
   if t['status']!='running':return False
   a=t['actions'][index];t.update(current_action=a['action'],target_app=a.get('target_app') or t['context'].get('target_app'),target_window=t['context'].get('hwnd'),retry_count=retry,in_flight=True,action_started_at=time.time());self.save(t);return True
 def complete_action(self,tid,index,result):
  with self.lock,self.db:
   t=self.get(tid)
   if t['status']!='running':return
   if index!=t['next_action']:raise ValueError('Checkpoint không khớp')
   t['results'].append(result);t['in_flight']=False
   if result.get('success'):
    t['next_action']=index+1;t['last_successful_action']=t['current_action'];t['last_successful_checkpoint']=time.time()
    t['context'].update(result.get('result',{}).get('context',{}))
    if t['next_action']==len(t['actions']):t['status']='completed'
   else:t['status']=result.get('status','failed');t['error']=result.get('error')
   self.save(t)
 def stop_all(self):
  with self.lock,self.db:
   for t in self.list():
    if t['status'] in ('waiting','running','paused'):
     t['status']='needs_review' if t.get('in_flight') and t.get('current_action') in UNSAFE else 'stopped';t['error']='Đã dừng. Thao tác đang thực hiện cần kiểm tra trước khi chạy lại.';self.save(t)
 def resume(self,tid,reviewed=False):
  with self.lock,self.db:
   t=self.get(tid)
   if t['status']=='needs_review':
    if not reviewed:raise ValueError('Cần xác nhận đã kiểm tra tác động của action trước')
    raise ValueError('Không tự chạy lại thao tác chưa rõ kết quả. Tạo workflow mới từ bước cần thực hiện.')
   if t['status'] not in ('paused','failed','stopped'):raise ValueError('Task không ở trạng thái có thể tiếp tục')
   t.update(status='waiting',in_flight=False);self.save(t)
 def event(self,data):
  with self.lock,self.db:self.db.execute('INSERT INTO events(at,payload) VALUES(?,?)',(time.time(),json.dumps(data,ensure_ascii=False)))
 def logs(self):
  with self.lock:return [dict(json.loads(r['payload']),timestamp=r['at']) for r in self.db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 200')]
