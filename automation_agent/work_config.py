"""Project-specific tasks and ordinal scopes."""
import re
KINDS=('analysis','scenes','images','retry_images','sync')
def lanes(raw):
 """ChatGPT lanes: the main browser first, then extra browser profiles (each with its own ChatGPT + Extension)."""
 if raw is None:return []
 if not isinstance(raw,list) or len(raw)>4:raise ValueError('Tối đa 4 tab ChatGPT song song')
 out=[]
 for row in raw:
  if not isinstance(row,dict) or row.get('browser') not in ('edge','chrome'):raise ValueError('Mỗi tab ChatGPT cần trình duyệt Edge hoặc Chrome')
  profile=str(row.get('profile') or 'Default')
  if not re.fullmatch(r'(Default|Profile \d{1,3})',profile):raise ValueError('Hồ sơ trình duyệt không hợp lệ: '+profile)
  key=(row['browser'],profile)
  if key in [(x['browser'],x['profile']) for x in out]:raise ValueError('Hai tab ChatGPT không được dùng cùng một hồ sơ trình duyệt (Extension chỉ dùng 1 tab mỗi hồ sơ)')
  out.append({'browser':row['browser'],'profile':profile})
 return out
def normalize(raw):
 if not isinstance(raw,dict):raise ValueError('Cấu hình phải là object')
 selected=raw.get('tasks',[])
 if not isinstance(selected,list) or not selected or any(k not in KINDS for k in selected):raise ValueError('Chọn task có worker; transcript/video/export chưa hỗ trợ')
 policy=raw.get('error_policy','continue');retry=raw.get('retry_limit',2)
 if policy not in ('continue','stop') or type(retry)!=int or not 0<=retry<=3:raise ValueError('Chính sách lỗi/retry không hợp lệ')
 if raw.get('rerun') and any(k in selected for k in ('analysis','scenes')):raise ValueError('Chạy lại kết quả phân tích/phân cảnh chưa hỗ trợ an toàn; chỉ ảnh có backup/rerun')
 scopes={}
 for kind in selected:
  scope=(raw.get('scopes') or {}).get(kind,{'mode':'all'})
  if not isinstance(scope,dict) or scope.get('mode','all') not in ('all','missing','errors','range','selected'):raise ValueError('Phạm vi không hợp lệ')
  scope=dict(scope,mode=scope.get('mode','all'))
  if kind=='analysis' and scope['mode']!='all':raise ValueError('Studio chỉ phân tích cấu trúc toàn kịch bản; chọn phạm vi ở Phân cảnh')
  if scope['mode']=='range' and (any(type(scope.get(k))!=int for k in ('from','to')) or not 1<=scope['from']<=scope['to']<=100000):raise ValueError('Khoảng: số nguyên 1-based, từ <= đến')
  if scope['mode']=='selected':
   if not isinstance(scope.get('items'),list) or not scope['items'] or any(type(x)!=int or not 1<=x<=100000 for x in scope['items']):raise ValueError('Nhập số thứ tự dương')
   scope['items']=sorted(set(scope['items']))
  scopes[kind]=scope
 return {'tasks':[k for k in KINDS if k in selected],'scopes':scopes,'error_policy':policy,'retry_limit':retry,'rerun':bool(raw.get('rerun',False)),**({'lanes':lanes(raw['lanes'])} if raw.get('lanes') else {})}
def in_scope(index,scope):
 mode=scope.get('mode','all')
 return scope['from']<=index<=scope['to'] if mode=='range' else index in scope['items'] if mode=='selected' else True

def validate_extent(scope,total):
 if scope.get('mode')=='range' and scope['to']>total:raise ValueError('Phạm vi vượt tổng số mục hiện có: '+str(total))
 if scope.get('mode')=='selected' and any(x>total for x in scope['items']):raise ValueError('Mục được chọn chưa tồn tại trong Studio')
