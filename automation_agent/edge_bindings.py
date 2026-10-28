"""Agent-owned linkage only. Never writes properties onto another app's window."""
SCHEMA=2
KEYS=('hwnd','pid','process_started','browser_profile')

def validate_record(target,record):
 if not record or record.get('binding_schema')!=SCHEMA or any(record.get(k)!=target.get(k) for k in KEYS):
  raise RuntimeError('Chưa xác minh đúng Edge Profile/cửa sổ. Chọn profile rồi bấm Mở Edge trước.')

def validate_live(record,live,proof):
 if not live or any(record.get(k)!=live.get(k) for k in ('hwnd','pid','process_started')):
  raise RuntimeError('Cửa sổ Edge/PID đã thay đổi; liên kết cũ không còn hợp lệ.')
 if not proof.get('verified'):
  raise RuntimeError('Cửa sổ Edge không còn xác minh được đúng profile; đã chặn thao tác.')

def make_record(window,profile,name):
 return dict(window,target_app='edge',browser='edge',browser_profile=profile,browser_profile_name=name,profile_proof='Windows Shell',binding_schema=SCHEMA)
