import json, os, tempfile, unittest
from unittest.mock import patch
import server

class StoryReviewPresenceTest(unittest.TestCase):
    """Studio's Analysis tab shows the Aprilynne review AI MANAGER ran, read from analysis/story.json."""
    def test_report_from_story_json_and_reread_on_change(self):
        with tempfile.TemporaryDirectory() as folder:
            os.makedirs(folder+'/analysis')
            rows=[{'id':i,'score':None if i in (1,8) else (9 if i<10 else 6),'part':None if i in (1,8) else 1,'evidence':'e','reason':'r','fix':'Cắt đoạn lặp'} for i in range(14)]
            story={'stage':'saved','round':2,'plan':{'title':'Trần Thủ Độ'},'sections':[{'id':'s1'}],'rows':rows,'history':[{'round':0,'passed':6},{'round':1,'passed':8}],'note':'Duyệt'}
            path=folder+'/analysis/story.json'
            with open(path,'w',encoding='utf8') as f: json.dump(story,f)
            server._STORY_CACHE.clear()
            with patch.object(server,'studio_project_folder',return_value=folder):
                rep=server.story_review('e6ae3139a690474ca5db6654cdc5f9b5')
                self.assertEqual(rep['passed'],8); self.assertEqual(rep['needed'],8)
                self.assertEqual([h['passed'] for h in rep['history']],[6,8]); self.assertEqual(len(rep['rows']),14)
                story['history'].append({'round':2,'passed':9}); story['rows'][10]['score']=9
                with open(path,'w',encoding='utf8') as f: json.dump(story,f)
                os.utime(path,ns=(os.stat(path).st_atime_ns,os.stat(path).st_mtime_ns+10**9))
                self.assertEqual(server.story_review('e6ae3139a690474ca5db6654cdc5f9b5')['passed'],9)
            with patch.object(server,'studio_project_folder',return_value=None):
                server._STORY_CACHE.clear()
                self.assertIsNone(server.story_review('e6ae3139a690474ca5db6654cdc5f9b5'))

if __name__=='__main__': unittest.main()
