import json, os, re, sys, tempfile, threading, time, unicodedata, uuid, webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from queue_manager import QueueManager
from simulation_worker import SimulationWorker
from studio_monitor import StudioMonitor

VERSION = '0.1.12'
DOWNLOAD_URL = 'https://github.com/theodoichatpage/AI_MANAGER-/archive/refs/heads/phase3-status-fix-preview.zip'
BASE = Path(os.environ.get('AI_MANAGER_HOME', Path.home() / '.ai_manager'))
CONFIG = BASE / 'config.json'
LOCK = threading.RLock()

class StudioPresence:
    def __init__(self, ttl=15): self.ttl=ttl; self.lock=threading.RLock(); self.tabs={}
    def update(self, data):
        session=str(data.get('sessionId','')).strip(); tab=str(data.get('tabId','')).strip()
        if not session or not tab: return
        with self.lock:
            if data.get('event')=='close': self.tabs.pop((session,tab),None); return
            self.tabs[(session,tab)]={'session_id':session,'tab_id':tab,'chat_connected':bool(data.get('chatReady')),
                'project_name':str(data.get('projectName','')).strip() or None,'at':time.time()}
    def snapshot(self, session_id=None):
        now=time.time()
        with self.lock:
            self.tabs={k:v for k,v in self.tabs.items() if now-v['at']<=self.ttl}
            matching=[v for v in self.tabs.values() if session_id is None or v['session_id']==session_id]
            if not matching: return {'studio_tab_open':False,'chat_connected':False,'session_id':None,'project_name':None,'last_seen':None}
            latest=max(matching,key=lambda x:x['at'])
            return {'studio_tab_open':True,'chat_connected':any(v['chat_connected'] for v in matching),
                'session_id':latest['session_id'],'project_name':latest.get('project_name'),'last_seen':latest['at']}
PRESENCE=StudioPresence()

def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True); fd, name = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def config():
    if CONFIG.exists(): return json.loads(CONFIG.read_text(encoding='utf-8'))
    return {'root': str(Path.home() / 'VIDEO_PROJECTS')}
def slug(name):
    name=unicodedata.normalize('NFKD',name.replace('đ','d').replace('Đ','D')).encode('ascii','ignore').decode(); name=re.sub(r'[^A-Za-z0-9]+','_',name).strip('_')[:70]; return name or 'Du_An'
def projects():
    root=Path(config()['root']); result=[]
    if root.exists():
        for p in sorted(root.glob('*/project.json')):
            try:
                data=json.loads(p.read_text(encoding='utf-8'))
                if data.get('schema')=='ai-manager-1': result.append(data)
            except (OSError,ValueError): continue
    return result
def create_project(name, script, test_key=None):
    name=name.strip() or next((x.strip() for x in script.splitlines() if x.strip()),'')[:100]
    if not name: raise ValueError('Nhập tên dự án hoặc kịch bản.')
    root=Path(config()['root']); root.mkdir(parents=True,exist_ok=True); used=[int(m.group(1)) for p in root.iterdir() if (m:=re.match(r'^(\d+)_',p.name))]; n=max(used,default=0)+1
    while True:
        folder=root/f'{n:03d}_{slug(name)}'
        try: folder.mkdir(); break
        except FileExistsError: n+=1
    now=datetime.now(timezone.utc).isoformat(); project={'schema':'ai-manager-1','id':str(uuid.uuid4()),'name':name,'folder':str(folder),'created_at':now,'status':'Chưa bắt đầu','script':script,'parts':0,'scenes':0,'images':0,'errors':0}
    if test_key: project['simulation_test_key']=test_key
    for d in ('analysis','scenes','prompts','images','logs'): (folder/d).mkdir()
    atomic(folder/'project.json',project); (folder/'logs'/'activity.log').write_text(f'{now} – Đã tạo dự án\n',encoding='utf-8'); return project

MANAGER=None; WORKER=None; STUDIO=StudioMonitor(); STUDIO_STOP=threading.Event(); threading.Thread(target=STUDIO.run,args=(STUDIO_STOP,),daemon=True).start()
def manager():
    global MANAGER,WORKER
    if MANAGER is None:
        MANAGER=QueueManager(Path(config()['root']))
        for p in projects(): MANAGER.add(p)
        WORKER=SimulationWorker(MANAGER)
    return MANAGER

def synchronized_state(q):
    ps=projects(); qs=q.list(); studio=STUDIO.snapshot(); data=studio.get('data') or {}; presence=PRESENCE.snapshot(data.get('project_id') or '')
    studio=dict(studio); studio['presence']=presence
    if presence['studio_tab_open']:
        data=dict(data); data['studio_tab_open']=True; data['chat_connected']=presence['chat_connected']; data['project_id']=presence['session_id'] or data.get('project_id')
        if presence.get('project_name'): data['project_name']=presence['project_name']
        studio=dict(studio); studio['data']=data; studio['presence']=presence
        if studio.get('status') in ('unconfigured','connecting','lost','error'): studio['status']='connected'
    studio_name=data.get('project_name')
    if studio_name:
        candidates=[x for x in qs if x.get('status') in ('running','paused') and not x.get('simulation_test_key')]; target=candidates[0].get('id') if candidates else None
        if target is None:
            real=[p for p in ps if not p.get('simulation_test_key')]
            if len(real)==1: target=real[0].get('id')
        if target:
            for p in ps:
                if p.get('id')==target: p['name']=studio_name; p['studio_project_id']=data.get('project_id')
            for item in qs:
                if item.get('id')==target: item['name']=studio_name
    return {'version':VERSION,'config':config(),'projects':ps,'queue':qs,'logs':q.logs(),'studio':studio}

