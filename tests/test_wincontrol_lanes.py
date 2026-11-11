import tempfile
import threading
import time
import unittest
from pathlib import Path

from automation_agent.runtime import AgentRuntime


def ok(tid, action, retry=0, result=None):
    return {'task_id': tid, 'action': action['action'], 'success': True, 'status': 'completed', 'error': None,
            'result': result or {}, 'retry_count': retry}


class SlowProduction:
    """A production action that keeps running until it is cancelled or released."""
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancelled = False

    def run(self, tid, action, context, cancel, retry=0):
        self.started.set()
        while not self.release.is_set():
            if cancel.wait(.02):
                self.cancelled = True
                return {'task_id': tid, 'action': action['action'], 'success': False, 'status': 'stopped', 'error': 'Đã dừng', 'result': {}, 'retry_count': retry}
        return ok(tid, action, retry)

    def cancel(self):
        pass


class QuickWinControl:
    def __init__(self):
        self.calls = []

    def run(self, tid, action, context, cancel, retry=0):
        self.calls.append(action['action'])
        if action['action'] == 'WINCONTROL_DECIDE':
            return ok(tid, action, retry, {'decision': {'status': 'complete', 'summary': 'Xong', 'actions': []}, 'context': {'wincontrol_round': 1}})
        return ok(tid, action, retry)

    def cancel(self):
        pass


class WinControlLaneTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.runtime = AgentRuntime(Path(self.td.name))
        self.production = SlowProduction()
        self.wincontrol = QuickWinControl()
        self.runtime.executor = self.production
        self.runtime.wc_executor = self.wincontrol

    def tearDown(self):
        self.production.release.set()
        self.runtime.shutdown.set()
        self.runtime.thread.join(2)
        self.runtime.wc_thread.join(2)
        self.runtime.store.close()
        self.td.cleanup()

    def wait_for(self, tid, statuses, seconds=5):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            task = self.runtime.store.get(tid)
            if task['status'] in statuses:
                return task
            time.sleep(.02)
        return self.runtime.store.get(tid)

    def test_wincontrol_task_finishes_while_production_runs_and_its_cancel_spares_production(self):
        studio = self.runtime.store.submit([{'action': 'WAIT'}], stage='Automation', context={'studio_project_id': 's'})
        self.runtime.start()
        self.assertTrue(self.production.started.wait(3))
        wc = self.runtime.store.submit([{'action': 'WINCONTROL_DECIDE'}], stage='WinControl', context={'wincontrol_task': True, 'wincontrol_round': 0})
        self.assertEqual(self.wait_for(wc, ('completed', 'failed', 'needs_review'))['status'], 'completed')
        self.assertEqual(self.runtime.store.get(studio)['status'], 'running')
        second = self.runtime.store.submit([{'action': 'WAIT', 'seconds': 1}], stage='WinControl', context={'wincontrol_task': True})
        self.runtime.cancel_task(second)
        self.assertFalse(self.runtime.cancel.is_set())
        self.assertTrue(self.runtime.enabled)
        self.assertEqual(self.runtime.store.get(studio)['status'], 'running')
        self.production.release.set()
        self.assertEqual(self.wait_for(studio, ('completed',))['status'], 'completed')
        self.assertFalse(self.production.cancelled)

    def test_production_pause_leaves_wincontrol_alone(self):
        wc = self.runtime.store.submit([{'action': 'WAIT'}], stage='WinControl', context={'wincontrol_task': True}, initial_status='held')
        self.runtime.pause()
        self.assertEqual(self.runtime.store.get(wc)['status'], 'held')

    def test_a_wincontrol_send_interrupted_for_review_can_continue_but_an_ui_action_cannot(self):
        store = self.runtime.store
        send = store.submit([{'action': 'SEND_CHATGPT', 'text': 'x', 'exchange_id': 'wincontrol-x-1'}], stage='WinControl', context={'wincontrol_task': True}, initial_status='held')
        typed = store.submit([{'action': 'TYPE_TEXT'}], stage='WinControl', context={'wincontrol_task': True}, initial_status='held')
        with store.lock, store.db:
            for tid, action in ((send, 'SEND_CHATGPT'), (typed, 'TYPE_TEXT')):
                t = store.get(tid); t.update(status='needs_review', current_action=action, in_flight=True); store.save(t)
        store.resume(send)
        self.assertEqual(store.get(send)['status'], 'waiting')
        with self.assertRaises(ValueError):
            store.resume(typed)


if __name__ == '__main__':
    unittest.main()
