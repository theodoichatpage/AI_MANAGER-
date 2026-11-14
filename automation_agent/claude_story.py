"""Story line written and graded by Claude (tool CAU_TRUC_APRILINNE), for a project whose engine is 'claude'.

Manager only starts the tool and watches it: `python -m aprilinne` runs in the background inside the project folder
(analysis/aprilinne/run/), writer and grader are separate `claude -p` calls. Every step's prompt, answer, script and
scorecard stay there; Studio's Analysis tab reads them through story_review (aprilinne.studio.report).
When the best version is approved, its acts become the Studio script and the story parts, exactly like the ChatGPT line."""
import json,os,re,subprocess,sys
from pathlib import Path

RUN='run'
TRIES=3
DEFAULT_ROOT=Path.home()/'Projects'/'CAU_TRUC_APRILINNE'
MODES=('video_dai','series')
STEP={'lay_transcript':'Đang lấy transcript','dan_y':'Claude đang lập dàn ý hai tuyến','viet':'Claude đang viết kịch bản',
 'bien_tap':'Claude đang biên tập','cham':'Người chấm Claude (độc lập) đang chấm','sua':'Claude đang sửa theo bảng điểm'}

def tool_root(c=None):
 return Path((c or {}).get('studio_aprilinne_root') or os.environ.get('APRILINNE_ROOT') or DEFAULT_ROOT)
def runs_dir(folder):return Path(folder)/'analysis'/'aprilinne'
def run_state(folder):
 try:return json.loads((runs_dir(folder)/RUN/'state.json').read_text(encoding='utf8'))
 except (OSError,ValueError):return None
def engine(c):return 'claude' if str((c or {}).get('studio_story_engine') or '').lower()=='claude' else 'chatgpt'

def _tool(root):
 root=str(root)
 if root not in sys.path:sys.path.insert(0,root)
 import aprilinne.studio,aprilinne.script
 return aprilinne

def report(folder,root=None):
 """The run as Studio's Analysis tab shows it, or None when this project has no Claude run."""
 d=runs_dir(folder)/RUN
 if not (d/'state.json').is_file():return None
 return _tool(root or tool_root()).studio.report(d)

def process_alive(pid):
 if not pid:return False
 if os.name=='nt':
  import ctypes
  h=ctypes.windll.kernel32.OpenProcess(0x00100000|0x1000,False,int(pid))  # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
  if not h:return False
  try:return ctypes.windll.kernel32.WaitForSingleObject(h,0)==0x102  # WAIT_TIMEOUT: still running
  finally:ctypes.windll.kernel32.CloseHandle(h)
 try:os.kill(int(pid),0);return True
 except OSError:return False

