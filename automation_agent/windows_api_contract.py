"""Discover Windows API references from source and check real installed modules."""
import ast,importlib,json,sys
from pathlib import Path
MODULES={'win32gui','win32api','win32process','win32con','win32job','win32clipboard','pythoncom','win32com.propsys.propsys','win32com.propsys.pscon'}

def scan_api_usage(root):
 usage={}
 for path in sorted(Path(root).rglob('*.py')):
  tree=ast.parse(path.read_text(encoding='utf8'));aliases={};direct={}
  for node in ast.walk(tree):
   if isinstance(node,ast.Import):
    for n in node.names:
     if n.name in MODULES:aliases[n.asname or n.name]=n.name
   elif isinstance(node,ast.ImportFrom):
    for n in node.names:
     full=(node.module or '')+'.'+n.name
     if full in MODULES:aliases[n.asname or n.name]=full
     elif node.module in MODULES:direct[n.asname or n.name]=(node.module,n.name,node.lineno)
  refs=[]
  for node in ast.walk(tree):
   if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id in aliases:
    refs.append((aliases[node.value.id],node.attr,node.lineno))
   elif isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load) and node.id in direct:refs.append(direct[node.id])
   elif isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='getattr' and len(node.args)>1 and isinstance(node.args[0],ast.Name) and node.args[0].id in aliases and isinstance(node.args[1],ast.Constant) and isinstance(node.args[1].value,str):refs.append((aliases[node.args[0].id],node.args[1].value,node.lineno))
  for mod,name,line in refs:
   key=(mod,name);usage.setdefault(key,[]).append({'file':str(path.relative_to(root)),'line':line})
 return [{'module':mod,'name':name,'references':refs} for (mod,name),refs in sorted(usage.items())]

def audit(usage=None):
 if sys.platform!='win32':return {'status':'SKIP','reason':'Requires real Windows/pywin32; no mock substitute','checked':[],'missing':[]}
 usage=scan_api_usage(Path(__file__).parent) if usage is None else usage
 checked=[];missing=[];modules={}
 for item in usage:
  mod=item['module'];key=mod+'.'+item['name']
  if mod not in modules:
   try:modules[mod]=importlib.import_module(mod)
   except ImportError:modules[mod]=None
  exists=modules[mod] is not None and hasattr(modules[mod],item['name'])
  checked.append(dict(item,exists=exists))
  if not exists:missing.append(key)
 return {'status':'FAIL' if missing else 'PASS','checked':checked,'missing':missing}

if __name__=='__main__':
 report=audit();print(json.dumps(report,ensure_ascii=True,indent=2));sys.exit(1 if report['status']=='FAIL' else 0)
