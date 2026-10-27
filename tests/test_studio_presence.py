import json, time, unittest
from server import StudioPresence

class StudioPresenceTest(unittest.TestCase):
    def test_presence_reports_tab_chat_and_project_name(self):
        p=StudioPresence(ttl=15)
        p.update({'sessionId':'abc1234567890123','tabId':'tab-1','chatReady':True,'projectName':'Nhật Bản trước thời kỳ loạn lạc'})
        s=p.snapshot()
        self.assertTrue(s['studio_tab_open'])
        self.assertTrue(s['chat_connected'])
        self.assertEqual(s['session_id'],'abc1234567890123')
        self.assertEqual(s['project_name'],'Nhật Bản trước thời kỳ loạn lạc')

    def test_close_and_stale_presence_are_offline(self):
        p=StudioPresence(ttl=.01)
        p.update({'sessionId':'abc1234567890123','tabId':'tab-1','chatReady':True})
        p.update({'sessionId':'abc1234567890123','tabId':'tab-1','event':'close'})
        self.assertFalse(p.snapshot()['studio_tab_open'])
        p.update({'sessionId':'abc1234567890123','tabId':'tab-2','chatReady':True})
        time.sleep(.02)
        self.assertFalse(p.snapshot()['studio_tab_open'])
        self.assertFalse(p.snapshot()['chat_connected'])

    def test_presence_is_scoped_to_requested_session(self):
        p=StudioPresence(ttl=15)
        p.update({'sessionId':'session111111111','tabId':'tab-a','chatReady':True})
        p.update({'sessionId':'session222222222','tabId':'tab-b','chatReady':False})
        self.assertTrue(p.snapshot('session111111111')['chat_connected'])
        self.assertFalse(p.snapshot('session222222222')['chat_connected'])
        self.assertFalse(p.snapshot('session333333333')['studio_tab_open'])

    def test_close_does_not_close_another_session(self):
        p=StudioPresence(ttl=15)
        p.update({'sessionId':'session111111111','tabId':'tab-a','chatReady':True})
        p.update({'sessionId':'session222222222','tabId':'tab-a','event':'close'})
        self.assertTrue(p.snapshot('session111111111')['studio_tab_open'])

if __name__=='__main__': unittest.main()

