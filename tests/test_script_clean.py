import json,os,tempfile,unittest
from unittest import mock
from automation_agent import script_clean as sc
from automation_agent import story_pipeline as sp

STORY=('Năm 1209, nhà Lý rối ren và họ Trần bước vào triều đình bằng con đường hôn nhân với hoàng tộc. '
 'Trần Thủ Độ khi ấy giữ quân túc vệ, nắm trong tay đội quân bảo vệ kinh thành và cả hoàng cung. ')

class CleanChecks(unittest.TestCase):
 """The faults of 'Bản tin 247' in the user's comparison, measured exactly."""
 def kinds(self,texts):return sc.summary(sc.check(texts))
 def test_a_clean_script_passes(self):
  self.assertEqual(sc.check(['Chào mừng các bác đến với kênh. '+STORY+'Vào video thôi!','Một năm sau, ông đưa Lý Chiêu Hoàng lên ngôi.','Đến năm 1264 ông mất. Nhớ bấm theo dõi kênh nhé.']),[])
 def test_notes_read_aloud_are_moved_out(self):
  texts,notes=sc.strip_notes(['Ông sinh năm 1194 [CẦN KIỂM TRA]. Ông mồ côi sớm.'])
  self.assertEqual(texts,['Ông sinh năm 1194. Ông mồ côi sớm.']);self.assertEqual(notes[0]['part'],1)
  self.assertIn('note',self.kinds(['Theo tư liệu được cung cấp, ông giữ quân túc vệ.']))
 def test_greetings_and_calls_in_the_middle(self):
  k=self.kinds(['Chào mừng các bác đến với Bản tin 247. Vào video thôi!','Chào mừng quý bạn trở lại. Vào video thôi! Nhớ bấm theo dõi kênh.','Hết.'])
  self.assertEqual(set(k),{'greeting','lets_go','call'})
 def test_the_same_sentence_or_passage_told_twice(self):
  self.assertIn('duplicate',self.kinds(['Câu chuyện của chúng ta bắt đầu vào những năm cuối thế kỷ 12, khi nhà Lý suy yếu.','Câu chuyện của chúng ta bắt đầu vào những năm cuối thế kỷ 12, khi nhà Lý suy yếu.']))
  anecdote='Người lính gác chặn kiệu của phu nhân Trần Thủ Độ ở cấm thành, bà về khóc lóc kể với chồng, ông cho gọi người lính đến, ai cũng nghĩ người lính sẽ bị trị tội nhưng ông lại khen ngợi và ban thưởng vàng bạc vì đã giữ đúng phép nước.'
  retold='Các bác ạ, chuyện lạ có thật: người lính gác chặn kiệu của phu nhân Trần Thủ Độ ở cấm thành, bà về khóc lóc kể với chồng, ông cho gọi người lính đến và ai cũng nghĩ người lính sẽ bị trị tội nhưng ông lại khen ngợi, ban thưởng vàng bạc.'
  self.assertIn('retold',self.kinds([anecdote,retold]))
 def test_catchphrases_hedges_and_questions(self):
  k=self.kinds(['Level Max. '+STORY,'Level Max. Đây là cách em ví von thôi.','Level Max. Đây là cách em diễn giải. Vì sao? Ai biết? Thật sao?','Kết.'])
  self.assertIn('catchphrase',k);self.assertIn('hedge',k);self.assertIn('questions',k)
 def test_every_section_reopening_with_the_address(self):
  self.assertIn('opening',self.kinds(['Các bác ạ, '+STORY]*8))

class GateInTheStoryLine(unittest.TestCase):
 def test_criterion_13_cannot_pass_while_the_machine_measures_faults(self):
  rows=[{'id':i,'score':9.0,'part':1,'evidence':'e','reason':'r','fix':''} for i in range(14)]
  clean=sc.check(['Chào mừng các bác. Vào video thôi!','Chào mừng các bác trở lại.','Hết.'])
  out=sp.gate(rows,clean)
  self.assertEqual(out[13]['score'],6.0);self.assertIn('greeting',out[13]['reason'])
  self.assertEqual(sp.gate(rows,[]),rows)
  # A clean version wins over one with more criteria passed but repetition.
  self.assertTrue(sp.better(rows,{'passed':12,'total':120,'clean':clean},[]))
 def test_repair_gets_the_measured_faults_and_the_wrong_facts(self):
  secs=[{'id':'s1','title':'A','role':'','source':'x'*100,'text':'Chào mừng các bác trở lại.'}]
  p=sp.repair_prompt(secs[0],0,1,{'title':'T'},'g',[],secs,[],[{'part':1,'kind':'greeting','detail':'Có 2 lần lời chào'}],[{'part':1,'claim':'cướp vợ của cháu','fix':'ép vua lấy vợ của anh trai vua'}])
  self.assertIn('Có 2 lần lời chào',p);self.assertIn('ép vua lấy vợ của anh trai vua',p);self.assertIn('LIỀN MẠCH',p)
 def test_facts_are_read_from_the_grading_reply(self):
  reply=json.dumps({'rows':[],'facts':[{'part':2,'claim':'Trần Nhật Hạo','fix':'Trần Nhật Hiệu'},{'part':99,'claim':'x','fix':'y'},{'claim':''}]})
  self.assertEqual(sp.accept_facts(reply,3),[{'part':2,'claim':'Trần Nhật Hạo','fix':'Trần Nhật Hiệu'},{'part':None,'claim':'x','fix':'y'}])
 def test_the_outline_asks_for_long_acts(self):
  p=sp.plan_prompt('Câu một. '*4000,'g')
  self.assertIn('HỒI lớn',p);self.assertNotIn('1.000–2.500',p)

if __name__=='__main__':unittest.main()
