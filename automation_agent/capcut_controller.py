"""Foundation only; no timeline editing or export in Phase 4."""
from . import window_manager as wm
from . import ui_automation as ui
class CapCutController:
 def __init__(self,settings=None):self.settings=settings or {}
 def detect(self):return wm.windows('capcut')
 def open(self):return wm.open_app('capcut',self.settings)
 def focus(self,target):return wm.focus(target)
 def screenshot(self,target,directory):return ui.screenshot(target,directory)
 def close(self,target):return wm.close(target)
