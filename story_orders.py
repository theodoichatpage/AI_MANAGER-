"""Story production orders for the Sudowrite Adapter (Xưởng Nội Dung).

Manager keeps orders the user creates, a progress mirror built from Xưởng's events, and the
pairing with one Adapter extension. Chapters themselves live in Xưởng (single source of truth).
Contract: XUONG_NOI_DUNG/docs/sudowrite-adapter/PHASE2_PROTOCOL.md and shared/schemas/.
"""
import hmac, json, re, secrets, sqlite3, threading, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

SCHEMA = 1
PAGE_ORIGINS = ('http://127.0.0.1:8765', 'http://localhost:8765')
CHAPTER_STATES = ('queued', 'writing', 'waiting_user', 'reviewing', 'revising', 'review_passed', 'human_review', 'approved',
                  'ready_to_publish', 'published', 'publish_failed', 'failed', 'paused', 'cancelled', 'skipped_existing')
FINISHED = {'review_passed', 'human_review', 'approved', 'ready_to_publish', 'published', 'skipped_existing', 'cancelled'}
BROKEN = {'failed', 'publish_failed'}
ID = re.compile(r'^[A-Za-z0-9_-]{8,64}$')
JOB_KEY = re.compile(r'^[A-Za-z0-9_-]{8,64}:[0-9]{1,5}$')
CODE_TTL = 300
MAX_BODY = 256_000


