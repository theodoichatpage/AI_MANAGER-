import json, tempfile, threading, time, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
import server, story_orders

EXT = 'chrome-extension://abcdefghijklmnop'
PAGE = 'http://127.0.0.1:8765'
ORDER = {'project_id': 's_ashen', 'project_title': 'The Ashen Crown', 'chapter_start': 8, 'chapter_count': 2, 'story_bible_version': 3,
         'target_word_count': 2200, 'writer': 'sudowrite', 'reviser': 'chatgpt', 'idempotency_key': 'mgr-test-0001'}


class StoryOrdersHTTPTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = server._STORY
        server._STORY = story_orders.StoryStore(Path(self.tmp.name) / 'story.sqlite3')
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
        server._STORY.db.close(); server._STORY = self.old; self.tmp.cleanup()

    def call(self, method, path, body=None, origin=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if origin: headers['Origin'] = origin
        if token: headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request('http://127.0.0.1:%d/api/story/%s' % (self.http.server_port, path), method=method,
                                     data=json.dumps(body).encode() if body is not None else (b'{}' if method == 'POST' else None), headers=headers)
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as e: return e.code, json.load(e)

    def pair(self):
        code = self.call('POST', 'pairing-code', origin=PAGE)[1]['code']
        status, body = self.call('POST', 'pair', {'code': code, 'extension_version': '0.5.0'}, origin=EXT)
        self.assertEqual(status, 200); return body['token']

    def test_pairing_needs_a_fresh_code_from_the_page_and_an_extension_origin(self):
        self.assertEqual(self.call('POST', 'pairing-code', origin='https://evil.example')[0], 403)
        code = self.call('POST', 'pairing-code', origin=PAGE)[1]['code']
        self.assertEqual(self.call('POST', 'pair', {'code': code}, origin='https://evil.example')[0], 403)
        self.assertEqual(self.call('POST', 'pair', {'code': '000000' if code != '000000' else '111111'}, origin=EXT)[0], 403)
        token = self.call('POST', 'pair', {'code': code}, origin=EXT)[1]['token']
        self.assertGreaterEqual(len(token), 40)
        self.assertEqual(self.call('POST', 'pair', {'code': code}, origin=EXT)[0], 403, 'a code works once')

    def test_adapter_calls_need_the_token_and_the_pinned_origin_and_revoke_cuts_them(self):
        token = self.pair()
        self.assertEqual(self.call('GET', 'health', token=token, origin=EXT)[0], 200)
        self.assertEqual(self.call('GET', 'health', origin=EXT)[0], 401)
        self.assertEqual(self.call('GET', 'health', token='x' * 43, origin=EXT)[0], 401)
        self.assertEqual(self.call('GET', 'health', token=token, origin='chrome-extension://other')[0], 403)
        self.assertEqual(self.call('GET', 'health', token=token)[0], 200, 'Chrome sends no Origin on extension GETs')
        req = urllib.request.Request('http://127.0.0.1:%d/api/story/health' % self.http.server_port, headers={'Authorization': 'Bearer ' + token, 'Sec-Fetch-Site': 'cross-site'})
        with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 403, 'a cross-site request without Origin is refused')
        self.assertEqual(self.call('POST', 'revoke', origin=PAGE)[0], 200)
        self.assertEqual(self.call('GET', 'health', token=token, origin=EXT)[0], 401)

    def test_orders_are_validated_idempotent_and_never_overlap(self):
        self.assertEqual(self.call('POST', 'orders', {**ORDER, 'max_revision_rounds': 4}, origin=PAGE)[0], 400)
        self.assertEqual(self.call('POST', 'orders', {**ORDER, 'api_key': 'sk-x'}, origin=PAGE)[0], 400)
        self.assertEqual(self.call('POST', 'orders', ORDER, origin=EXT)[0], 403, 'the extension cannot create orders')
        status, first = self.call('POST', 'orders', ORDER, origin=PAGE)
        self.assertEqual(status, 201); o = first['order']
        self.assertEqual((o['status'], o['approval_threshold'], o['max_revision_rounds'], o['schema']), ('queued', 85, 3, 1))
        status, again = self.call('POST', 'orders', ORDER, origin=PAGE)
        self.assertEqual((status, again['order']['order_id'], again['created']), (200, o['order_id'], False))
        status, body = self.call('POST', 'orders', {**ORDER, 'idempotency_key': 'mgr-test-0002', 'chapter_start': 9}, origin=PAGE)
        self.assertEqual((status, body['error']), (409, 'overlap'))
        self.assertEqual(self.call('POST', 'orders', {**ORDER, 'idempotency_key': 'mgr-test-0003', 'chapter_start': 10}, origin=PAGE)[0], 201)

    def test_adapter_picks_up_acks_and_reports_events_until_the_order_is_done(self):
        token = self.pair(); oid = self.call('POST', 'orders', ORDER, origin=PAGE)[1]['order']['order_id']
        queued = self.call('GET', 'orders?status=queued', token=token, origin=EXT)[1]['orders']
        self.assertEqual([x['order_id'] for x in queued], [oid])
        self.assertEqual(self.call('POST', f'orders/{oid}/ack', {'order_id': oid, 'result': 'accepted', 'chapters': [{'chapter_no': 8, 'state': 'queued'}]}, token=token, origin=EXT)[0], 200)
        self.assertEqual(self.call('GET', 'orders?status=queued', token=token, origin=EXT)[1]['orders'], [])
        ev = lambda eid, ch, state, at, **k: {'schema': 1, 'event_id': eid, 'order_id': oid, 'job_key': f'{oid}:{ch}', 'chapter_no': ch, 'state': state, 'at': at, **k}
        r = self.call('POST', 'events', {'events': [ev('evt_00000001', 8, 'reviewing', '2026-11-05T10:00:00Z'), ev('evt_00000002', 8, 'review_passed', '2026-11-05T10:05:00Z', score=88, round=1, version=2)]}, token=token, origin=EXT)[1]
        self.assertEqual((r['accepted'], r['duplicates']), (2, 0))
        self.assertEqual(self.call('POST', 'events', {'events': [ev('evt_00000002', 8, 'review_passed', '2026-11-05T10:05:00Z')]}, token=token, origin=EXT)[1]['duplicates'], 1)
        self.call('POST', 'events', {'events': [ev('evt_00000003', 8, 'writing', '2026-11-05T09:00:00Z')]}, token=token, origin=EXT)
        order, chapters = server._STORY.order(oid)
        self.assertEqual((order['status'], chapters[0]['state'], chapters[0]['score']), ('running', 'review_passed', 88), 'a late, older event does not roll the state back')
        self.call('POST', 'events', {'events': [ev('evt_00000004', 9, 'human_review', '2026-11-05T11:00:00Z')]}, token=token, origin=EXT)
        self.assertEqual(server._STORY.order(oid)[0]['status'], 'done')
        bad = ev('evt_00000005', 9, 'reviewing', '2026-11-05T11:00:00Z'); bad['job_key'] = 'ord_other00:9'
        self.assertEqual(self.call('POST', 'events', {'events': [bad]}, token=token, origin=EXT)[0], 400)

    def test_controls_reach_the_adapter_in_order_and_cancel_stops_the_order(self):
        token = self.pair(); oid = self.call('POST', 'orders', ORDER, origin=PAGE)[1]['order']['order_id']
        self.call('POST', f'orders/{oid}/control', {'action': 'pause'}, origin=PAGE)
        self.call('POST', f'orders/{oid}/control', {'action': 'cancel'}, origin=PAGE)
        self.assertEqual(self.call('POST', f'orders/{oid}/control', {'action': 'delete'}, origin=PAGE)[0], 400)
        c = self.call('GET', 'controls?since=0', token=token, origin=EXT)[1]
        self.assertEqual([x['action'] for x in c['controls']], ['pause', 'cancel'])
        self.assertEqual(self.call('GET', f'controls?since={c["next"]}', token=token, origin=EXT)[1]['controls'], [])
        self.assertEqual(server._STORY.order(oid)[0]['status'], 'cancelled')

    def test_story_page_is_served(self):
        with urllib.request.urlopen('http://127.0.0.1:%d/story' % self.http.server_port) as r:
            self.assertIn('Sản xuất truyện', r.read().decode())


if __name__ == '__main__':
    unittest.main()
