"""Thin integration layer. Dashboard handlers never execute Windows UI calls."""
import json,re,threading
from pathlib import Path
from .agent_client import AgentClient
from .queue_bridge import QueueBridge
from .workflows import workflow

class AutomationService:
 def __init__(self,home,queue_getter):
  self.home=Path(home);self.queue_getter=queue_getter;self.client=AgentClient(self.home);self.client.start_supervisor();self.bridge=None
 def ensure_bridge(self):
  if self.bridge is None:self.bridge=QueueBridge(self.queue_getter(),self.client)
 def reset_bridge(self):
  if self.bridge:self.bridge.close();self.bridge=None
 def snapshot(self):return self.client.snapshot()
 def control(self,data):
  cmd=data.get('command')
  if cmd=='studio_attach':
   from .studio_workflow import workflow as studio_workflow,validate_url
   q=self.queue_getter();p=q.get(data['project'])
   if p['status'] in ('running','paused'):raise ValueError('Dừng dự án trước khi gắn Studio')
   browser=data.get('browser','edge');profile=data.get('browser_profile') or 'Default'
   if browser=='chrome' and profile!='Default':raise ValueError('Bản này chỉ xác minh profile Edge; Chrome chỉ dùng cửa sổ đã chọn')
   if not self.snapshot().get('online'):raise ValueError('Windows Agent chưa kết nối')
   if browser=='edge':
    report=self.client.request('/inspect',{'action':'LIST_EDGE_PROFILES','target_app':'edge'},timeout=7)
    profiles=report.get('result',{}).get('profiles',[])
    match=next((r for r in profiles if r['directory']==profile),None)
    if not match:raise ValueError('Profile Edge không tồn tại')
    profile_name=match['name']
   else:profile_name='Default'
   sid=str(data.get('studio_project_id',''));url=validate_url(str(data.get('studio_url','')))
   metadata=json.loads((Path(p['folder'])/'project.json').read_text(encoding='utf8'))
   if metadata.get('simulation_test_key'):raise ValueError('Chọn dự án thật, không dùng project TEST cho Studio')
   actions,context=studio_workflow(sid,url,browser,profile,p['folder'],metadata.get('script',''),data.get('context'))
   for other in q.list():
    if other['id']==p['id']:continue
    other_path=Path(other['folder'])/'project.json'
    try:other_meta=json.loads(other_path.read_text(encoding='utf8'))
    except (OSError,ValueError):continue
    if other_meta.get('studio_project_id')==sid:raise ValueError('Studio project ID này đã liên kết với dự án khác')
   q.bind_studio(p['id'],sid,url,browser,profile)
   q.set_browser(p['id'],browser,profile,profile_name)
   metadata.update(browser=browser,browser_profile=profile,browser_profile_name=profile_name,studio_project_id=sid,studio_url=url)
   from .studio_workflow import atomic
   atomic(Path(p['folder'])/'project.json',metadata)
   result=self.client.request('/submit',{'actions':actions,'context':context,'project':p['id'],'held':True})
   q.attach_automation(p['id'],result['task_id']);self.ensure_bridge();return result
  if cmd=='start_agent':self.client.restart();return {'ok':True}
  if cmd=='stop_agent':
   self.queue_getter().stop_all();self.client.stop(terminate=True);return {'ok':True}
  if cmd=='stop':self.stop_all();return {'ok':True}
  if cmd=='settings':
   if any(t['status']=='running' for t in self.snapshot().get('tasks',[])):raise ValueError('Dừng task trước khi đổi cài đặt Agent')
   settings={}
   for app in ('chrome','capcut'):
    p=str(data.get(app+'_path','')).strip()
    if p and Path(p).name.lower()!=app+'.exe':raise ValueError('Đường dẫn phải kết thúc bằng '+app+'.exe')
    settings[app+'_path']=p
   self.home.mkdir(parents=True,exist_ok=True);path=self.home/'settings.json';temp=path.with_suffix('.tmp');temp.write_text(json.dumps(settings),encoding='utf8');temp.replace(path)
   self.client.stop(terminate=True);self.client.restart();return {'ok':True}
  if cmd=='project_browser':
   q=self.queue_getter();p=q.get(data['project']);browser=data.get('browser')
   if browser not in ('chrome','edge'):raise ValueError('Chọn Chrome hoặc Edge')
   profile=str(data.get('browser_profile') or 'Default')
   if browser=='edge':
    r=self.client.request('/inspect',{'action':'LIST_EDGE_PROFILES','target_app':'edge'},timeout=7)
    rows=r.get('result',{}).get('profiles',[])
    match=next((x for x in rows if x['directory']==profile),None)
    if not r.get('success') or not match:raise ValueError('Profile Edge không tồn tại')
    name=match['name']
   else:name=profile
   q.set_browser(p['id'],browser,profile,name);return {'ok':True}
  if not self.snapshot().get('online'):raise ValueError('Windows Agent chưa kết nối. Kiểm tra trạng thái và nhật ký khởi động.')
  if cmd=='edge_diagnostics':return self.client.request('/inspect',{'action':'EDGE_DIAGNOSTICS','target_app':'edge','browser_profile':data.get('browser_profile')},timeout=23)
  if cmd=='edge_profiles':return self.client.request('/inspect',{'action':'LIST_EDGE_PROFILES','target_app':'edge'},timeout=7)
  if cmd=='ping':return self.client.request('/state')
  if cmd=='resume':return self.client.request('/resume',{'task_id':data['task_id']})
  if cmd=='start':return self.client.request('/start',{})
  if cmd=='test' and data.get('kind') in ('windows','processes','find','check'):
   kind=data['kind'];action={'windows':'LIST_WINDOWS','processes':'LIST_PROCESSES','find':'LIST_WINDOWS','check':'CHECK_PROCESS'}[kind]
   body={'action':action}
   if kind in ('find','check'):body['target_app']=data.get('app','chrome')
   if data.get('browser_profile'):body['browser_profile']=data['browser_profile']
   return self.client.request('/inspect',body,timeout=7)
  if cmd in ('test','submit'):
   actions=workflow(data.get('kind'),data.get('app','chrome'),data.get('url','https://example.com'),data.get('hwnd') or None,data.get('browser_profile')) if cmd=='test' else data.get('actions')
   if len(actions or [])==1 and actions[0].get('action')=='OPEN_APP' and actions[0].get('target_app')=='edge':
    profile=actions[0].get('browser_profile')
    existing=next((t for t in self.snapshot().get('tasks',[]) if t['status'] in ('running','waiting') and len(t['actions'])==1 and t['actions'][0].get('action')=='OPEN_APP' and t['actions'][0].get('target_app')=='edge' and t['actions'][0].get('browser_profile')==profile),None)
    if existing:
     if existing['status']=='waiting':self.client.request('/start',{})
     return {'task_id':existing['id'],'already_pending':True}
   pid=data.get('project') or None
   if pid:
    q=self.queue_getter();p=q.get(pid)
    if p['status'] in ('running','paused'):raise ValueError('Dừng dự án trước khi gắn workflow')
    app=data.get('app','chrome');profile=data.get('browser_profile') or 'Default'
    if app in ('chrome','edge') and (p.get('browser','chrome')!=app or p.get('browser_profile','Default')!=profile):raise ValueError('Trình duyệt/profile không khớp dự án. Lưu lựa chọn cho dự án trước khi gắn workflow.')
   result=self.client.request('/submit',{'actions':actions,'project':pid,'held':bool(pid),'context':data.get('context')})
   if pid:
    self.queue_getter().attach_automation(pid,result['task_id']);self.ensure_bridge()
   else:self.client.request('/start',{})
   return result
  raise ValueError('Lệnh Automation không hợp lệ')
 def retry_projects(self,pid=None):
  q=self.queue_getter();tasks={t['id']:t for t in self.snapshot().get('tasks',[])}
  for p in q.list():
   if p['status']=='failed' and p.get('execution_mode')=='automation' and (not pid or pid==p['id']):
    t=tasks.get(p.get('automation_task_id'))
    if not t or t['status']=='needs_review':raise ValueError('Task cần kiểm tra thủ công, không tự chạy lại thao tác chưa rõ kết quả')
    self.client.request('/requeue',{'task_id':t['id']})
 def stop_all(self):
  self.queue_getter().stop_all()
  if self.client.process and self.client.process.poll() is None:self.client.stop()
 def screenshot(self,name):
  if not re.fullmatch(r'[a-f0-9-]{36}\.png',name):raise ValueError('Tên ảnh không hợp lệ')
  return (self.home/'screenshots'/name).read_bytes()
 def close(self):
  if self.bridge:self.bridge.close()
  self.client.close()
