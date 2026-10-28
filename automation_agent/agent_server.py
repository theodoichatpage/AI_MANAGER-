import json,os,secrets,threading,time,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .runtime import AgentRuntime

class AgentServer(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,port,token,home,settings=None):
  self.token=token;self.started=time.time();self.runtime=AgentRuntime(home,settings);self.home=home
  super().__init__(('127.0.0.1',port),AgentHandler)

class AgentHandler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def reply(self,status,body):
  b=json.dumps(body,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def authorized(self):return secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.token)
 def do_GET(self):
  if not self.authorized():return self.reply(403,{'error':'Forbidden'})
  r=self.server.runtime
  if self.path=='/state':return self.reply(200,{'online':True,'windows':sys.platform=='win32','pid':os.getpid(),'uptime':time.time()-self.server.started,'current_task':r.current,'enabled':r.enabled,'tasks':r.store.list(),'logs':r.store.logs()})
  self.reply(404,{'error':'Not found'})
 def do_POST(self):
  if not self.authorized():return self.reply(403,{'error':'Forbidden'})
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<=n<=1_000_000:raise ValueError('Payload quá lớn')
   data=json.loads(self.rfile.read(n) or b'{}');r=self.server.runtime
   if self.path=='/submit':
    tid=r.store.submit(data['actions'],data.get('project'),data.get('stage','Automation'),data.get('context'),initial_status='held' if data.get('held') else 'waiting')
    return self.reply(200,{'task_id':tid})
   if self.path=='/requeue':
    with r.store.lock,r.store.db:
     t=r.store.get(data['task_id'])
     if t['status'] not in ('failed','paused','stopped'):raise ValueError('Task cần kiểm tra thủ công hoặc chưa dừng')
     t.update(status='held',in_flight=False);r.store.save(t)
    return self.reply(200,{'ok':True})
   if self.path=='/release':
    with r.store.lock,r.store.db:
     t=r.store.get(data['task_id'])
     if t['status'] not in ('held','paused','stopped'):raise ValueError('Task không thể bắt đầu lại')
     t.update(status='waiting',in_flight=False);r.store.save(t)
    r.start();return self.reply(200,{'ok':True})
   if self.path=='/start':r.start();return self.reply(200,{'ok':True})
   if self.path=='/stop':r.stop();return self.reply(200,{'ok':True})
   if self.path=='/resume':r.store.resume(data['task_id']);r.start();return self.reply(200,{'ok':True})
   self.reply(404,{'error':'Not found'})
  except Exception as e:self.reply(400,{'error':str(e)})

def main():
 home=Path(os.environ['AI_MANAGER_AGENT_HOME']);home.mkdir(parents=True,exist_ok=True)
 settings=json.loads(os.environ.get('AI_MANAGER_AGENT_SETTINGS','{}'));parent=int(os.environ.get('AI_MANAGER_PARENT_PID','0'))
 server=AgentServer(int(os.environ['AI_MANAGER_AGENT_PORT']),os.environ['AI_MANAGER_AGENT_TOKEN'],home,settings)
 if parent:
  def parent_watch():
   while True:
    time.sleep(2)
    try:
     import psutil
     alive=psutil.Process(parent).is_running()
    except Exception:alive=False
    if not alive:
     server.runtime.stop();server.shutdown();return
  threading.Thread(target=parent_watch,daemon=True).start()
 try:server.serve_forever()
 finally:server.runtime.close();server.server_close()
if __name__=='__main__':main()
