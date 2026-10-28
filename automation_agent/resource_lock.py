"""Transactional interprocess ownership retained across uncertain remote work."""
import json,time,sqlite3
from pathlib import Path
class StudioResource:
 def __init__(self,home):
  self.home=Path(home);self.home.mkdir(parents=True,exist_ok=True);self.path=self.home/'studio_resource.sqlite3'
 def acquire(self,context,action):
  from .studio_workflow import StudioReviewRequired
  with sqlite3.connect(self.path,timeout=5) as db:
   db.execute('PRAGMA synchronous=FULL');db.execute('CREATE TABLE IF NOT EXISTS resource(id INTEGER PRIMARY KEY, owner TEXT, payload TEXT)');db.execute('BEGIN IMMEDIATE')
   row=db.execute('SELECT owner FROM resource WHERE id=1').fetchone()
   if row and row[0]!=context['studio_run_id']:
    if context.get('work_config'):
     from .work_ledger import WorkLedger
     WorkLedger(context['studio_folder'],context).update('resource','Studio/ChatGPT','WAITING_RESOURCE',error='Khóa đang thuộc workflow '+row[0])
    raise StudioReviewRequired('Studio/ChatGPT còn khóa bởi workflow trước; Resume workflow đó để đối soát')
   record={'owner':context['studio_run_id'],'project_id':context.get('manager_project_id'),'studio_project_id':context['studio_project_id'],'profile':context.get('browser_profile'),'action':action,'at':time.time()}
   db.execute('INSERT OR REPLACE INTO resource VALUES(1,?,?)',(context['studio_run_id'],json.dumps(record)))
 def release(self,context):
  if not self.path.exists():return
  with sqlite3.connect(self.path,timeout=5) as db:db.execute('DELETE FROM resource WHERE id=1 AND owner=?',(context['studio_run_id'],))
