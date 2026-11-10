import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation_agent.action_worker import dispatch


class WinControlFileActionTests(unittest.TestCase):
    def test_ensure_verify_and_open_are_confined_to_wincontrol_temp(self):
        root = Path(tempfile.gettempdir()) / 'WinControl'
        path = root / 'acceptance.txt'
        context = {'target_app': 'notepad'}
        ensure = dispatch({'action': 'ENSURE_TEMP_DIR'}, context, Path(tempfile.gettempdir()), {})
        self.assertTrue(ensure['created'] or ensure['exists'])
        path.write_text('WinControl đang hoạt động', encoding='utf-8')
        verified = dispatch({'action': 'VERIFY_FILE', 'path': str(path), 'expected_text': 'WinControl đang hoạt động'}, context, Path(tempfile.gettempdir()), {})
        self.assertTrue(verified['verified'])
        with patch('automation_agent.action_worker.subprocess.Popen') as popen, patch('automation_agent.action_worker.wm.windows', return_value=[{'hwnd':1,'title':'acceptance.txt - Notepad'}]):
            opened = dispatch({'action': 'OPEN_FILE', 'target_app': 'notepad', 'path': str(path)}, context, Path(tempfile.gettempdir()), {})
        self.assertTrue(opened['opened'])
        self.assertEqual(opened['window']['title'],'acceptance.txt - Notepad')
        popen.assert_called_once()

    def test_file_actions_reject_paths_outside_temp(self):
        with self.assertRaises(ValueError):
            dispatch({'action': 'VERIFY_FILE', 'path': str(Path(tempfile.gettempdir()) / 'outside.txt'), 'expected_text': 'x'}, {}, Path(tempfile.gettempdir()), {})


if __name__ == '__main__':
    unittest.main()
