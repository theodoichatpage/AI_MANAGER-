import tempfile
import unittest
from pathlib import Path
from studio_catalog import StudioCatalog

class CatalogTests(unittest.TestCase):
 def test_identity_rename_missing_and_isolated_sources(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'studio.sqlite3'; c=StudioCatalog(path)
   c.replace('https://preview.example','profile-a',[{'id':'one','name':'Trùng'},{'id':'two','name':'Trùng'}])
   c.replace('https://preview.example','profile-b',[{'id':'one','name':'Khác'}])
   c.replace('https://preview.example','profile-a',[{'id':'one','name':'Đổi tên'}])
   rows=StudioCatalog(path).list('https://preview.example','profile-a')
   self.assertEqual({r['id']:(r['name'],r['missing']) for r in rows},{'one':('Đổi tên',False),'two':('Trùng',True)})
   self.assertEqual(StudioCatalog(path).list('https://preview.example','profile-b')[0]['name'],'Khác')
   c.link('local-1','https://preview.example','profile-a','one')
   self.assertEqual(c.linked('local-1'),('https://preview.example','profile-a','one'))
   with self.assertRaises(ValueError):c.link('local-2','https://preview.example','profile-a','unknown')
