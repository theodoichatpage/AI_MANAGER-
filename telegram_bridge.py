"""Telegram for WinControl: the user's own bot forwards commands to WinControl and reports what happens.

Reuses the design of the earlier Codex gateway (Documents/AI_MAN_TELEGRAM_TEST/telegram_gateway.py): only one
paired Telegram user in one private chat is obeyed, each update is claimed before it is handled (never twice),
and MAN is reached only through its own local API, exactly like the WinControl page:
GET /api/state to read, POST /api/automation {command:'wincontrol'} to give a command.

The bot token is saved encrypted with Windows DPAPI (like the Studio pairing) and never shown again.
Only one program may read a bot's updates at a time: the old gateway must not run with the same bot."""
import json, random, re, threading, time, urllib.error, urllib.request
from pathlib import Path

TOKEN = re.compile(r'[0-9]{5,20}:[A-Za-z0-9_-]{30,100}')
PAIR_TTL = 900          # a pairing code works for 15 minutes
POLL_WAIT = 20          # Telegram long poll
MAN = 'http://127.0.0.1:8765'
ORIGIN = 'http://127.0.0.1:8765'
TERMINAL = ('completed', 'needs_review', 'failed', 'stopped')
HELP = ('WinControl qua Telegram.\n'
        'Gõ nhiệm vụ bằng tiếng Việt, ví dụ: "Kiểm tra tiến độ dự án Thái sư Trần Thủ Độ".\n'
        '/status – tình trạng MAN, Studio, Extension, dự án\n'
        '/stop – dừng an toàn nhiệm vụ WinControl đang chạy\n'
        '/help – hướng dẫn')


def _protect(raw):
    from studio_monitor import _protect as p
    return p(raw)


def _unprotect(blob):
    from studio_monitor import _unprotect as u
    return u(blob)


def _http(url, body=None, timeout=10, origin=False):
    data = None if body is None else json.dumps(body).encode()
    headers = {'Content-Type': 'application/json'}
    if origin:
        headers['Origin'] = ORIGIN
    req = urllib.request.Request(url, data, headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read() or b'{}')
            reason = body.get('error') or body.get('description')
        except ValueError:
            reason = None
        raise RuntimeError(str(reason or exc.reason)) from exc


def status_text(s):
    """Short Vietnamese status from MAN's /api/state."""
    a = s.get('automation') or {}
    st = s.get('studio') or {}
    e = s.get('extension') or {}
    lines = ['MAN %s · Agent %s%s' % (s.get('version'), 'online' if a.get('online') else 'OFFLINE',
                                         '' if a.get('enabled') else ' (đang tắt)'),
             'Studio: %s · Extension %s %s' % (st.get('status'), e.get('version') or '', e.get('status'))]
    for q in s.get('queue') or []:
        if q.get('status') in ('running', 'paused', 'waiting', 'failed'):
            lines.append('• %s: %s · %s' % (q.get('name'), q.get('status'), q.get('current_stage') or ''))
    for t in a.get('tasks') or []:
        c = t.get('context') or {}
        if t.get('status') == 'running' and c.get('studio_lanes'):
            lanes = ', '.join('%s%s' % (l.get('label') or l.get('lane'), ' (nghỉ)' if l.get('cooldown') else '')
                              for l in c['studio_lanes'])
            lines.append('Ảnh: %s · tab: %s' % (c.get('studio_images_generated'), lanes))
            if c.get('studio_message'):
                lines.append(str(c['studio_message']))
    return '\n'.join(lines)


def wincontrol_summary(task):
    for row in reversed(task.get('results') or []):
        d = (row.get('result') or {}).get('decision') or {}
        if d.get('summary'):
            return str(d['summary'])[:1200]
    return str(task.get('error') or '')[:600]


