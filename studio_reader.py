"""Read-only projection of VIDEO IMAGE STUDIO web sessions.

A session record cannot prove that the Studio browser tab or ChatGPT is online.
"""
import json,re,urllib.parse,urllib.request

ENDPOINT='https://wtxgjsorpqjanxoevxuw.supabase.co/functions/v1/studio-api'

def _project_name(session):
    """Use Studio's own project name; tolerate older/newer session schemas."""
    for key in ('projectName','project_name','name','title'):
        value=session.get(key)
        if isinstance(value,str) and value.strip(): return value.strip()
    project=session.get('project')
    if isinstance(project,dict):
        for key in ('name','title'):
            value=project.get(key)
            if isinstance(value,str) and value.strip(): return value.strip()
    return None

def summarize_session(session):
    parts=session.get('parts')
    scenes=[scene for part in parts for scene in part.get('scenes',[])] if isinstance(parts,list) else None
    job=session.get('activeJob') or {}
    current=None
    key=job.get('sceneKey','')
    if scenes is not None and ':' in key:
        part_id, index=key.rsplit(':',1)
        part=next((p for p in parts if p.get('id')==part_id),None)
        if part and index.isdigit() and int(index)<len(part.get('scenes',[])): current=part['scenes'][int(index)].get('title')
    return {'project_id':session.get('id'), 'project_name':_project_name(session), 'status':session.get('status'),
        'total_parts':len(parts) if isinstance(parts,list) else None,
        'completed_parts':sum(p.get('status')=='complete' for p in parts) if isinstance(parts,list) else None,
        'total_scenes':len(scenes) if scenes is not None else None, 'analyzed_scenes':sum(bool(s.get('prompt')) for s in scenes) if scenes is not None else None,
        'images_done':sum(s.get('imageStatus')=='complete' for s in scenes) if scenes is not None else None,
        'images_failed':sum(s.get('imageStatus')=='error' for s in scenes) if scenes is not None else None,
        'current_scene':current, 'current_part':job.get('partId'), 'studio_tab_open':None, 'chat_connected':None}

def read_session(session_id,timeout=8):
    if not re.fullmatch(r'[A-Za-z0-9-]{16,64}',session_id): raise ValueError('Mã phiên không hợp lệ')
    url=ENDPOINT+'?'+urllib.parse.urlencode({'path':'sessions/'+session_id})
    with urllib.request.urlopen(urllib.request.Request(url,method='GET'),timeout=timeout) as response:
        payload=response.read(5_000_001)
    if len(payload)>5_000_000: raise ValueError('Dữ liệu quá lớn')
    session=json.loads(payload).get('session')
    if not isinstance(session,dict): raise ValueError('Không tìm thấy phiên Studio')
    return summarize_session(session)
