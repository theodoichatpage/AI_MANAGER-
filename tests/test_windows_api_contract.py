"""Real Windows modules only: never patch sys.modules or mock hasattr here."""
import json,sys,unittest
from pathlib import Path
from automation_agent.windows_api_contract import audit,scan_api_usage

@unittest.skipUnless(sys.platform=='win32','Requires actual Windows pywin32 modules')
class InstalledWindowsAPIContractTests(unittest.TestCase):
 def test_every_referenced_api_exists_in_real_installed_modules(self):
  report=audit()
  self.assertGreater(len(report['checked']),20)
  self.assertEqual(report['missing'],[],json.dumps(report['missing']))
 def test_old_v0210_contract_detects_setprop_failure(self):
  old=json.loads((Path(__file__).parent/'fixtures/windows_api_v0210.json').read_text())
  report=audit(old)
  print('BASELINE_V0210_MISSING_REAL_APIS='+json.dumps(report['missing']),flush=True)
  self.assertEqual(report['status'],'FAIL')
  self.assertIn('win32gui.SetProp',report['missing'])

class SourceScanTests(unittest.TestCase):
 def test_no_window_property_writes_or_reads_remain(self):
  usage=scan_api_usage(Path(__file__).parent.parent/'automation_agent')
  self.assertFalse([u for u in usage if u['module']=='win32gui' and u['name'] in ('SetProp','GetProp','RemoveProp')])
