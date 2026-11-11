import unittest

from automation_agent.chatgpt_mcp import parse_snapshot
from automation_agent.wincontrol_chat_loop import parse_decision

URL = 'https://chatgpt.com/c/x'
# Chrome DevTools MCP take_snapshot prints text verbatim: inner quotes are not escaped.
SNAPSHOT = '''uid=1_0 RootWebArea "T" url="https://chatgpt.com/c/x"
  uid=1_1 heading "You said:" level="4"
  uid=1_2 "[wincontrol-abc-1] WinControl task. {"user_command": "Mở \\"Notepad\\""}"
  uid=1_3 heading "ChatGPT said:" level="4"
  uid=1_4 "{"status":"continue","summary":"Mở Notepad","actions":[{"action":"OPEN_APP","target_app":"notepad"}]}"
  uid=1_5 button "Copy"
  uid=1_6 textbox "Ask ChatGPT" multiline value="
"'''


class VerbatimSnapshotTests(unittest.TestCase):
    def test_user_prompt_and_json_reply_with_inner_quotes_are_read_whole(self):
        r = parse_snapshot(SNAPSHOT, URL)
        self.assertTrue(r['lastUserText'].startswith('[wincontrol-abc-1] '))
        self.assertTrue(r['lastUserText'].endswith('}'))
        decision = parse_decision(r['lastAssistant'])
        self.assertEqual(decision['actions'][0]['action'], 'OPEN_APP')


if __name__ == '__main__':
    unittest.main()
