"""Telegram for WinControl: pairing, one owner, each message once, commands go to WinControl, reports (no network)."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import test_guard  # noqa: F401
import telegram_bridge as tb

TOKEN = '123456789:' + 'A' * 35
OWNER, STRANGER = 111, 222


class FakeApi:
    def __init__(self):
        self.updates = []; self.sent = []; self.posts = []
        self.state = {'version': '0.2.23', 'automation': {'online': True, 'enabled': True, 'tasks': []}, 'queue': [],
                      'studio': {'status': 'connected'}, 'extension': {'status': 'responding', 'version': '0.5.21'}}
    def __call__(self, url, body=None, timeout=10, origin=False):
        if url.endswith('/getUpdates'):
            out = [u for u in self.updates if u['update_id'] >= body['offset']]; return {'ok': True, 'result': out}
        if url.endswith('/sendMessage'):
            self.sent.append(body['text']); return {'ok': True}
        if url.endswith('/api/state'):
            return self.state
        if url.endswith('/api/automation'):
            assert origin, 'MAN refuses writes without its own Origin'
            self.posts.append(body); return {'task_id': 't1', 'summary': 'Đã gửi nhiệm vụ đến ChatGPT.'}
        raise AssertionError(url)


def msg(uid, text, sender=OWNER, chat=None, kind='private'):
    return {'update_id': uid, 'message': {'text': text, 'from': {'id': sender}, 'chat': {'id': chat or sender, 'type': kind}}}


class TelegramBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        p1 = patch.object(tb, '_protect', lambda raw: b'enc:' + raw); p2 = patch.object(tb, '_unprotect', lambda blob: blob[4:])
        p1.start(); p2.start(); self.addCleanup(p1.stop); self.addCleanup(p2.stop)
        self.api = FakeApi(); self.now = 1000.0
        self.b = tb.TelegramBridge(self.tmp.name, api=self.api, clock=lambda: self.now)

    def pair(self):
        code = self.b.configure(TOKEN)['pair_code']
        self.api.updates.append(msg(1, '/pair ' + code)); self.b.poll_once(); self.api.sent.clear()

    def test_token_is_checked_saved_encrypted_and_never_shown(self):
        with self.assertRaises(ValueError): self.b.configure('not a token')
        snap = self.b.configure(TOKEN)
        self.assertTrue(snap['configured']); self.assertRegex(snap['pair_code'], r'^\d{6}$')
        self.assertNotIn(TOKEN, json.dumps(snap)); self.assertNotIn(TOKEN, (Path(self.tmp.name) / 'telegram.json').read_text(encoding='utf8'))
        self.assertEqual((Path(self.tmp.name) / 'telegram_token.bin').read_bytes(), b'enc:' + TOKEN.encode())
        again = tb.TelegramBridge(self.tmp.name, api=self.api, clock=lambda: self.now)
        self.assertTrue(again.snapshot()['configured'], 'a MAN restart keeps the token')

    def test_only_the_right_code_in_a_private_chat_pairs(self):
        code = self.b.configure(TOKEN)['pair_code']
        self.api.updates += [msg(1, '/pair 000000' if code != '000000' else '/pair 111111', STRANGER),
                             msg(2, '/pair ' + code, OWNER, chat=-5, kind='group')]
        self.b.poll_once()
        self.assertFalse(self.b.snapshot()['paired']); self.assertEqual(self.api.sent, [], 'strangers get no answer')
        self.api.updates.append(msg(3, '/pair ' + code)); self.b.poll_once()
        self.assertTrue(self.b.snapshot()['paired']); self.assertIn('Đã ghép nối', self.api.sent[0])

    def test_an_expired_code_does_not_pair(self):
        code = self.b.configure(TOKEN)['pair_code']; self.now += tb.PAIR_TTL + 1
        self.api.updates.append(msg(1, '/pair ' + code)); self.b.poll_once()
        self.assertFalse(self.b.snapshot()['paired'])

    def test_owner_text_goes_to_wincontrol_once(self):
        self.pair()
        self.api.updates.append(msg(5, 'Kiểm tra tiến độ dự án Thái sư Trần Thủ Độ'))
        self.b.poll_once(); self.b.poll_once()  # the same update is offered again: handled once
        self.assertEqual(self.api.posts, [{'command': 'wincontrol', 'text': 'Kiểm tra tiến độ dự án Thái sư Trần Thủ Độ', 'request_id': 'tg-5'}])
        self.assertIn('Đã giao cho WinControl', self.api.sent[0])
        restarted = tb.TelegramBridge(self.tmp.name, api=self.api, clock=lambda: self.now); restarted.poll_once()
        self.assertEqual(len(self.api.posts), 1, 'a restart does not handle it again')

    def test_other_users_are_ignored_after_pairing(self):
        self.pair()
        self.api.updates.append(msg(6, 'Tạm dừng dự án X', STRANGER)); self.b.poll_once()
        self.assertEqual(self.api.posts, []); self.assertEqual(self.api.sent, [])

    def test_status_and_stop(self):
        self.pair()
        self.api.state['queue'] = [{'id': 'p', 'name': 'Thái sư', 'status': 'running', 'current_stage': 'Ảnh'}]
        self.api.state['automation']['tasks'] = [{'id': 'w1', 'status': 'running', 'context': {'wincontrol_task': True, 'wincontrol_command': 'việc A'}}]
        self.api.updates += [msg(7, '/status'), msg(8, '/stop')]; self.b.poll_once()
        self.assertIn('Thái sư: running', self.api.sent[0])
        self.assertEqual(self.api.posts, [{'command': 'wincontrol_cancel', 'task_id': 'w1'}])

    def test_reports_changes_once_and_not_old_news(self):
        self.pair()
        self.api.state['queue'] = [{'id': 'p', 'name': 'Thái sư', 'status': 'running'}]
        old = {'id': 'w0', 'status': 'completed', 'context': {'wincontrol_task': True, 'wincontrol_command': 'cũ'}, 'results': []}
        self.api.state['automation']['tasks'] = [old]
        self.b.report_once(); self.assertEqual(self.api.sent, [], 'the first look only records the present')
        done = {'id': 'w1', 'status': 'completed', 'context': {'wincontrol_task': True, 'wincontrol_command': 'Tạm dừng Thái sư'},
                'results': [{'result': {'decision': {'summary': 'Đã tạm dừng và xác nhận.'}}}]}
        self.api.state['automation']['tasks'] = [old, done]; self.api.state['queue'][0]['status'] = 'paused'
        self.b.report_once(); self.b.report_once()
        self.assertEqual(len(self.api.sent), 2)
        self.assertIn('Đã tạm dừng và xác nhận', self.api.sent[0] + self.api.sent[1])
        self.assertIn('running → paused', self.api.sent[0] + self.api.sent[1])


if __name__ == '__main__':
    unittest.main()
