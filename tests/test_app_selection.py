import unittest
from pathlib import Path
from unittest.mock import patch
from automation_agent.action_worker import dispatch
class AppSelectionTests(unittest.TestCase):
 def test_open_step_cannot_overwrite_a_stale_selected_identity(self):
  target={'target_app':'chrome','hwnd':7,'pid':10,'process_started':100}
  with patch('automation_agent.action_worker.wm.validate_target',side_effect=RuntimeError('PID changed')),patch('automation_agent.action_worker.wm.open_app',return_value={'context':{'hwnd':7,'pid':99}}) as opener:
   with self.assertRaisesRegex(RuntimeError,'PID changed'):dispatch({'action':'OPEN_APP','target_app':'chrome','hwnd':7},target,Path('.'),{})
   opener.assert_not_called()
