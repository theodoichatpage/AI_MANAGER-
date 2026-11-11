import unittest

from automation_agent.wincontrol_chat_loop import parse_decision, validate_actions


class WinControlChatLoopTests(unittest.TestCase):
    def test_parses_one_bounded_action_from_chatgpt(self):
        decision = parse_decision('{"status":"continue","summary":"Open Notepad","actions":[{"action":"OPEN_APP","target_app":"notepad"}]}')
        self.assertEqual(decision['status'], 'continue')
        self.assertEqual(decision['actions'][0]['action'], 'OPEN_APP')

    def test_complete_decision_has_no_actions(self):
        self.assertEqual(parse_decision('{"status":"complete","summary":"Verified","actions":[]}')['status'], 'complete')

    def test_blocks_chatgpt_production_and_unsafe_unbounded_actions(self):
        for action in ('STUDIO_IMAGES', 'SEND_CHATGPT', 'CLOSE_APP', 'RESTART_APP'):
            with self.subTest(action=action), self.assertRaises(ValueError):
                validate_actions([{'action': action}])

    def test_file_actions_cannot_escape_wincontrol_temp(self):
        import tempfile
        from pathlib import Path
        with self.assertRaisesRegex(ValueError, 'FILE_PATH_OUTSIDE'):
            validate_actions([{'action':'VERIFY_FILE','path':str(Path(tempfile.gettempdir())/'outside.txt'),'expected_text':'x'}])

    def test_continue_requires_exactly_one_next_action(self):
        with self.assertRaisesRegex(ValueError, 'ONE_ACTION'):
            parse_decision('{"status":"continue","summary":"do both","actions":[{"action":"OPEN_APP","target_app":"notepad"},{"action":"WAIT","seconds":1}]}')

    def test_window_actions_need_an_explicit_app_and_no_browser_input(self):
        with self.assertRaisesRegex(ValueError, 'TARGET_APP_REQUIRED'):
            validate_actions([{'action': 'TYPE_TEXT', 'selector': {'class_name': 'Edit'}, 'text': 'x'}])
        for action in ({'action': 'TYPE_TEXT', 'target_app': 'chrome', 'selector': {'class_name': 'Edit'}, 'text': 'x'},
                       {'action': 'HOTKEY', 'target_app': 'edge', 'keys': 'CTRL+W'},
                       {'action': 'CLICK', 'target_app': 'chrome', 'selector': {'title': 'Send'}}):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'BROWSER_INPUT'):
                validate_actions([action])
        self.assertEqual(validate_actions([{'action': 'TYPE_TEXT', 'target_app': 'notepad', 'selector': {'class_name': 'Edit'}, 'text': 'x'}])[0]['target_app'], 'notepad')
        self.assertEqual(validate_actions([{'action': 'LIST_WINDOWS'}])[0]['action'], 'LIST_WINDOWS')

    def test_json_is_found_inside_chatgpt_page_text(self):
        text = 'json\nCopy code\n{"status":"continue","summary":"Mở Notepad",\n"actions":[{"action":"OPEN_APP","target_app":"notepad"}]}\nChatGPT can make mistakes. Check important info.'
        decision = parse_decision(text)
        self.assertEqual(decision['actions'][0]['target_app'], 'notepad')
        self.assertEqual(decision['summary'], 'Mở Notepad')

    def test_reply_without_json_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'JSON_INVALID'):
            parse_decision('Tôi sẽ mở Notepad ngay.')

    def test_feedback_prompt_stays_within_send_limit(self):
        from automation_agent.wincontrol_chat_loop import feedback_prompt
        huge = [{'action': 'LIST_WINDOWS', 'success': True, 'error': None, 'result': {'windows': ['x' * 500] * 200}}] * 5
        self.assertLessEqual(len(feedback_prompt('Liệt kê cửa sổ', 'ok', huge)), 11000)

    def test_prompts_are_one_line_for_the_composer_check(self):
        from automation_agent.wincontrol_chat_loop import initial_prompt, feedback_prompt, correction_prompt
        prompts = (initial_prompt('mở\nNotepad', {'temp_dir': 'x'}),
                   feedback_prompt('a\nb', 's\nx', [{'action': 'WAIT', 'success': True, 'result': {'t': 'l1\nl2'}}]),
                   correction_prompt('c', 'e\nf', 'r\ng'))
        for text in prompts:
            self.assertNotIn('\n', text)
            self.assertNotIn('\r', text)

    def test_man_health_reports_extension_and_agent_issues(self):
        from automation_agent.wincontrol_chat_loop import man_health
        health = man_health({'automation': {'online': False, 'tasks': [{'id': 't', 'status': 'needs_review', 'error': 'x'}]},
                             'extension': {'status': 'extension_lost'}, 'extension_update': {'installed': '0.5.18', 'latest': '0.5.19'}})
        self.assertEqual(set(health['issues']), {'AGENT_OFFLINE', 'EXTENSION_EXTENSION_LOST', 'EXTENSION_UPDATE_AVAILABLE', 'TASKS_NEED_REVIEW'})


if __name__ == '__main__': unittest.main()
