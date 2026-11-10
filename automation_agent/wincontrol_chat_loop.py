"""Protocol and action validation for WinControl's existing ChatGPT MCP loop."""
import json
import re
import tempfile
from pathlib import Path


WINCONTROL_ACTIONS = {
    'LIST_WINDOWS', 'LIST_PROCESSES', 'CHECK_PROCESS', 'OPEN_APP', 'WAIT_WINDOW',
    'FOCUS_WINDOW', 'RESTORE', 'MAXIMIZE', 'MINIMIZE', 'SCREENSHOT', 'FIND_ELEMENT',
    'READ_ELEMENT', 'CLICK', 'TYPE_TEXT', 'HOTKEY', 'WAIT', 'WAIT_ELEMENT',
    'ENSURE_TEMP_DIR', 'VERIFY_FILE', 'OPEN_FILE',
}
TARGET_APPS = {'notepad', 'chrome', 'edge', 'capcut'}
MAX_ROUNDS = 12
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
        if set(raw) - FIELDS[name]:
            raise ValueError('WINCONTROL_ACTION_FIELDS_NOT_ALLOWED')
        action = dict(raw)
        app = action.get('target_app')
        if app is not None and app not in TARGET_APPS:
            raise ValueError('WINCONTROL_TARGET_NOT_ALLOWED')
        if name in {'FIND_ELEMENT', 'READ_ELEMENT', 'CLICK', 'TYPE_TEXT', 'WAIT_ELEMENT'}:
            selector = action.get('selector')
            if not isinstance(selector, dict) or not selector or set(selector) - SELECTOR_FIELDS:
                raise ValueError('WINCONTROL_SELECTOR_INVALID')
        if name == 'TYPE_TEXT' and (not isinstance(action.get('text'), str) or len(action['text']) > 8000):
            raise ValueError('WINCONTROL_TEXT_INVALID')
        if name == 'HOTKEY' and action.get('keys') not in HOTKEYS:
            raise ValueError('WINCONTROL_HOTKEY_INVALID')
        if name in {'VERIFY_FILE', 'OPEN_FILE'}:
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


def parse_decision(text):
    value = str(text or '').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', value, re.I | re.S)
    if fenced:
        value = fenced.group(1)
    try:
        decision = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('WINCONTROL_CHATGPT_JSON_INVALID') from exc
    if not isinstance(decision, dict) or set(decision) - {'status', 'summary', 'actions'}:
        raise ValueError('WINCONTROL_CHATGPT_DECISION_INVALID')
    status = decision.get('status')
    summary = str(decision.get('summary') or '').strip()[:1000]
    actions = decision.get('actions')
    if status == 'continue':
        return {'status': status, 'summary': summary, 'actions': validate_actions(actions)}
    if status in {'complete', 'blocked'} and actions == []:
        return {'status': status, 'summary': summary, 'actions': []}
    raise ValueError('WINCONTROL_CHATGPT_STATUS_INVALID')


def initial_prompt(command, context):
    envelope = {
        'user_command': command,
        'live_state': context,
        'available_actions': sorted(WINCONTROL_ACTIONS),
        'contract': 'Return exactly one JSON object with keys status, summary, actions. status=continue requires exactly one safe next action in actions. status=complete or blocked requires actions=[]. Choose only one next step, wait for its result before deciding again. Do not issue Studio, Extension, SEND_CHATGPT, filesystem actions outside the WinControl temp directory, or claim an action succeeded before result verification. For Notepad, observe after every important UI action; save under temp_dir, reopen, read back, then report complete only after VERIFY_FILE succeeds.',
    }
    return 'WinControl task. Respond with JSON only under this contract:\n' + json.dumps(envelope, ensure_ascii=False)


def feedback_prompt(command, summary, results):
    envelope = {'user_command': command, 'last_decision': summary, 'observed_action_results': results,
                'contract': 'Decide the next single safe tool action based only on observed results. Return the same JSON schema. If all requested work is verified, return status=complete and actions=[]. If recoverable, choose one corrective action. Never resend a prior uncertain SEND_CHATGPT or perform Studio production.'}
    return 'WinControl tool result; continue autonomously:\n' + json.dumps(envelope, ensure_ascii=False)
