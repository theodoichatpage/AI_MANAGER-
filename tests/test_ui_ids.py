import re
import unittest
from pathlib import Path

class DashboardIdsTest(unittest.TestCase):
 def test_referenced_elements_exist_in_html(self):
  html=(Path(__file__).parents[1]/'index.html').read_text(encoding='utf-8')
  ids=set(re.findall(r'id="([^"]+)"',html))
  referenced=set(re.findall(r"\$\('([^']+)'\)",html))
  self.assertEqual(referenced-ids,set())
