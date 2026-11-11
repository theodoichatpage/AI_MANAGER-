import tempfile
import time
import unittest
from pathlib import Path

from automation_agent.runtime import AgentRuntime
from automation_agent.wincontrol_chat_loop import parse_decision


class Executor:
    def __init__(self):
        self.calls = []
        self.replies = [parse_decision('{"status":"continue","summary":"Gõ","actions":[{"action":"TYPE_TEXT","target_app":"notepad","selector":{"class_name":"Edit"},"text":"x"}]}'),
                        {'status': 'complete', 'summary': 'Xong', 'actions': []}]

    def run(self, tid, action, context, cancel, retry=0):
        self.calls.append(action['action'])
        base = {'task_id': tid, 'action': action['action'], 'retry_count': retry}
        if action['action'] == 'WINCONTROL_DECIDE':
            return dict(base, success=True, status='completed', error=None, result={'decision': self.replies.pop(0), 'context': {}})
        if action['action'] == 'TYPE_TEXT':
            return dict(base, success=False, status='failed', error='chưa nhập gì', error_code='NOT_EXECUTED', result={})
        return dict(base, success=True, status='completed', error=None, result={})

    def cancel(self):
        pass


class NotExecutedTests(unittest.TestCase):
    def test_an_input_refused_before_anything_happened_goes_back_to_chatgpt(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = AgentRuntime(Path(td))
            fake = Executor()
            runtime.wc_executor = fake
            try:
                tid = runtime.store.submit([{'action': 'WINCONTROL_DECIDE'}], stage='WinControl', context={'wincontrol_task': True, 'wincontrol_round': 0})
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and runtime.store.get(tid)['status'] not in ('completed', 'failed', 'needs_review'):
                    time.sleep(.05)
                task = runtime.store.get(tid)
                self.assertEqual(task['status'], 'completed', task.get('error'))
                self.assertEqual(fake.calls, ['WINCONTROL_DECIDE', 'TYPE_TEXT', 'SEND_CHATGPT', 'WINCONTROL_DECIDE'])
            finally:
                runtime.shutdown.set()
                runtime.thread.join(2)
                runtime.wc_thread.join(2)
                runtime.store.close()


if __name__ == '__main__':
    unittest.main()