def render_index():
    page=(Path(__file__).parent/'index.html').read_text(encoding='utf-8')
    page=re.sub(r'Phiên bản\s+[^<·]+\s+\(v[^)]+\)',f'Phiên bản {VERSION} (v{VERSION})',page, count=1)
    marker='<div id="rootError" style="color:#d33"></div>'; download=(f'<div class="notice" style="margin-top:16px"><b>Bản Windows hiện tại: v{VERSION}</b><br><span class="muted">Tải gói mới nhất, giải nén thư mục thành AI_MANAGER_v{VERSION} rồi chạy MO_AI_MANAGER.bat.</span><p><a class="btn primary" href="{DOWNLOAD_URL}" target="_blank" rel="noopener" download="AI_MANAGER_v{VERSION}.zip">⬇ Tải AI_MANAGER_v{VERSION}.zip</a></p></div>')
    if marker in page: page=page.replace(marker,marker+download,1)
    return page

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,data,kind='application/json; charset=utf-8',cors=False):
        body=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        if cors:
            self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Methods','POST, OPTIONS'); self.send_header('Access-Control-Allow-Headers','Content-Type, Access-Control-Request-Private-Network'); self.send_header('Access-Control-Allow-Private-Network','true')
        self.end_headers(); self.wfile.write(body)
    def do_OPTIONS(self):
        if urlparse(self.path).path=='/api/studio-presence': return self.send(204,b'',cors=True)
        self.send(404,{'error':'Không tìm thấy'})
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/': return self.send(200,render_index().encode(),'text/html; charset=utf-8')
        if path=='/api/state':
            with LOCK: return self.send(200,synchronized_state(manager()))
        if path=='/api/studio-presence': return self.send(200,PRESENCE.snapshot(),cors=True)
        self.send(404,{'error':'Không tìm thấy'})
    def do_POST(self):
        try:
            path=urlparse(self.path).path; length=int(self.headers.get('Content-Length','0'))
            if length>5_000_000: raise ValueError('Dữ liệu quá lớn')
            data=json.loads(self.rfile.read(length) or b'{}')
            if path=='/api/studio-presence': PRESENCE.update(data); return self.send(200,{'ok':True,'presence':PRESENCE.snapshot()},cors=True)
            if self.headers.get('Origin') not in ('http://127.0.0.1:8765','http://localhost:8765'): raise ValueError('Nguồn truy cập không hợp lệ')
            with LOCK:
                if path=='/api/studio':
                    if data.get('action')=='disconnect': STUDIO.disconnect()
                    elif data.get('action')=='connect': STUDIO.configure(data.get('code','')); threading.Thread(target=STUDIO.poll,daemon=True).start()
                    else: raise ValueError('Lệnh không hợp lệ')
                    return self.send(200,{'ok':True})
                if path=='/api/test-projects':
                    existing={p.get('simulation_test_key'):p for p in projects() if p.get('simulation_test_key')}; result=[]
                    for key in ('A','B','C'):
                        p=existing.get(key) or create_project('TEST PROJECT '+key,'',test_key=key); manager().add(p); result.append(p)
                    return self.send(200,{'projects':result})
                if path=='/api/project': p=create_project(str(data.get('name','')),str(data.get('script',''))); manager().add(p); return self.send(201,p)
                if path=='/api/root':
                    global MANAGER,WORKER
                    if MANAGER and any(p['status'] in ('running','paused') for p in MANAGER.list()): raise ValueError('Dừng hàng đợi trước khi đổi thư mục.')
                    root=Path(str(data.get('root','')).strip()).expanduser()
                    if not root.is_absolute(): raise ValueError('Đường dẫn phải là đường dẫn tuyệt đối.')
                    root.mkdir(parents=True,exist_ok=True); atomic(CONFIG,{'root':str(root.resolve())})
                    if WORKER: WORKER.close(); WORKER=None
                    if MANAGER: MANAGER.close(); MANAGER=None
                    return self.send(200,config())
                if path=='/api/queue':
                    q=manager(); action=data.get('action'); pid=str(data.get('id',''))
                    if action=='start': q.start_all()
                    elif action=='pause': q.pause(pid or next((p['id'] for p in q.list() if p['status']=='running'),''))
                    elif action=='resume': q.resume(pid or next((p['id'] for p in q.list() if p['status']=='paused'),''))
                    elif action=='stop_all': q.stop_all()
                    elif action=='stop': q.stop(pid)
                    elif action=='retry': q.retry_errors(pid or None)
                    elif action=='move': q.move(pid,int(data.get('direction',0)))
                    elif action=='simulate_complete': q.finish(pid)
                    elif action=='simulate_fail': q.fail(pid,'Lỗi được mô phỏng')
                    else: raise ValueError('Lệnh không hợp lệ')
                    return self.send(200,{'ok':True})
            self.send(404,{'error':'Không tìm thấy'})
        except (ValueError,OSError,TypeError,json.JSONDecodeError) as e: self.send(400,{'error':str(e)})

if __name__=='__main__':
    try: server=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    except OSError: print('Cong 8765 dang duoc su dung. Hay dong cua so AI MANAGER cu, sau do mo lai file nay.',flush=True); sys.exit(1)
    print(f'AI MANAGER v{VERSION}: http://127.0.0.1:8765',flush=True)
    if '--no-browser' not in sys.argv: threading.Timer(.5,lambda:webbrowser.open('http://127.0.0.1:8765')).start()
    server.serve_forever()