class ClaudeStory:
 def __init__(self,w,script=None):
  self.w=w;self.script=script;self.dir=runs_dir(w.folder);self.meta_path=self.dir/'manager.json'
  try:self.meta=json.loads(self.meta_path.read_text(encoding='utf8'))
  except (OSError,ValueError):self.meta={'tries':0}
 def save_meta(self):
  self.dir.mkdir(parents=True,exist_ok=True);self.meta_path.write_text(json.dumps(self.meta,ensure_ascii=False),encoding='utf8')
 def wait(self,key,message):
  return self.w.wait('claude:'+key,3600,dict(studio_stage='Viết kịch bản (Claude)',studio_message=message))
 def spawn(self,args):
  """Start the tool in the background; its output goes to analysis/aprilinne/chay.log."""
  c=self.w.c;root=tool_root(c);self.dir.mkdir(parents=True,exist_ok=True)
  env=dict(os.environ,APRILINNE_RUNS=str(self.dir),PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
  # MAN does not have ~/.local/bin (the Claude Code install) on its PATH: name that claude.exe for the tool.
  local=Path.home()/'.local'/'bin'/('claude.exe' if os.name=='nt' else 'claude')
  if not env.get('APRILINNE_CLAUDE') and local.is_file():env['APRILINNE_CLAUDE']=str(local)
  flags=(getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)) if os.name=='nt' else 0
  with open(self.dir/'chay.log','ab') as log:
   p=subprocess.Popen([sys.executable,'-m','aprilinne',*args],cwd=str(root),env=env,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=flags)
  self.meta.update(pid=p.pid,args=args,started=self.w.clock());self.save_meta()
 def log_tail(self,n=1500):
  try:return (self.dir/'chay.log').read_bytes()[-n:].decode('utf8','replace')
  except OSError:return ''
 def source(self):
  """Text the run starts from: the pasted script, or the transcript of the reference link."""
  if self.script:return self.script
  from .story_pipeline import fetch_transcript
  return fetch_transcript(self.w.c['studio_youtube_url'],self.w.c.get('studio_language','vi'))
 def step(self,s):
  w=self.w;c=w.c;w.post_command(None)
  st=run_state(w.folder)
  if st is None:
   if process_alive(self.meta.get('pid')):return self.wait('start','Đang khởi động công cụ Aprilinne')
   if not self.script:
    from .studio_workflow import engine_up,start_transcript_engine
    if not engine_up():return self.wait('engine',start_transcript_engine(w.j,w.clock()))
   self.dir.mkdir(parents=True,exist_ok=True);src=self.dir/'nguon_vao.txt'
   if not src.is_file():src.write_text(self.source(),encoding='utf8')
   mode=c.get('studio_story_mode') if c.get('studio_story_mode') in MODES else 'video_dai'
   args=['moi',RUN,'--transcript',str(src),'--che-do',mode,'--may','cli']
   if str(c.get('studio_channel_name') or '').strip():args+=['--kenh',str(c['studio_channel_name']).strip()[:100]]
   if str(c.get('studio_story_note') or '').strip():args+=['--ghi-chu',str(c['studio_story_note']).strip()[:2000]]
   self.spawn(args);return self.wait('start','Đã giao Claude viết kịch bản ('+('Series' if mode=='series' else 'Video dài')+')')
  if st.get('buoc')!='xong':
   label=STEP.get(st.get('buoc'),st.get('buoc'))+(' · vòng %d'%st['vong'] if st.get('vong') else '')
   if process_alive(self.meta.get('pid')):return self.wait('%s:%s'%(st.get('buoc'),st.get('vong')),label)
   tail=self.log_tail()
   if 'Not logged in' in tail or '/login' in tail:
    raise RuntimeError('Claude Code chưa đăng nhập trên máy này: mở cửa sổ lệnh, chạy "claude", gõ /login, rồi chạy lại dự án')
   self.meta['tries']=self.meta.get('tries',0)+1
   if self.meta['tries']>TRIES:raise RuntimeError('Công cụ Aprilinne dừng giữa chừng %d lần ở bước %s: %s'%(TRIES,st.get('buoc'),tail[-300:].strip()))
   self.spawn(['chay',RUN,'--may','cli']);return self.wait('%s:%s:retry%d'%(st.get('buoc'),st.get('vong'),self.meta['tries']),label+' (chạy tiếp lần %d)'%self.meta['tries'])
  best=st.get('tot_nhat');d=self.dir/RUN/('vong%d'%best)
  card=json.loads((d/'cham.json').read_text(encoding='utf8'))
  if not card.get('duyet'):
   fail=', '.join('%s %s'%(k,v['diem']) for k,v in card['tieu_chi'].items() if not v['dat'])
   raise RuntimeError('Kịch bản Claude chưa đạt sau %d vòng (bản tốt nhất vòng %d, trượt: %s). Xem thẻ Phân tích trên Studio.'%(st.get('vong'),best,fail or 'lỗi chặn'))
  acts=_tool(tool_root(c)).script.split_acts((d/'kich_ban.md').read_text(encoding='utf8'))
  parts=[{'title':re.sub(r'(?i)^hồi\s*\d+\s*[—–:.\-]*\s*','',t or '').strip() or 'Hồi %d'%(i+1),'content':b.strip()} for i,(t,b) in enumerate(acts)]
  script='\n\n'.join(x['content'] for x in parts)
  if str(s.get('script') or '').strip()!=script:
   if s.get('activeJob'):return self.wait('done:busy','Chờ Studio rảnh để lưu kịch bản')
   w.api.request(w.sid,'/script',{'script':script})
  w.j['aprilynne_done']=True;w.j['story_parts']=parts;w.save()
  return None
 def summary(self):
  st=run_state(self.w.folder) or {}
  return {'engine':'claude','mode':st.get('che_do'),'round':st.get('vong'),'best':st.get('tot_nhat')}
