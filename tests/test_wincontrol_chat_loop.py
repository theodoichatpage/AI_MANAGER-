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


if __name__ == '__main__': unittest.main()
