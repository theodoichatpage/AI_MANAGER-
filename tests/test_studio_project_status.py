import unittest
from unittest.mock import patch
import server

class Q:
    def list(self): return [{'id':'p1','status':'completed','current_stage':'Hoàn tất','completed_scenes':173,'total_scenes':173}]

class StudioProjectStatusTest(unittest.TestCase):
    def test_linked_project_reports_manager_state(self):
        with patch.object(server,'projects',return_value=[{'id':'p1','name':'Lê Lợi','studio_project_id':'b60ba8066793432daca0897bde0a7cb8'}]):
            code,body=server.studio_project_status(Q(),'b60ba8066793432daca0897bde0a7cb8')
        self.assertEqual(code,200)
        self.assertEqual((body['status'],body['completed_scenes'],body['total_scenes']),('completed',173,173))

    def test_unknown_or_malformed_session_is_not_found(self):
        with patch.object(server,'projects',return_value=[]):
            self.assertEqual(server.studio_project_status(Q(),'b60ba8066793432daca0897bde0a7cb8')[0],404)
        self.assertEqual(server.studio_project_status(Q(),'../x')[0],404)

if __name__=='__main__': unittest.main()
