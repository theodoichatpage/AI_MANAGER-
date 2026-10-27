"""Separate read-only catalog of projects reported by Studio browser profiles."""
import sqlite3

class StudioCatalog:
 def __init__(self,path):
  self.path=path
  path.parent.mkdir(parents=True,exist_ok=True)
  with sqlite3.connect(path) as db:
   db.execute('CREATE TABLE IF NOT EXISTS studio_projects (origin TEXT NOT NULL, instance TEXT NOT NULL, project_id TEXT NOT NULL, name TEXT NOT NULL, updated_at INTEGER, missing INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(origin,instance,project_id))')
   db.execute('CREATE TABLE IF NOT EXISTS studio_project_links (local_id TEXT PRIMARY KEY, origin TEXT NOT NULL, instance TEXT NOT NULL, project_id TEXT NOT NULL, UNIQUE(origin,instance,project_id))')
 def replace(self,origin,instance,items):
  with sqlite3.connect(self.path) as db:
   db.execute('UPDATE studio_projects SET missing=1 WHERE origin=? AND instance=?',(origin,instance))
   for item in items:
    db.execute('INSERT INTO studio_projects(origin,instance,project_id,name,updated_at,missing) VALUES(?,?,?,?,?,0) ON CONFLICT(origin,instance,project_id) DO UPDATE SET name=excluded.name,updated_at=excluded.updated_at,missing=0',(origin,instance,item['id'],item['name'],item.get('updatedAt')))
 def list(self,origin,instance):
  with sqlite3.connect(self.path) as db:
   rows=db.execute('SELECT project_id,name,updated_at,missing FROM studio_projects WHERE origin=? AND instance=? ORDER BY name,project_id',(origin,instance)).fetchall()
  return [{'id':r[0],'name':r[1],'updatedAt':r[2],'missing':bool(r[3])} for r in rows]
 def link(self,local_id,origin,instance,project_id):
  with sqlite3.connect(self.path) as db:
   if not db.execute('SELECT 1 FROM studio_projects WHERE origin=? AND instance=? AND project_id=? AND missing=0',(origin,instance,project_id)).fetchone(): raise ValueError('Không tìm thấy dự án Studio')
   db.execute('INSERT INTO studio_project_links(local_id,origin,instance,project_id) VALUES(?,?,?,?) ON CONFLICT(local_id) DO UPDATE SET origin=excluded.origin,instance=excluded.instance,project_id=excluded.project_id',(local_id,origin,instance,project_id))
 def linked(self,local_id):
  with sqlite3.connect(self.path) as db:return db.execute('SELECT origin,instance,project_id FROM studio_project_links WHERE local_id=?',(local_id,)).fetchone()
