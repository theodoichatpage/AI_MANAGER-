import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from automation_agent import ui_automation as ui

class ScreenshotFocusTests(unittest.TestCase):
 def test_recovers_focus_before_capture(self):
  target={'target_app':'capcut','hwnd':42,'pid':7}
  image=Mock(width=100,height=80)
  with tempfile.TemporaryDirectory() as folder, patch.object(ui,'require_windows'), patch.object(ui,'validate_target',side_effect=[42,RuntimeError('lost focus'),42]), patch.object(ui,'focus',create=True) as focus, patch.object(ui,'root') as root:
   root.return_value.capture_as_image.return_value=image
   result=ui.screenshot(target,Path(folder))
   focus.assert_called_once_with(target)
   self.assertEqual(result['width'],100)
   image.save.assert_called_once()
 def test_rejects_changed_identity_before_focus(self):
  with tempfile.TemporaryDirectory() as folder, patch.object(ui,'require_windows'), patch.object(ui,'validate_target',side_effect=RuntimeError('PID changed')), patch.object(ui,'focus',create=True) as focus, patch.object(ui,'root') as root:
   with self.assertRaisesRegex(RuntimeError,'PID changed'):ui.screenshot({'hwnd':42},folder)
   focus.assert_not_called();root.assert_not_called()
 def test_no_capture_if_focus_cannot_be_restored(self):
  with tempfile.TemporaryDirectory() as folder, patch.object(ui,'require_windows'), patch.object(ui,'validate_target',side_effect=[42,RuntimeError('lost focus')]), patch.object(ui,'focus',create=True,side_effect=RuntimeError('cannot focus')), patch.object(ui,'root') as root:
   with self.assertRaisesRegex(RuntimeError,'cannot focus'):ui.screenshot({'hwnd':42},folder)
   root.assert_not_called()
