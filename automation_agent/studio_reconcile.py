"""REFRESH -> RECONCILE -> VALIDATE for Studio work.

Studio is the source of truth. A stored error or checkpoint is only a hint: before any
resume/retry the current Studio server session and the live Studio tab state are read
again, and the old error is cleared when the real state no longer has the problem.
"""
import json,time,urllib.parse,urllib.request

SCRIPT_MISSING='SCRIPT_MISSING'
SCRIPT_NOT_SYNCED='SCRIPT_NOT_SYNCED'
SCRIPT_ERRORS=('Dự án chưa có kịch bản',SCRIPT_MISSING)

def read_presence(sid,run_id=None):
 query={'sessionId':sid}
 if run_id:query['runId']=run_id
 with urllib.request.urlopen('http://127.0.0.1:8765/api/studio-presence?'+urllib.parse.urlencode(query),timeout=3) as r:return json.load(r)

def refresh(sid,api=None,presence=None):
 """REFRESH: read the live Studio server session and any open Studio tab for this project."""
 from .studio_workflow import StudioAPI
 session=(api or StudioAPI()).request(sid)
 try:tab=(presence or read_presence)(sid)
 except Exception:tab={}
 return session,tab or {}

def reconcile(session,tab=None):
 """RECONCILE: one fact sheet from the real Studio state (no prompt text is stored)."""
 tab=tab or {};state=tab.get('project_state') or {}
 parts=session.get('parts') or [];job=session.get('activeJob') or None
 server_chars=len(str(session.get('script') or '').strip())
 draft_chars=int(state.get('script_draft_characters') or 0) if tab.get('studio_tab_open') else 0
 scenes=[s for p in parts for s in (p.get('scenes') or [])]
 return {
  'refreshed_at':time.time(),
  'studio_status':session.get('status'),
  'active_job':(job or {}).get('type'),
  'script_content_exists':server_chars>0 or draft_chars>0,
  'script_character_count':server_chars or draft_chars,
  'script_server_character_count':server_chars,
  'script_draft_character_count':draft_chars,
  'script_source':'studio_server' if server_chars else 'studio_draft' if draft_chars else None,
  'script_sync':state.get('script_sync') if tab.get('studio_tab_open') else None,
  'transcript_known':bool(tab.get('studio_tab_open') and tab.get('project_state') is not None),
  'transcript_exists':bool(state.get('transcript_exists')),
  'transcript_character_count':int(state.get('transcript_characters') or 0),
  'analysis_completed':bool(parts) and not (job and job.get('type')=='script_structure'),
  'parts_total':len(parts),
  'parts_completed':sum(p.get('status')=='complete' for p in parts),
  'scenes_total':len(scenes),
  'images_completed':sum(bool(s.get('imageStatus')=='complete' and s.get('imageResults')) for s in scenes),
  'studio_tab_open':bool(tab.get('studio_tab_open')),
  'chat_connected':bool(tab.get('chat_connected')),
 }

def validate(facts,action):
 """VALIDATE: (error_code, message) for the next action, or (None, None) when it may run."""
 if action in ('STUDIO_TRANSCRIPT','STUDIO_ANALYZE') and not facts['analysis_completed']:
  if not facts['script_content_exists']:
   if facts.get('transcript_exists'):return SCRIPT_MISSING,'Studio đã có transcript nhưng chưa có kịch bản. Bấm "Dùng transcript" trong Studio để đưa vào kịch bản.'
   return SCRIPT_MISSING,'Studio chưa có kịch bản. Nhập kịch bản hoặc lấy transcript trong Studio rồi chạy lại.'
 return None,None

def is_script_error(error):
 return any(x in str(error or '') for x in SCRIPT_ERRORS)

WINDOW_KEYS=('hwnd','pid','process_started','profile_proof','binding_schema','focus_verified_at')

def resume_point(task,facts,run_tab_open):
 """Where RESUME starts. With no Studio job running, the run re-validates from STUDIO_READY;
 if the Studio tab for this run nonce is gone, the same launch URL is opened again first."""
 names=[a['action'] for a in task['actions']];index=task['next_action']
 if facts.get('active_job') or 'STUDIO_READY' not in names or index<=names.index('STUDIO_READY'):return index
 if not run_tab_open and 'OPEN_APP' in names:return names.index('OPEN_APP')
 return names.index('STUDIO_READY')

def prepare_resume(task,facts,run_tab_open):
 """Apply the resume point to a task dict (agent side). Returns the new next_action."""
 index=resume_point(task,facts,run_tab_open);names=[a['action'] for a in task['actions']]
 if 'OPEN_APP' in names and index==names.index('OPEN_APP'):
  for key in WINDOW_KEYS:task['context'].pop(key,None)
 task['next_action']=index
 task['context'].update(studio_reconcile=facts,studio_error_code=None,studio_resumed_at=time.time())
 if is_script_error(task.get('error')) and facts['script_content_exists']:task['context']['studio_resolved_error']=SCRIPT_MISSING
 task['error']=None
 return index
