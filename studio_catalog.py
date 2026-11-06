"""Match legacy/imported Studio profiles by identity, never by display name."""
def identity(p):
 source=p.get('studio_source') or {}
 return (source.get('id') or p.get('studio_project_id') or p.get('studio_import_id'),str(source.get('origin') or p.get('studio_url') or '').rstrip('/'),source.get('browser') or p.get('browser','edge'),source.get('profile') or p.get('browser_profile','Default'))

def ids(p):
 """Every Studio project this Manager project is linked to: its import source, its import id and the Studio project a deploy attached later."""
 return {x for x in (p.get('studio_project_id'),p.get('studio_import_id'),(p.get('studio_source') or {}).get('id')) if x}

def matches(p,key):
 if p.get('simulation_test_key'):return False
 _,origin,browser,profile=identity(p)
 return key['id'] in ids(p) and (origin,browser,profile)==(key['origin'].rstrip('/'),key['browser'],key['profile'])

def canonical(rows,queue):
 active=[p for p in rows if queue.get(p['id'],{}).get('status') in ('running','paused')]
 if len(active)>1:raise ValueError('Có nhiều hồ sơ đang hoạt động cho cùng Studio ID; dừng trước khi đồng bộ')
 return active[0] if active else max(rows,key=lambda p:(bool(queue.get(p['id'],{}).get('automation_task_id')),queue.get(p['id'],{}).get('action_done',0),bool(p.get('studio_project_id'))))
