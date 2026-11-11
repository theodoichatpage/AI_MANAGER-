"""Protocol and action validation for WinControl's existing ChatGPT MCP loop."""
import json
import re
import tempfile
from pathlib import Path


WINCONTROL_ACTIONS = {
    'LIST_WINDOWS', 'LIST_PROCESSES', 'CHECK_PROCESS', 'OPEN_APP', 'WAIT_WINDOW',
    'FOCUS_WINDOW', 'RESTORE', 'MAXIMIZE', 'MINIMIZE', 'SCREENSHOT', 'FIND_ELEMENT',
    'READ_ELEMENT', 'CLICK', 'TYPE_TEXT', 'HOTKEY', 'WAIT', 'WAIT_ELEMENT',
    'ENSURE_TEMP_DIR', 'VERIFY_FILE', 'OPEN_FILE', 'SAVE_AS', 'MAN_STATUS',
}
TARGET_APPS = {'notepad', 'chrome', 'edge', 'capcut'}
BROWSER_APPS = {'chrome', 'edge'}
INPUT_ACTIONS = {'CLICK', 'TYPE_TEXT', 'HOTKEY', 'OPEN_FILE', 'SAVE_AS'}
MAX_ROUNDS = 12
MAX_CORRECTIONS = 2
RESULT_CHARS = 1500
PROMPT_CHARS = 11000
FIELDS = {
    'LIST_WINDOWS': {'action', 'target_app', 'title', 'timeout'},
    'LIST_PROCESSES': {'action', 'timeout'},
    'CHECK_PROCESS': {'action', 'target_app', 'timeout'},
    'OPEN_APP': {'action', 'target_app', 'timeout'},
    'WAIT_WINDOW': {'action', 'target_app', 'title', 'timeout'},
    'FOCUS_WINDOW': {'action', 'target_app', 'timeout'},
    'RESTORE': {'action', 'target_app', 'timeout'},
    'MAXIMIZE': {'action', 'target_app', 'timeout'},
    'MINIMIZE': {'action', 'target_app', 'timeout'},
    'SCREENSHOT': {'action', 'target_app', 'timeout'},
    'FIND_ELEMENT': {'action', 'target_app', 'selector', 'timeout'},
    'READ_ELEMENT': {'action', 'target_app', 'selector', 'timeout'},
    'CLICK': {'action', 'target_app', 'selector', 'timeout'},
    'TYPE_TEXT': {'action', 'target_app', 'selector', 'text', 'timeout'},
    'HOTKEY': {'action', 'target_app', 'keys', 'timeout'},
    'WAIT': {'action', 'seconds', 'timeout'},
    'WAIT_ELEMENT': {'action', 'target_app', 'selector', 'timeout'},
    'ENSURE_TEMP_DIR': {'action', 'timeout'},
    'VERIFY_FILE': {'action', 'path', 'expected_text', 'timeout'},
    'OPEN_FILE': {'action', 'target_app', 'path', 'timeout'},
    'SAVE_AS': {'action', 'target_app', 'path', 'timeout'},
    'MAN_STATUS': {'action', 'timeout'},
}
SELECTOR_FIELDS = {'title', 'title_re', 'auto_id', 'control_type', 'class_name', 'control_id'}
HOTKEYS = {'CTRL+A', 'CTRL+C', 'CTRL+V', 'CTRL+S', 'CTRL+O', 'CTRL+L', 'CTRL+T', 'CTRL+W', 'CTRL+TAB', 'CTRL+SHIFT+TAB', 'ENTER', 'ESCAPE', 'F5'}


def _safe_temp_path(value):
    base = (Path(tempfile.gettempdir()) / 'WinControl').resolve()
    path = Path(str(value or '')).expanduser().resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError('FILE_PATH_OUTSIDE_WINCONTROL_TEMP') from exc
    if path == base:
        raise ValueError('FILE_PATH_REQUIRED')
    return str(path)


