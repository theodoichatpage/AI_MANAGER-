"""WinControl recovery: no duplicate ChatGPT sends, MCP reconnect on reads, ChatGPT asked to fix a bad reply."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from automation_agent import chatgpt_mcp as m
from automation_agent.runtime import AgentRuntime

URL = 'https://chatgpt.com/c/dedicated-test'


class SendRecovery(unittest.TestCase):
    def test_prompt_already_delivered_is_not_sent_again(self):
        state = dict(completion_verified=False, url=URL, fingerprint='b' * 64, turnCount=7,
                     lastUserText='[wincontrol-abc-1] WinControl tool result')
        with patch.object(m, 'observe', return_value=state), patch.object(m, '_config', return_value={}), patch.object(m, '_call') as call:
            result = m.send({}, {}, URL, '[wincontrol-abc-1] WinControl tool result', 'wincontrol-abc-1', {})
        call.assert_not_called()
        self.assertTrue(result['recovered'])
        self.assertEqual(result['submission'], 'received')

    def test_snapshot_reconnects_after_closed_connection_but_send_does_not_repeat(self):
        calls = []

        def flaky(c, operation, text=None):
            calls.append(operation)
            if len(calls) == 1:
                raise RuntimeError('MCP_ACTION_FAILED: McpError: MCP error -32000: Connection closed')
            return {'snapshot': 'ok'}
        with patch.object(m, '_call_once', side_effect=flaky), patch.object(m.time, 'sleep'):
            self.assertEqual(m._call({}, 'snapshot'), {'snapshot': 'ok'})
        self.assertEqual(calls, ['snapshot', 'snapshot'])
        with patch.object(m, '_call_once', side_effect=RuntimeError('MCP_ACTION_FAILED: closed')) as once:
            with self.assertRaises(RuntimeError):
                m._call({}, 'fill_click', 'hello')
            self.assertEqual(once.call_count, 1)

    def test_receipt_accepts_whitespace_differences_from_page_rendering(self):
        self.assertTrue(m._same_prompt('[x] a\nb  c', '[x] a b c'))
        self.assertFalse(m._same_prompt('', 'a'))


class Executor:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    def run(self, tid, action, context, cancel, retry=0):
        self.calls.append(dict(action))
        name = action['action']
        if name == 'WINCONTROL_DECIDE':
            decision = self.decisions.pop(0)
            return {'task_id': tid, 'action': name, 'success': True, 'status': 'completed', 'error': None, 'retry_count': retry,
                    'result': {'decision': decision, 'context': {'wincontrol_round': context.get('wincontrol_round', 0) + 1}}}
        return {'task_id': tid, 'action': name, 'success': True, 'status': 'completed', 'error': None, 'retry_count': retry,
                'result': {'context': {}}}

    def cancel(self):
        pass


def run_task(decisions):
    td = tempfile.TemporaryDirectory()
    runtime = AgentRuntime(Path(td.name))
    fake = Executor(decisions)
    runtime.executor = fake
    runtime.wc_executor = fake
    try:
        tid = runtime.store.submit([{'action': 'WINCONTROL_DECIDE'}], stage='WinControl',
                                   context={'wincontrol_task': True, 'wincontrol_command': 'Mở Notepad', 'wincontrol_round': 0})
        runtime.start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and runtime.store.get(tid)['status'] not in ('completed', 'failed', 'needs_review'):
            time.sleep(.02)
        return runtime.store.get(tid), fake.calls
    finally:
        runtime.shutdown.set()
        runtime.thread.join(2)
        runtime.store.close()
        td.cleanup()


class DecisionRecovery(unittest.TestCase):
    def test_unusable_reply_gets_one_correction_then_continues(self):
        task, calls = run_task([
            {'status': 'invalid', 'summary': 'WINCONTROL_CHATGPT_JSON_INVALID', 'actions': [], 'reply': 'Tôi sẽ mở Notepad'},
            {'status': 'complete', 'summary': 'Xong', 'actions': []},
        ])
        self.assertEqual(task['status'], 'completed')
        self.assertEqual([c['action'] for c in calls], ['WINCONTROL_DECIDE', 'SEND_CHATGPT', 'WINCONTROL_DECIDE'])
        fix = calls[1]
        self.assertIn('wincontrol_correction', fix)
        self.assertTrue(fix['text'].startswith('[' + fix['exchange_id'] + '] '))
        self.assertIn('JSON_INVALID', fix['text'])

    def test_not_allowed_action_is_corrected_not_executed(self):
        task, calls = run_task([
            {'status': 'continue', 'summary': 'x', 'actions': [{'action': 'STUDIO_IMAGES'}]},
            {'status': 'complete', 'summary': 'Xong', 'actions': []},
        ])
        self.assertEqual(task['status'], 'completed')
        self.assertNotIn('STUDIO_IMAGES', [c['action'] for c in calls])

    def test_repeated_bad_replies_stop_for_review(self):
        bad = {'status': 'invalid', 'summary': 'WINCONTROL_CHATGPT_JSON_INVALID', 'actions': [], 'reply': '?'}
        task, calls = run_task([bad, bad, bad])
        self.assertEqual(task['status'], 'needs_review')
        self.assertEqual([c['action'] for c in calls].count('SEND_CHATGPT'), 2)
        self.assertEqual(len({c['exchange_id'] for c in calls if c['action'] == 'SEND_CHATGPT'}), 2)


if __name__ == '__main__': unittest.main()
