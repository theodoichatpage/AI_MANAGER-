import tempfile
import time
import unittest
from pathlib import Path

from automation_agent.runtime import AgentRuntime
from automation_agent.wincontrol_chat_loop import parse_decision


class Executor:
    """ChatGPT is still writing on the first read, then answers with a checked action, then says complete."""
    def __init__(self):
        self.calls = []
        cleaned = parse_decision('{"status":"continue","summary":"Đọc MAN","actions":[{"action":"MAN_STATUS"}]}')
        self.replies = [None, cleaned, {'status': 'complete', 'summary': 'Xong', 'actions': []}]

    def run(self, tid, action, context, cancel, retry=0):
        self.calls.append(dict(action))
        base = {'task_id': tid, 'action': action['action'], 'success': True, 'status': 'completed', 'error': None, 'retry_count': retry}
        if action['action'] == 'WINCONTROL_DECIDE':
            reply = self.replies.pop(0)
            if reply is None:
                return dict(base, result={'waiting': True, 'context': {'wincontrol_wait_reason': 'generating'}})
            return dict(base, result={'decision': reply, 'context': {'wincontrol_round': context.get('wincontrol_round', 0) + 1}})
        return dict(base, result={'issues': []})

    def cancel(self):
        pass


class DecideWhileChatGPTWritesTests(unittest.TestCase):
    def test_a_waiting_read_is_not_a_bad_reply_and_a_checked_action_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = AgentRuntime(Path(td))
            fake = Executor()
            runtime.wc_executor = fake
            try:
                tid = runtime.store.submit([{'action': 'WINCONTROL_DECIDE', 'exchange_id': 'wincontrol-t-initial'}], stage='WinControl',
                                           context={'wincontrol_task': True, 'wincontrol_command': 'x', 'wincontrol_round': 0})
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and runtime.store.get(tid)['status'] not in ('completed', 'failed', 'needs_review'):
                    time.sleep(.05)
                task = runtime.store.get(tid)
                self.assertEqual(task['status'], 'completed', task.get('error'))
                names = [c['action'] for c in fake.calls]
                self.assertEqual(names, ['WINCONTROL_DECIDE', 'WINCONTROL_DECIDE', 'MAN_STATUS', 'SEND_CHATGPT', 'WINCONTROL_DECIDE'])
                self.assertFalse(any(str(a.get('exchange_id', '')).endswith('-fix') for a in task['actions']))
            finally:
                runtime.shutdown.set()
                runtime.thread.join(2)
                runtime.wc_thread.join(2)
                runtime.store.close()

    def test_a_new_decision_replaces_steps_still_queued(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = AgentRuntime(Path(td))
            runtime.shutdown.set()
            runtime.thread.join(2)
            runtime.wc_thread.join(2)
            try:
                tid = runtime.store.submit([{'action': 'WINCONTROL_DECIDE'}, {'action': 'SEND_CHATGPT', 'exchange_id': 'stale-fix'}], stage='WinControl',
                                           context={'wincontrol_task': True, 'wincontrol_round': 0})
                runtime.store.claim(tid)
                task = runtime.store.get(tid)
                result = {'success': True, 'result': {'decision': parse_decision('{"status":"continue","summary":"s","actions":[{"action":"MAN_STATUS"}]}'), 'context': {'wincontrol_round': 1}}}
                runtime.wincontrol_next(tid, 0, task, result)
                actions = runtime.store.get(tid)['actions']
                self.assertEqual([a['action'] for a in actions], ['WINCONTROL_DECIDE', 'MAN_STATUS', 'SEND_CHATGPT', 'WINCONTROL_DECIDE'])
                self.assertNotIn('stale-fix', [a.get('exchange_id') for a in actions])
            finally:
                runtime.store.close()


if __name__ == '__main__':
    unittest.main()
