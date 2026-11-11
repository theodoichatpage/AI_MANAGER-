import json
import tempfile
import time
import unittest
from pathlib import Path

from automation_agent.runtime import AgentRuntime


class FakeExecutor:
    def __init__(self):
        self.calls = []
        self.decisions = [
            {'status': 'continue', 'summary': 'Open Notepad', 'actions': [{'action': 'OPEN_APP', 'target_app': 'notepad'}]},
            {'status': 'complete', 'summary': 'Verified and complete', 'actions': []},
        ]

    def run(self, tid, action, context, cancel, retry=0):
        self.calls.append((action['action'], dict(action), dict(context)))
        if action['action'] == 'WINCONTROL_DECIDE':
            decision = self.decisions.pop(0)
            return {'task_id': tid, 'action': action['action'], 'success': True, 'status': 'completed', 'error': None,
                    'result': {'decision': decision, 'context': {'wincontrol_round': context.get('wincontrol_round', 0) + 1}}, 'retry_count': retry}
        if action['action'] == 'OPEN_APP':
            return {'task_id': tid, 'action': action['action'], 'success': False, 'status': 'failed', 'error': 'temporary Notepad window error', 'error_code': 'WINDOW_LOST', 'result': {}, 'retry_count': retry}
        if action['action'] == 'SEND_CHATGPT':
            return {'task_id': tid, 'action': action['action'], 'success': True, 'status': 'completed', 'error': None,
                    'result': {'submission': 'received', 'context': {'chatgpt_verified': {'completed': True}}}, 'retry_count': retry}
        raise AssertionError(action)

    def cancel(self):
        pass


class WinControlRuntimeLoopTests(unittest.TestCase):
    def test_safe_cancel_preserves_uncertain_receipt_and_other_checkpoints(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = AgentRuntime(Path(td))
            try:
                tid = runtime.store.submit([{'action':'SEND_CHATGPT','text':'safe test','exchange_id':'wincontrol-cancel-exchange'}], stage='WinControl', context={'wincontrol_task':True})
                runtime.store.claim(tid)
                runtime.store.mark_action(tid,0)
                runtime.current=tid
                other=runtime.store.submit([{'action':'WAIT'}],context={})
                with runtime.store.lock,runtime.store.db:
                    untouched=runtime.store.get(other);untouched.update(status='needs_review',in_flight=True,current_action='STUDIO_PARALLEL');runtime.store.save(untouched)
                result=runtime.cancel_task(tid)
                stopped=runtime.store.get(tid)
                preserved=runtime.store.get(other)
                self.assertEqual(result['status'],'needs_review')
                self.assertTrue(stopped['in_flight'])
                self.assertEqual(stopped['next_action'],0)
                self.assertEqual(preserved['status'],'needs_review')
                self.assertTrue(preserved['in_flight'])
                self.assertEqual(preserved['current_action'],'STUDIO_PARALLEL')
            finally:
                runtime.shutdown.set()
                runtime.thread.join(2)
                runtime.store.close()

    def test_tool_error_is_reported_to_chatgpt_and_agent_continues_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = AgentRuntime(Path(td))
            fake = FakeExecutor()
            runtime.executor = fake
            runtime.wc_executor = fake
            try:
                tid = runtime.store.submit([{'action': 'WINCONTROL_DECIDE'}], stage='WinControl', context={'wincontrol_task': True, 'wincontrol_command': 'open Notepad', 'wincontrol_round': 0})
                runtime.start()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and runtime.store.get(tid)['status'] not in ('completed', 'failed', 'needs_review'):
                    time.sleep(.02)
                task = runtime.store.get(tid)
                self.assertEqual(task['status'], 'completed')
                self.assertEqual([c[0] for c in fake.calls], ['WINCONTROL_DECIDE', 'OPEN_APP', 'SEND_CHATGPT', 'WINCONTROL_DECIDE'])
                self.assertFalse(task['results'][1]['success'])
                feedback = fake.calls[2][1]
                self.assertTrue(feedback['wincontrol_feedback'])
                self.assertGreaterEqual(len(feedback['exchange_id']), 8)
                self.assertEqual(task['results'][-1]['result']['decision']['status'], 'complete')
            finally:
                runtime.shutdown.set()
                runtime.thread.join(2)
                runtime.store.close()


if __name__ == '__main__': unittest.main()