def validate_actions(actions):
    if not isinstance(actions, list) or len(actions) != 1:
        raise ValueError('WINCONTROL_CONTINUE_REQUIRES_ONE_ACTION')
    clean = []
    for raw in actions:
        if not isinstance(raw, dict) or raw.get('action') not in WINCONTROL_ACTIONS:
            raise ValueError('WINCONTROL_ACTION_NOT_ALLOWED')
        name = raw['action']
        raw = {k: v for k, v in raw.items() if k != 'retries'}  # set to 0 below; an already checked action keeps it
        if set(raw) - FIELDS[name]:
            raise ValueError('WINCONTROL_ACTION_FIELDS_NOT_ALLOWED')
        action = dict(raw)
        app = action.get('target_app')
        if app is not None and app not in TARGET_APPS:
            raise ValueError('WINCONTROL_TARGET_NOT_ALLOWED')
        # Without an explicit app the worker falls back to the task's own app (the ChatGPT Chrome window).
        if app is None and 'target_app' in FIELDS[name] and name not in {'LIST_WINDOWS'}:
            raise ValueError('WINCONTROL_TARGET_APP_REQUIRED')
        # Chrome/Edge hold the ChatGPT brain tab and Studio production tabs: no keyboard or mouse input there.
        if app in BROWSER_APPS and name in INPUT_ACTIONS:
            raise ValueError('WINCONTROL_BROWSER_INPUT_NOT_ALLOWED')
        if name in {'FIND_ELEMENT', 'READ_ELEMENT', 'CLICK', 'TYPE_TEXT', 'WAIT_ELEMENT'}:
            selector = action.get('selector')
            if not isinstance(selector, dict) or not selector or set(selector) - SELECTOR_FIELDS:
                raise ValueError('WINCONTROL_SELECTOR_INVALID')
        if name == 'TYPE_TEXT' and (not isinstance(action.get('text'), str) or len(action['text']) > 8000):
            raise ValueError('WINCONTROL_TEXT_INVALID')
        if name == 'HOTKEY' and action.get('keys') not in HOTKEYS:
            raise ValueError('WINCONTROL_HOTKEY_INVALID')
        if name in {'VERIFY_FILE', 'OPEN_FILE', 'SAVE_AS'}:
            action['path'] = _safe_temp_path(action.get('path'))
        if name == 'VERIFY_FILE' and (not isinstance(action.get('expected_text'), str) or len(action['expected_text']) > 8000):
            raise ValueError('WINCONTROL_FILE_EXPECTATION_INVALID')
        timeout = float(action.get('timeout', 30))
        if not 0.1 <= timeout <= 300:
            raise ValueError('WINCONTROL_TIMEOUT_INVALID')
        action['timeout'] = timeout
        action['retries'] = 0
        clean.append(action)
    return clean


def _json_objects(value):
    """Yield every balanced top-level {...} block, so ChatGPT page text around the JSON is ignored."""
    depth = 0
    start = None
    quoted = False
    escaped = False
    for i, ch in enumerate(value):
        if quoted:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"' and depth:
            quoted = True
        elif ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}' and depth:
            depth -= 1
            if depth == 0:
                yield value[start:i + 1]


def _load_decision(text):
    value = str(text or '').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', value, re.I | re.S)
    if fenced:
        value = fenced.group(1)
    # The accessibility snapshot splits a reply into lines; a code block also adds "json" / "Copy code".
    for candidate in (value, value.replace('\n', ' '), value.replace('\n', '')):
        for block in reversed(list(_json_objects(candidate))):
            try:
                decision = json.loads(block, strict=False)
            except ValueError:
                continue
            if isinstance(decision, dict) and 'status' in decision:
                return decision
    raise ValueError('WINCONTROL_CHATGPT_JSON_INVALID')


def parse_decision(text):
    decision = _load_decision(text)
    if set(decision) - {'status', 'summary', 'actions'}:
        raise ValueError('WINCONTROL_CHATGPT_DECISION_INVALID')
    status = decision.get('status')
    summary = str(decision.get('summary') or '').strip()[:1000]
    actions = decision.get('actions')
    if status == 'continue':
        return {'status': status, 'summary': summary, 'actions': validate_actions(actions)}
    if status in {'complete', 'blocked'} and actions in ([], None):
        return {'status': status, 'summary': summary, 'actions': []}
    raise ValueError('WINCONTROL_CHATGPT_STATUS_INVALID')


def _short(value, limit=RESULT_CHARS):
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return text if len(text) <= limit else text[:limit] + '…(rút gọn)'