class TelegramBridge:
    def __init__(self, home, api=_http, man=MAN, clock=time.time, rng=None):
        self.home = Path(home)
        self.token_path = self.home / 'telegram_token.bin'
        self.state_path = self.home / 'telegram.json'
        self.api = api
        self.man = man
        self.clock = clock
        self.rng = rng or random.SystemRandom()
        self.lock = threading.Lock()
        self.token = ''
        self.error = ''
        self.last_poll = None
        self.s = {'user_id': None, 'chat_id': None, 'offset': 0, 'pair_code': None, 'pair_until': 0,
                  'seen': {}, 'primed': False}
        self._load()

    # ---- storage
    def _load(self):
        try:
            self.s.update(json.loads(self.state_path.read_text(encoding='utf8')))
        except (OSError, ValueError):
            pass
        try:
            self.token = (_unprotect(self.token_path.read_bytes()) or b'').decode('ascii')
        except Exception:
            self.token = ''

    def _save(self):
        self.home.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.s, ensure_ascii=False), encoding='utf8')
        tmp.replace(self.state_path)

    # ---- setup (from the WinControl page; the user pastes the token there)
    def configure(self, token):
        token = str(token or '').strip()
        if not TOKEN.fullmatch(token):
            raise ValueError('Token bot không hợp lệ (dạng 123456789:ABC…, lấy từ @BotFather)')
        blob = _protect(token.encode('ascii'))
        if blob is None:
            raise ValueError('Chỉ lưu được token trên Windows')
        self.home.mkdir(parents=True, exist_ok=True)
        self.token_path.write_bytes(blob)
        with self.lock:
            self.token = token
            self.error = ''
            self.s.update(user_id=None, chat_id=None)
            self._new_code()
            self._save()
        return self.snapshot()

    def new_pair_code(self):
        with self.lock:
            self._new_code()
            self._save()
        return self.snapshot()

    def _new_code(self):
        self.s['pair_code'] = '%06d' % self.rng.randrange(1000000)
        self.s['pair_until'] = self.clock() + PAIR_TTL

    def unpair(self):
        with self.lock:
            self.s.update(user_id=None, chat_id=None, pair_code=None, pair_until=0)
            self._save()
        return self.snapshot()

    def forget(self):
        try:
            self.token_path.unlink()
        except FileNotFoundError:
            pass
        with self.lock:
            self.token = ''
            self.s.update(user_id=None, chat_id=None, pair_code=None, pair_until=0)
            self._save()
        return self.snapshot()

    def snapshot(self):
        paired = bool(self.s.get('chat_id'))
        code = self.s.get('pair_code') if self.token and not paired and self.clock() < float(self.s.get('pair_until') or 0) else None
        return {'configured': bool(self.token), 'paired': paired, 'pair_code': code,
                'error': self.error or None, 'last_poll': self.last_poll}

    # ---- Telegram
    def _tg(self, method, payload, timeout=10):
        return self.api('https://api.telegram.org/bot' + self.token + '/' + method, payload, timeout=timeout)

    def send(self, text):
        if self.token and self.s.get('chat_id'):
            self._tg('sendMessage', {'chat_id': self.s['chat_id'], 'text': str(text)[:3900]})

    def poll_once(self):
        data = self._tg('getUpdates', {'offset': int(self.s.get('offset') or 0), 'timeout': POLL_WAIT,
                                       'allowed_updates': ['message']}, timeout=POLL_WAIT + 10)
        self.last_poll = self.clock()
        for update in data.get('result') or []:
            uid = update.get('update_id')
            if type(uid) is not int:
                continue
            # Claim first: an update is never handled twice, even if MAN stops in the middle.
            with self.lock:
                if uid < int(self.s.get('offset') or 0):
                    continue
                self.s['offset'] = uid + 1
                self._save()
            try:
                self.handle(update)
            except Exception as exc:  # one bad message must not stop the bridge
                self.error = str(exc)[:200]

    def handle(self, update):
        msg = update.get('message') or {}
        text = str(msg.get('text') or '').strip()
        sender = (msg.get('from') or {}).get('id')
        chat = msg.get('chat') or {}
        if not text or type(sender) is not int or chat.get('type') != 'private' or chat.get('id') != sender:
            return
        if not self.s.get('chat_id'):
            m = re.fullmatch(r'/pair\s+(\d{6})', text)
            if m and m.group(1) == self.s.get('pair_code') and self.clock() < float(self.s.get('pair_until') or 0):
                with self.lock:
                    self.s.update(user_id=sender, chat_id=sender, pair_code=None, pair_until=0)
                    self._save()
                self.send('Đã ghép nối với AI MANAGER trên máy tính.\n' + HELP)
            return  # strangers and wrong codes get no answer
        if sender != self.s.get('user_id') or chat.get('id') != self.s.get('chat_id'):
            return
        cmd = text.split()[0].split('@')[0].lower()
        if cmd in ('/start', '/help'):
            self.send(HELP)
        elif cmd == '/status':
            self.send(status_text(self.api(self.man + '/api/state', None, timeout=10)))
        elif cmd == '/stop':
            state = self.api(self.man + '/api/state', None, timeout=10)
            running = [t for t in (state.get('automation') or {}).get('tasks') or []
                       if (t.get('context') or {}).get('wincontrol_task') and t.get('status') in ('running', 'waiting')]
            if not running:
                self.send('Không có nhiệm vụ WinControl đang chạy.')
            for t in running:
                self.api(self.man + '/api/automation', {'command': 'wincontrol_cancel', 'task_id': t['id']}, timeout=10, origin=True)
                self.send('Đã yêu cầu dừng an toàn nhiệm vụ: ' + str((t.get('context') or {}).get('wincontrol_command') or t['id'])[:200])
        else:
            try:
                r = self.api(self.man + '/api/automation', {'command': 'wincontrol', 'text': text[:4000],
                                                            'request_id': 'tg-' + str(update.get('update_id'))},
                             timeout=15, origin=True)
                self.send(('Đã nhận (đã giao trước đó). ' if r.get('duplicate') else 'Đã giao cho WinControl. ')
                          + str(r.get('summary') or '') + '\nTôi sẽ báo khi xong.')
            except RuntimeError as exc:
                self.send('Chưa thực hiện: ' + str(exc)[:400])

    # ---- reports
    def events(self, state):
        """What changed since the last look: finished WinControl tasks, project status, limit notices, lost links.
        The first look only records the present, so a restart does not repeat old news."""
        seen = self.s.setdefault('seen', {})
        out = []
        tasks = (state.get('automation') or {}).get('tasks') or []
        for t in tasks:
            c = t.get('context') or {}
            if c.get('wincontrol_task') and t.get('status') in TERMINAL:
                key = 'wc:' + str(t.get('id'))
                if seen.get(key) != t['status']:
                    seen[key] = t['status']
                    word = {'completed': 'Xong', 'needs_review': 'Dừng an toàn, cần xem',
                            'failed': 'Lỗi', 'stopped': 'Đã dừng'}[t['status']]
                    out.append('WinControl · %s: %s\n%s' % (word, str(c.get('wincontrol_command') or '')[:200], wincontrol_summary(t)))
            if not c.get('wincontrol_task') and c.get('studio_attention'):
                key = 'att:' + str(t.get('id'))
                note = ' | '.join(map(str, c['studio_attention']))[:600]
                if seen.get(key) != note:
                    seen[key] = note
                    out.append('Studio: ' + note)
        for q in state.get('queue') or []:
            key = 'p:' + str(q.get('id'))
            if seen.get(key) != q.get('status'):
                if key in seen:
                    out.append('Dự án %s: %s → %s (%s)' % (q.get('name'), seen[key], q.get('status'), q.get('current_stage') or ''))
                seen[key] = q.get('status')
        for name, value in (('studio', (state.get('studio') or {}).get('status')),
                            ('extension', (state.get('extension') or {}).get('status'))):
            key = 'link:' + name
            bad = value in ('lost', 'error', 'extension_lost')
            if seen.get(key) != bad:
                if key in seen:
                    out.append(('%s mất kết nối (%s).' if bad else '%s đã kết nối lại.') % (name.capitalize(), value))
                seen[key] = bad
        if len(seen) > 400:  # keep the file small: forget the oldest finished tasks
            for k in [k for k in seen if k.startswith('wc:')][:len(seen) - 400]:
                seen.pop(k, None)
        if not self.s.get('primed'):
            self.s['primed'] = True
            out = []
        self._save()
        return out

    def report_once(self):
        if not (self.token and self.s.get('chat_id')):
            return
        for text in self.events(self.api(self.man + '/api/state', None, timeout=10)):
            self.send(text)

    def run(self, stop):
        while not stop.is_set():
            if not self.token:
                stop.wait(5)
                continue
            try:
                self.poll_once()
                self.report_once()
                self.error = ''
            except Exception as exc:
                self.error = str(exc)[:200]
                stop.wait(10)