def now_iso():
    t = datetime.now(timezone.utc)
    return t.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (t.microsecond // 1000)


def norm_time(value):
    """One sortable format (UTC, milliseconds) so string comparison orders events correctly."""
    try:
        t = datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
        return t.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (t.microsecond // 1000)
    except (TypeError, ValueError):
        return now_iso()


class StoryError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message); self.status, self.code, self.message = status, code, message


def _int(data, key, lo, hi, default=None):
    v = data.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise StoryError(400, 'invalid_order', f'{key} phải là số nguyên từ {lo} đến {hi}')
    return v


def _str(data, key, max_len, pattern=None, required=True, default=''):
    v = data.get(key, default)
    if v is None: v = ''
    if not isinstance(v, str) or len(v) > max_len or (required and not v.strip()) or (pattern and v and not re.fullmatch(pattern, v)):
        raise StoryError(400, 'invalid_order', f'{key} không hợp lệ')
    return v.strip()


def clean_order(data):
    """Validates a new order from the Manager page (mirrors production-order.schema.json)."""
    if not isinstance(data, dict): raise StoryError(400, 'invalid_order', 'Lệnh phải là một đối tượng')
    allowed = {'idempotency_key', 'project_id', 'project_title', 'chapter_start', 'chapter_count', 'story_bible_version', 'target_word_count',
               'writing_language', 'writing_style', 'writer', 'reviser', 'approval_threshold', 'max_revision_rounds'}
    extra = set(data) - allowed
    if extra: raise StoryError(400, 'invalid_order', 'Trường không hỗ trợ: ' + ', '.join(sorted(extra)))
    order = {
        'schema': SCHEMA,
        'idempotency_key': _str(data, 'idempotency_key', 128) if data.get('idempotency_key') else 'mgr-' + secrets.token_hex(8),
        'project_id': _str(data, 'project_id', 80),
        'project_title': _str(data, 'project_title', 200, required=False),
        'chapter_start': _int(data, 'chapter_start', 1, 10000),
        'chapter_count': _int(data, 'chapter_count', 1, 50),
        'story_bible_version': _int(data, 'story_bible_version', 1, 10**9),
        'target_word_count': _int(data, 'target_word_count', 300, 10000, 2000),
        'writing_language': _str(data, 'writing_language', 5, r'[a-z]{2}(-[A-Z]{2})?', default='en'),
        'writing_style': _str(data, 'writing_style', 2000, required=False),
        'writer': data.get('writer', 'chatgpt'), 'reviser': data.get('reviser', 'chatgpt'),
        'approval_threshold': _int(data, 'approval_threshold', 50, 100, 85),
        'max_revision_rounds': _int(data, 'max_revision_rounds', 0, 3, 3),
    }
    if len(order['idempotency_key']) < 8: raise StoryError(400, 'invalid_order', 'idempotency_key quá ngắn')
    for k in ('writer', 'reviser'):
        if order[k] not in ('chatgpt', 'sudowrite'): raise StoryError(400, 'invalid_order', f'{k} phải là chatgpt hoặc sudowrite')
    return order


class StoryStore:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS story_orders(order_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
            status TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS story_chapters(order_id TEXT NOT NULL, chapter_no INTEGER NOT NULL, state TEXT NOT NULL, round INTEGER,
            score INTEGER, version INTEGER, words INTEGER, message TEXT, link TEXT, at TEXT NOT NULL, PRIMARY KEY(order_id, chapter_no));
          CREATE TABLE IF NOT EXISTS story_events(event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, payload TEXT NOT NULL, received_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS story_controls(seq INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL, action TEXT NOT NULL, at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS story_pairing(id INTEGER PRIMARY KEY CHECK(id=1), token TEXT, extension_origin TEXT, extension_version TEXT,
            code TEXT, code_expires REAL, paired_at TEXT, last_seen TEXT);
          INSERT OR IGNORE INTO story_pairing(id) VALUES(1);''')

    # ---- pairing
    def pairing(self):
        with self.lock:
            r = self.db.execute('SELECT token,extension_origin,extension_version,paired_at,last_seen FROM story_pairing WHERE id=1').fetchone()
        return {'paired': bool(r[0]), 'extension_origin': r[1], 'extension_version': r[2], 'paired_at': r[3], 'last_seen': r[4]}

    def new_code(self):
        code = f'{secrets.randbelow(10**6):06d}'
        with self.lock: self.db.execute('UPDATE story_pairing SET code=?,code_expires=? WHERE id=1', (code, time.time() + CODE_TTL))
        return {'code': code, 'expires_at': datetime.fromtimestamp(time.time() + CODE_TTL, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}

    def pair(self, code, origin, version):
        if not origin.startswith('chrome-extension://'): raise StoryError(403, 'forbidden', 'Chỉ extension được ghép đôi')
        with self.lock:
            saved, exp = self.db.execute('SELECT code,code_expires FROM story_pairing WHERE id=1').fetchone()
            if not saved or not exp or time.time() > exp or not hmac.compare_digest(str(code), saved):
                raise StoryError(403, 'bad_code', 'Mã ghép đôi sai hoặc đã hết hạn. Tạo mã mới trong AI Manager.')
            token = secrets.token_urlsafe(32)
            self.db.execute('UPDATE story_pairing SET token=?,extension_origin=?,extension_version=?,code=NULL,code_expires=NULL,paired_at=?,last_seen=? WHERE id=1',
                            (token, origin, str(version)[:20], now_iso(), now_iso()))
        return {'token': token}

    def revoke(self):
        with self.lock: self.db.execute('UPDATE story_pairing SET token=NULL,extension_origin=NULL,code=NULL,code_expires=NULL,paired_at=NULL WHERE id=1')

    def check_adapter(self, headers):
        auth = headers.get('Authorization', '')
        with self.lock: token, origin = self.db.execute('SELECT token,extension_origin FROM story_pairing WHERE id=1').fetchone()
        given = auth[7:] if auth.startswith('Bearer ') else ''
        if not token or not given or not hmac.compare_digest(given, token): raise StoryError(401, 'unauthorized', 'Adapter chưa ghép đôi hoặc token đã bị thu hồi')
        # Chrome sends Origin on the extension's POSTs but not on its GETs. A present Origin must be the paired
        # extension; without one, a request the browser marks as cross-site (a web page) is refused.
        given_origin = headers.get('Origin', '')
        if given_origin and given_origin != origin: raise StoryError(403, 'forbidden', 'Nguồn không khớp extension đã ghép đôi')
        if not given_origin and headers.get('Sec-Fetch-Site', '') == 'cross-site': raise StoryError(403, 'forbidden', 'Nguồn truy cập không hợp lệ')
        with self.lock: self.db.execute('UPDATE story_pairing SET last_seen=? WHERE id=1', (now_iso(),))

    # ---- orders
    def _order(self, row):
        o = json.loads(row[0]); o.update(order_id=row[1], status=row[2], created_at=row[3])
        if row[4]: o['reason'] = row[4]
        return o

    def create_order(self, data):
        order = clean_order(data)
        with self.lock:
            row = self.db.execute('SELECT payload,order_id,status,created_at,reason FROM story_orders WHERE idempotency_key=?', (order['idempotency_key'],)).fetchone()
            if row: return self._order(row), False
            busy = self.db.execute("SELECT payload FROM story_orders WHERE status IN ('queued','accepted','running')").fetchall()
            for (p,) in busy:
                o = json.loads(p)
                if o['project_id'] == order['project_id'] and o['chapter_start'] < order['chapter_start'] + order['chapter_count'] and order['chapter_start'] < o['chapter_start'] + o['chapter_count']:
                    raise StoryError(409, 'overlap', 'Đã có lệnh đang chạy cho các chương này của truyện. Chờ xong hoặc hủy lệnh đó.')
            oid, at = 'ord_' + secrets.token_urlsafe(9).replace('-', 'x').replace('_', 'y'), now_iso()
            self.db.execute('INSERT INTO story_orders VALUES(?,?,?,?,?,?,?)', (oid, order['idempotency_key'], json.dumps(order), 'queued', None, at, at))
        return {**order, 'order_id': oid, 'status': 'queued', 'created_at': at}, True

    def orders(self, statuses=None):
        q, args = 'SELECT payload,order_id,status,created_at,reason FROM story_orders', ()
        if statuses: q += ' WHERE status IN (%s)' % ','.join('?' * len(statuses)); args = tuple(statuses)
        with self.lock: return [self._order(r) for r in self.db.execute(q + ' ORDER BY created_at DESC LIMIT 200', args)]

    def order(self, oid):
        with self.lock:
            r = self.db.execute('SELECT payload,order_id,status,created_at,reason FROM story_orders WHERE order_id=?', (oid,)).fetchone()
            if not r: raise StoryError(404, 'not_found', 'Không có lệnh này')
            ch = self.db.execute('SELECT chapter_no,state,round,score,version,words,message,link,at FROM story_chapters WHERE order_id=? ORDER BY chapter_no', (oid,)).fetchall()
        keys = ('chapter_no', 'state', 'round', 'score', 'version', 'words', 'message', 'link', 'updated_at')
        return self._order(r), [dict(zip(keys, c)) for c in ch]

    def ack(self, oid, data):
        result = data.get('result')
        if result not in ('accepted', 'rejected') or data.get('order_id') != oid: raise StoryError(400, 'invalid_ack', 'Phản hồi lệnh không hợp lệ')
        with self.lock:
            row = self.db.execute('SELECT status FROM story_orders WHERE order_id=?', (oid,)).fetchone()
            if not row: raise StoryError(404, 'not_found', 'Không có lệnh này')
            if row[0] == 'queued':
                self.db.execute('UPDATE story_orders SET status=?,reason=?,updated_at=? WHERE order_id=?', (result, str(data.get('reason') or '')[:40] or None, now_iso(), oid))
            for c in data.get('chapters') or []:
                if isinstance(c, dict) and isinstance(c.get('chapter_no'), int) and c.get('state') in CHAPTER_STATES:
                    # Placeholder row: dated at the epoch so any real progress event replaces it.
                    self.db.execute('INSERT OR IGNORE INTO story_chapters(order_id,chapter_no,state,at) VALUES(?,?,?,?)', (oid, c['chapter_no'], c['state'], '1970-01-01T00:00:00.000Z'))
        return {}

    def control(self, oid, action):
        if action not in ('pause', 'resume', 'cancel'): raise StoryError(400, 'invalid_control', 'Lệnh điều khiển không hợp lệ')
        with self.lock:
            row = self.db.execute('SELECT status FROM story_orders WHERE order_id=?', (oid,)).fetchone()
            if not row: raise StoryError(404, 'not_found', 'Không có lệnh này')
            if action == 'cancel' and row[0] in ('queued', 'accepted', 'running'):
                self.db.execute("UPDATE story_orders SET status='cancelled',updated_at=? WHERE order_id=?", (now_iso(), oid))
            cur = self.db.execute('INSERT INTO story_controls(order_id,action,at) VALUES(?,?,?)', (oid, action, now_iso()))
        return {'seq': cur.lastrowid}

    def controls(self, since):
        with self.lock: rows = self.db.execute('SELECT seq,order_id,action,at FROM story_controls WHERE seq>? ORDER BY seq LIMIT 100', (since,)).fetchall()
        return [{'schema': SCHEMA, 'seq': s, 'order_id': o, 'action': a, 'at': t} for s, o, a, t in rows]

    def events(self, events):
        if not isinstance(events, list) or len(events) > 100: raise StoryError(400, 'invalid_events', 'Tối đa 100 sự kiện mỗi lần')
        accepted = dup = 0
        with self.lock:
            for e in events:
                if not (isinstance(e, dict) and isinstance(e.get('event_id'), str) and ID.match(e['event_id']) and isinstance(e.get('order_id'), str)
                        and isinstance(e.get('chapter_no'), int) and e.get('state') in CHAPTER_STATES and isinstance(e.get('job_key'), str) and JOB_KEY.match(e['job_key'])
                        and e['job_key'] == f"{e['order_id']}:{e['chapter_no']}"):
                    raise StoryError(400, 'invalid_event', 'Sự kiện không hợp lệ')
                if not self.db.execute('SELECT 1 FROM story_orders WHERE order_id=?', (e['order_id'],)).fetchone(): raise StoryError(404, 'not_found', 'Sự kiện cho lệnh không tồn tại')
                if self.db.execute('INSERT OR IGNORE INTO story_events VALUES(?,?,?,?)', (e['event_id'], e['order_id'], json.dumps(e), now_iso())).rowcount == 0:
                    dup += 1; continue
                accepted += 1; at = norm_time(e.get('at'))
                old = self.db.execute('SELECT at FROM story_chapters WHERE order_id=? AND chapter_no=?', (e['order_id'], e['chapter_no'])).fetchone()
                if old and old[0] > at: continue  # an older event arrived late; keep the newer state
                self.db.execute('INSERT OR REPLACE INTO story_chapters VALUES(?,?,?,?,?,?,?,?,?,?)', (e['order_id'], e['chapter_no'], e['state'], e.get('round'), e.get('score'),
                                e.get('version'), e.get('words'), str(e.get('message') or '')[:500], e.get('link') if str(e.get('link') or '').startswith('https://') else None, at))
            for oid in {e['order_id'] for e in events}: self._settle(oid)
        return {'accepted': accepted, 'duplicates': dup}

    def _settle(self, oid):
        status, payload = self.db.execute('SELECT status,payload FROM story_orders WHERE order_id=?', (oid,)).fetchone()
        if status in ('cancelled', 'rejected'): return
        count = json.loads(payload)['chapter_count']
        states = [s for (s,) in self.db.execute('SELECT state FROM story_chapters WHERE order_id=?', (oid,))]
        new = 'running'
        if len(states) >= count and all(s in FINISHED | BROKEN for s in states): new = 'partially_done' if any(s in BROKEN for s in states) else 'done'
        if new != status: self.db.execute('UPDATE story_orders SET status=?,updated_at=? WHERE order_id=?', (new, now_iso(), oid))


def handle(store, method, path, query, headers, body, version):
    """Routes /api/story/*. Returns (status, payload). Page calls must come from the Manager page; Adapter calls need the token."""
    def page():
        origin = headers.get('Origin', '')
        if origin and origin not in PAGE_ORIGINS: raise StoryError(403, 'forbidden', 'Nguồn truy cập không hợp lệ')
        if not origin and (method != 'GET' or headers.get('Sec-Fetch-Site') == 'cross-site'): raise StoryError(403, 'forbidden', 'Nguồn truy cập không hợp lệ')
    try:
        if body is not None and len(body) > MAX_BODY: raise StoryError(413, 'too_large', 'Dữ liệu quá lớn')
        data = json.loads(body or b'{}') if method == 'POST' else {}
        parts = path.strip('/').split('/')[2:]  # after api/story
        if method == 'GET' and parts == ['state']: page(); return 200, {'ok': True, 'pairing': store.pairing(), 'orders': store.orders()}
        if method == 'POST' and parts == ['pairing-code']: page(); return 200, {'ok': True, **store.new_code()}
        if method == 'POST' and parts == ['revoke']: page(); store.revoke(); return 200, {'ok': True}
        if method == 'POST' and parts == ['pair']: return 200, {'ok': True, **store.pair(data.get('code', ''), headers.get('Origin', ''), data.get('extension_version', ''))}
        if method == 'POST' and parts == ['orders']: page(); o, created = store.create_order(data); return (201 if created else 200), {'ok': True, 'order': o, 'created': created}
        if method == 'GET' and len(parts) == 2 and parts[0] == 'orders' and parts[1] != '': page(); o, ch = store.order(parts[1]); return 200, {'ok': True, 'order': o, 'chapters': ch}
        if method == 'POST' and len(parts) == 3 and parts[0] == 'orders' and parts[2] == 'control': page(); return 200, {'ok': True, **store.control(parts[1], data.get('action'))}
        # Adapter calls
        store.check_adapter(headers)
        if method == 'GET' and parts == ['health']: return 200, {'ok': True, 'manager_version': version, 'server_time': now_iso()}
        if method == 'GET' and parts == ['orders']:
            st = [s for s in (parse_qs(query).get('status', ['queued'])[0]).split(',') if s][:6]
            return 200, {'ok': True, 'orders': store.orders(st)}
        if method == 'POST' and len(parts) == 3 and parts[0] == 'orders' and parts[2] == 'ack': return 200, {'ok': True, **store.ack(parts[1], data)}
        if method == 'GET' and parts == ['controls']:
            since = parse_qs(query).get('since', ['0'])[0]
            items = store.controls(int(since) if since.isdigit() else 0)
            return 200, {'ok': True, 'controls': items, 'next': items[-1]['seq'] if items else int(since or 0) if since.isdigit() else 0}
        if method == 'POST' and parts == ['events']: return 200, {'ok': True, **store.events(data.get('events'))}
        raise StoryError(404, 'not_found', 'Không tìm thấy')
    except StoryError as e:
        return e.status, {'ok': False, 'error': e.code, 'message': e.message}
    except (ValueError, json.JSONDecodeError):
        return 400, {'ok': False, 'error': 'bad_request', 'message': 'Dữ liệu không hợp lệ'}
