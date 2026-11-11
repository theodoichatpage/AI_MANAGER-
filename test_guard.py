"""Keeps test runs away from the real Manager data.

A full `python -m unittest discover` once opened the real queue database and paused a running production
project (2026-11-11 01:30Z). Under a test run this module gives the process a private temporary home and
refuses to open the real home or the real projects root. Normal Manager/Agent runs are not affected.
"""
import json
import os
import sys
import tempfile
from pathlib import Path


def under_test():
    if os.environ.get('AI_MANAGER_TESTING') == '1':
        return True
    main = sys.modules.get('__main__')
    spec = getattr(main, '__spec__', None)
    if (getattr(spec, 'name', '') or '').split('.')[0] in ('unittest', 'pytest'):
        return True
    path = Path(getattr(main, '__file__', '') or '')
    return path.name.startswith('test_') and path.parent.name == 'tests'


def production_paths():
    home = Path.home()
    base = home / '.ai_manager'
    paths = {base, home / 'VIDEO_PROJECTS'}
    try:
        paths.add(Path(json.loads((base / 'config.json').read_text(encoding='utf-8'))['root']))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {p.resolve() for p in paths}


def isolate():
    """Under test without AI_MANAGER_HOME: use a private temporary home (child processes inherit it)."""
    if under_test():
        os.environ['AI_MANAGER_TESTING'] = '1'
        if not os.environ.get('AI_MANAGER_HOME'):
            os.environ['AI_MANAGER_HOME'] = tempfile.mkdtemp(prefix='ai_manager_test_')


def refuse_production(path, what):
    if under_test() and Path(path).resolve() in production_paths():
        raise RuntimeError('TEST_WOULD_USE_PRODUCTION_DATA: %s %s - set AI_MANAGER_HOME to a temporary folder' % (what, Path(path).resolve()))
