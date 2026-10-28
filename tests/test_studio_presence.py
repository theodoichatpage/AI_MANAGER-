import json, time, unittest
from unittest.mock import patch
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

    def test_studio_name_does_not_rename_unrelated_local_project(self):
        import server
        class Q:
            def list(self): return [{'id':'local-1','name':'Local','status':'waiting'}]
            def logs(self): return []
            def batch(self): return []
        with patch.object(server,'projects',return_value=[{'id':'local-1','name':'Local'}]), patch.object(server.STUDIO,'snapshot',return_value={'configured':True,'data':{'project_id':'remote-1','project_name':'Studio'},'status':'connected'}), patch.object(server.PRESENCE,'snapshot',return_value={'studio_tab_open':False}):
            self.assertEqual(server.synchronized_state(Q())['projects'][0]['name'],'Local')

if __name__=='__main__': unittest.main()

