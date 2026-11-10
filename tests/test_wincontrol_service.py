import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from automation_agent.manager_service import AutomationService


class WinControlServiceTests(unittest.TestCase):
    def service(self, tasks=None):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        Path(td.name, 'settings.json').write_text(json.dumps({'chrome_mcp': {'page_url': 'https://chatgpt.com/c/test-conversation'}}), encoding='utf8')
        queue = Mock()
        queue.list.return_value = [{'id':'project-1','name':'Alpha','status':'stopped','execution_mode':'automation'}]
        with patch('automation_agent.manager_service.AgentClient') as factory:
            client = factory.return_value
            client.snapshot.return_value = {'online': True, 'tasks': tasks or [], 'pid': 123}
            def response(path, data=None, **kw):
                if path == '/state': return {'online': True, 'tasks': tasks or [], 'pid': 123, 'enabled': False, 'current_task': None}
                if path == '/submit': return {'task_id': 'new-wc-task'}
                return {'ok': True}
            client.request.side_effect = response
            service = AutomationService(Path(td.name), lambda: queue)
        return service

    def test_natural_language_task_uses_existing_chatgpt_mcp_and_agent_taskstore(self):
        service = self.service()
        result = service.control({'command':'wincontrol','text':'M? Notepad, ghi v? x?c minh t?p trong Temp'})
        self.assertEqual(result['task_id'], 'new-wc-task')
        calls = [c.args[0] for c in service.client.request.call_args_list]
        self.assertEqual(calls.count('/submit'), 1)
        self.assertEqual(calls.count('/start'), 0)
        submitted = next(c.args[1] for c in service.client.request.call_args_list if c.args[0] == '/submit')
        self.assertEqual([a['action'] for a in submitted['actions']], ['OBSERVE_CHATGPT','SEND_CHATGPT','WINCONTROL_DECIDE'])
        self.assertIn('temp_dir', submitted['actions'][1]['text'])
        self.assertTrue(submitted['context']['wincontrol_task'])
        self.assertTrue(submitted['exclusive'])
        self.assertEqual(submitted['stage'], 'WinControl')
        self.assertNotIn('studio_project_id', submitted['context'])

    def test_refuses_to_add_wincontrol_when_an_agent_task_is_active(self):
        service = self.service(tasks=[{'id':'legacy','status':'running'}])
        with self.assertRaisesRegex(ValueError, 'task'):
            service.control({'command':'wincontrol','text':'M? Notepad'})
        self.assertFalse(any(c.args[0] == '/submit' for c in service.client.request.call_args_list))

    def test_user_command_is_sent_only_to_chatgpt_as_planner_not_codex(self):
        service = self.service()
        service.control({'command':'wincontrol','text':'Ki?m tra tr?ng th?i MAN'})
        submitted = next(c.args[1] for c in service.client.request.call_args_list if c.args[0] == '/submit')
        self.assertIn('Ki?m tra tr?ng th?i MAN', submitted['actions'][1]['text'])
        self.assertNotIn('/plan', [c.args[0] for c in service.client.request.call_args_list])


if __name__ == '__main__': unittest.main()
