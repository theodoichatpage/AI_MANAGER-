"""WinControl production control: pause/resume a MAN project through MAN's own /api/queue (fake MAN, no real queue)."""
import json, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import test_guard  # noqa: F401  (never touch the real MAN data)
from automation_agent import action_worker
from automation_agent.wincontrol_chat_loop import validate_actions, resolve_project, named_by_user, man_queue, man_health, initial_prompt

QUEUE = [{'id': '99e63ac3-5877-4e1e-8c9a-67bccf30a995', 'name': 'Thái sư Trần Thủ Độ', 'status': 'paused', 'current_stage': 'Tạm dừng', 'action_done': 94, 'action_total': 384},
         {'id': 'b7fbe160-0000-0000-0000-000000000000', 'name': 'Thử 3 tab E - Nguyễn Du', 'status': 'stopped'},
         {'id': '1bc7f211-0000-0000-0000-000000000000', 'name': 'Thử 3 tab E - Nguyễn Du', 'status': 'stopped'}]


class FakeMan(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, data):
        body = json.dumps(data).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body)
    def do_GET(self): self.reply({'queue': self.server.queue})
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        # Like server.py: writes only from MAN's own page origin.
        if self.headers.get('Origin') != 'http://127.0.0.1:%d' % self.server.server_address[1]:
            body = json.dumps({'error': 'Nguồn truy cập không hợp lệ'}).encode()
            self.send_response(400); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body); return
        self.server.posts.append(data)
        row = next(q for q in self.server.queue if q['id'] == data['id'])
        row['status'] = {'resume': 'running', 'pause': 'paused'}[data['action']]
        self.reply({'ok': True})


class ManQueueTests(unittest.TestCase):
    def setUp(self):
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), FakeMan); self.http.queue = [dict(q) for q in QUEUE]; self.http.posts = []
        threading.Thread(target=self.http.serve_forever, daemon=True).start(); self.addCleanup(self.http.shutdown)
        self.ctx = {'wincontrol_task': True, 'man_state_url': 'http://127.0.0.1:%d/api/state' % self.http.server_address[1]}

    def run_action(self, op, project, command):
        a = validate_actions([{'action': 'MAN_QUEUE', 'op': op, 'project': project}])[0]
        return action_worker.dispatch(a, dict(self.ctx, wincontrol_command=command), '.', {})

    def test_only_pause_and_resume_with_a_project(self):
        for bad in ({'op': 'start', 'project': 'x'}, {'op': 'stop', 'project': 'x'}, {'op': 'resume'}, {'op': 'resume', 'project': ''}):
            with self.assertRaises(ValueError):
                validate_actions([dict(bad, action='MAN_QUEUE')])

    def test_resume_the_project_the_user_named_and_confirm_from_man_state(self):
        r = self.run_action('resume', 'Thái sư Trần Thủ Độ', 'Chạy tiếp dự án thái sư trần thủ độ giúp tôi')
        self.assertEqual((r['changed'], r['status_before'], r['status_after']), (True, 'paused', 'running'))
        self.assertEqual(self.http.posts, [{'action': 'resume', 'id': QUEUE[0]['id']}])

    def test_resume_twice_sends_once(self):
        self.run_action('resume', QUEUE[0]['id'], 'tiếp tục Thái sư Trần Thủ Độ')
        r = self.run_action('resume', QUEUE[0]['id'], 'tiếp tục Thái sư Trần Thủ Độ')
        self.assertFalse(r['changed']); self.assertEqual(len(self.http.posts), 1)

    def test_resume_refused_when_the_user_did_not_name_the_project(self):
        with self.assertRaises(action_worker.NotExecuted) as e:
            self.run_action('resume', 'Thái sư Trần Thủ Độ', 'Kiểm tra tình trạng MAN rồi làm tiếp việc còn dở')
        self.assertIn('MAN_RESUME_NEEDS_USER_NAMED_PROJECT', str(e.exception)); self.assertEqual(self.http.posts, [])

    def test_ambiguous_or_unknown_name_is_refused_without_action(self):
        with self.assertRaises(action_worker.NotExecuted):
            self.run_action('resume', 'Thử 3 tab E - Nguyễn Du', 'tiếp tục Thử 3 tab E - Nguyễn Du')
        with self.assertRaises(action_worker.NotExecuted):
            self.run_action('pause', 'Không có', 'tạm dừng Không có')
        self.assertEqual(self.http.posts, [])

    def test_pause_of_a_project_not_running_changes_nothing(self):
        r = self.run_action('pause', 'Thái sư Trần Thủ Độ', 'tạm dừng sản xuất')
        self.assertFalse(r['changed']); self.assertEqual(self.http.posts, [])

    def test_man_refusal_reason_is_reported(self):
        self.http.queue[0]['status'] = 'paused'
        real = FakeMan.do_POST
        def refuse(h):
            h.rfile.read(int(h.headers['Content-Length'])); body = json.dumps({'error': 'Dự án không ở trạng thái tạm dừng'}).encode()
            h.send_response(400); h.send_header('Content-Type', 'application/json'); h.end_headers(); h.wfile.write(body)
        FakeMan.do_POST = refuse; self.addCleanup(setattr, FakeMan, 'do_POST', real)
        with self.assertRaises(RuntimeError) as e:
            self.run_action('resume', 'Thái sư Trần Thủ Độ', 'tiếp tục Thái sư Trần Thủ Độ')
        self.assertNotIsInstance(e.exception, action_worker.NotExecuted, 'sent to MAN: outcome uncertain, stop for review')
        self.assertIn('Dự án không ở trạng thái tạm dừng', str(e.exception))

    def test_named_by_user_by_id_prefix(self):
        self.assertTrue(named_by_user('resume 99e63ac3', QUEUE[0]))
        self.assertFalse(named_by_user('resume 99e6', QUEUE[0]))

    def test_resolve_by_id_and_status_lists_ids_and_progress(self):
        self.assertEqual(resolve_project(QUEUE, QUEUE[0]['id'])['name'], 'Thái sư Trần Thủ Độ')
        row = man_health({'queue': QUEUE})['queue'][0]
        self.assertEqual((row['id'], row['progress']), (QUEUE[0]['id'], [94, 384]))

    def test_prompt_offers_man_queue_and_forbids_other_production_commands(self):
        text = initial_prompt('x', {})
        self.assertIn('MAN_QUEUE', text); self.assertIn('Never start, retry, stop or delete projects', text)


if __name__ == '__main__':
    unittest.main()