CONTRACT = ('Reply with ONE JSON object only, as plain text (no code block, no other words): '
            '{"status":"continue|complete|blocked","summary":"<short Vietnamese summary for the user>","actions":[...]}. '
            'status=continue requires exactly one next action in actions; complete or blocked requires actions=[]. '
            'Choose one step, then wait for its observed result before deciding again. Use only available_actions with their fields. '
            'Never request Studio production, Extension changes, SEND_CHATGPT, or files outside temp_dir. '
            'Never claim success before an observed result proves it. MAN_STATUS reads MAN, Agent, Studio and Extension health read-only. '
            'Every window action must name target_app; never CLICK, TYPE_TEXT, HOTKEY or OPEN_FILE in chrome or edge (they hold this ChatGPT tab and Studio). '
            'For a Notepad text task: ENSURE_TEMP_DIR, OPEN_APP notepad (always opens a new window and focuses it), TYPE_TEXT with selector {"class_name":"Edit"}, SAVE_AS target_app notepad with a new full path under temp_dir (it refuses existing files), '
            'then VERIFY_FILE before complete. If a step fails, choose one corrective step or report blocked with the reason.')


def _fit(prefix, envelope):
    # One line only: the Chrome MCP bridge reads the composer value back line by line and refuses to send a
    # multi-line value it cannot verify (COMPOSER_VALUE_UNVERIFIED_NO_SEND). json.dumps already escapes inner newlines.
    text = ' '.join((prefix + json.dumps(envelope, ensure_ascii=False, default=str)).splitlines())
    if len(text) > PROMPT_CHARS:
        text = text[:PROMPT_CHARS - 20] + '…(rút gọn)"}'
    return text


def initial_prompt(command, context):
    envelope = {
        'user_command': command,
        'live_state': context,
        'available_actions': {name: sorted(FIELDS[name] - {'action'}) for name in sorted(WINCONTROL_ACTIONS)},
        'contract': CONTRACT,
    }
    return _fit('WinControl task. JSON only under this contract:\n', envelope)


def feedback_prompt(command, summary, results):
    rows = [{'action': r.get('action'), 'success': r.get('success'), 'error': r.get('error'), 'result': _short(r.get('result'))} for r in results]
    envelope = {'user_command': command, 'last_decision': summary, 'observed_action_results': rows,
                'contract': 'Decide the next single step from these observed results only. Same JSON contract: ' + CONTRACT}
    return _fit('WinControl tool result; continue autonomously:\n', envelope)


def correction_prompt(command, error, reply):
    envelope = {'user_command': command, 'problem': str(error), 'your_last_reply': str(reply or '')[:600],
                'contract': 'Your last reply could not be used. Answer again with the corrected JSON only. ' + CONTRACT}
    return _fit('WinControl format correction:\n', envelope)


def man_health(state):
    """Read-only health summary of MAN, Agent, Studio and Extension from MAN's own /api/state."""
    agent = state.get('automation') or {}
    tasks = agent.get('tasks') or []
    problems = [{'id': t.get('id'), 'status': t.get('status'), 'stage': t.get('current_stage'), 'action': t.get('current_action'),
                 'error': str(t.get('error') or '')[:200]}
                for t in tasks if t.get('status') in ('failed', 'needs_review', 'timeout')][-6:]
    studio = state.get('studio') or {}
    extension = state.get('extension') or {}
    update = state.get('extension_update') or {}
    queue = state.get('queue') or []
    issues = []
    if not agent.get('online'):
        issues.append('AGENT_OFFLINE')
    if studio.get('status') in ('lost', 'error'):
        issues.append('STUDIO_' + str(studio.get('status')).upper())
    if extension.get('status') not in (None, 'responding'):
        issues.append('EXTENSION_' + str(extension.get('status')).upper())
    if update.get('installed') and update.get('latest') and update['installed'] != update['latest']:
        issues.append('EXTENSION_UPDATE_AVAILABLE')
    if problems:
        issues.append('TASKS_NEED_REVIEW')
    return {
        'version': state.get('version'),
        'agent': {k: agent.get(k) for k in ('online', 'enabled', 'pid', 'current_task', 'error')},
        'queue': [{'name': q.get('name'), 'status': q.get('status'), 'stage': q.get('current_stage')} for q in queue][:10],
        'studio': {'status': studio.get('status'), 'error': studio.get('error'), 'presence': studio.get('presence')},
        'extension': {k: extension.get(k) for k in ('status', 'heartbeatAge', 'activeJobId', 'version')},
        'extension_update': {k: update.get(k) for k in ('installed', 'latest', 'error')},
        'tasks_needing_review': problems,
        'issues': issues,
    }
