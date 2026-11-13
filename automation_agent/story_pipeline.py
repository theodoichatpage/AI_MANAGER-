"""Story pipeline run by AI MANAGER, one straight line with one owner:
transcript -> Aprilynne outline (with the split) -> every section written to its role -> joined -> Aprilynne review,
repairs of the failing sections, review again (3 rounds, best version kept) -> the approved script goes to Studio.

ChatGPT work is handed to the Studio tabs as plain tasks (the Studio server's rewrite list: id, title, prompt -> text),
the same way the parallel rewrite already works. The tabs only execute; every decision and all state live here, in
analysis/story.json, so reloading a Studio tab or the browser changes nothing."""
import hashlib,json,re,urllib.request
from pathlib import Path
from . import script_clean

THRESHOLD=8
ROUNDS=3
MAX_ROUNDS=6        # after ROUNDS, repairing goes on while every round still raises the score, up to this many rounds
PASS_NEEDED=8         # the analysis is approved when at least this many of the 12 criteria the script can show score 8 or more
PASS_AFTER_ROUNDS=PASS_NEEDED   # rounds used up: the best version must still reach it, or the run stops for the user
TASK_TRIES=5          # a task whose reply cannot be used is asked again this many times
REVIEW_OPENING=350;REVIEW_MIDDLE=250;REVIEW_ENDING=350

CRITERIA=[
 ('Câu đầu khớp tiêu đề','0:52','0:57','trong 5 giây đầu'),
 ('Cảnh đầu khớp ảnh bìa','0:54','0:57','trong 5 giây đầu'),
 ('Bối cảnh mở đầu','2:33','2:48','trong 20 giây đầu'),
 ('Phần thưởng hoặc cái giá phải trả','2:40','2:48','trong 20 giây đầu'),
 ('Khoảng trống tò mò','2:45','2:48','trong 20 giây đầu'),
 ('Đáp ứng rồi vượt kỳ vọng','3:34','3:56',''),
 ('Thể hiện công sức thực tế','5:05','5:37',''),
 ('Bắt đầu nội dung chính sớm','6:18','7:03','chậm nhất ở giây 20'),
 ('Đa dạng hình ảnh','7:16','7:35','đổi cảnh mỗi 3–5 giây theo ví dụ'),
 ('Tương phản','8:47','9:32',''),
 ('Luân phiên nhịp độ và năng lượng','10:20','11:19','chu kỳ thường 2–4 phút, tùy video'),
 ('Hé lộ phần thưởng lớn','11:57','12:02',''),
 ('Kết thúc ở cao trào','12:02','12:06',''),
 ('Kiểm tra và cắt đoạn gây chán','13:36','14:04',''),
]
# Graded later from the cover and the cut, not from the script.
VISUAL={1,8}
# Kịch bản liền mạch như một câu chuyện, không như nhiều tập phim nối lại (đo bằng máy trong script_clean, đọc thành quy tắc ở đây).
FLOW_RULES=('LIỀN MẠCH: một lời chào và một "vào video" duy nhất ở mở đầu; lời kêu gọi theo dõi chỉ ở đầu và cuối video; '
 'mạch thời gian đi một chiều, mỗi sự kiện và giai thoại chỉ kể MỘT lần, không báo trước rồi kể lại, không tóm tắt lại điều vừa kể; '
 'không mở phần bằng "Các bác ạ" hay lời chào lại, nối thẳng từ câu cuối của phần trước bằng sự kiện; tối đa một câu hỏi treo ở cuối phần, còn lại là câu kể; '
 'mỗi câu cửa miệng của kênh dùng tối đa hai lần cả video; một câu rào đón chung (lời thoại theo sử cũ và giai thoại) chỉ ở đầu video; '
 'khi đổi giọng đánh giá nhân vật thì có câu bắc cầu; tính từ cường điệu dùng tiết chế.')
CALL_TO_ACTION='Lời kêu gọi theo giọng của kênh, tự nhiên như nói với bạn bè, ví dụ: "Nếu đây là lần đầu bạn xem video của kênh, hãy bấm theo dõi và thích video để cùng đồng hành khám phá những câu chuyện lịch sử thú vị".'
# How this channel meets a criterion: used to grade it and to repair a section that fails it.
RULES={
 6:'THỂ HIỆN CÔNG SỨC THỰC TẾ: cả video chỉ cần MỘT HAI đoạn kể tự nhiên, giọng tâm sự, về công tìm hiểu, ví dụ "trong rất nhiều tài liệu viết về ông, có hai bộ sách đáng tin nhất là…, Toàn thư chép rằng…"; dẫn sử liệu có thật (Đại Việt sử ký toàn thư, An Nam chí lược, Khâm định Việt sử thông giám cương mục, Lịch triều hiến chương loại chí…), tên sách, điều sách chép, niên đại. Không bịa số quyển, số trang, lời trích hay thời gian tìm hiểu. TUYỆT ĐỐI không đưa ghi chú biên tập vào lời đọc ([CẦN KIỂM TRA], "theo tư liệu được cung cấp", "tư liệu đầu vào") và không rào đón ở từng đoạn; chi tiết chưa chắc thì bỏ hoặc nói gọn "sử cũ chép rằng". Sai sự thật (tên người, quan hệ, ai làm gì) bị trừ điểm nặng.',
 13:'KIỂM TRA VÀ CẮT ĐOẠN GÂY CHÁN: chấm theo quy tắc liền mạch: '+FLOW_RULES,
 9:'TƯƠNG PHẢN: hai tuyến truyện đối lập nhau về quy mô hoặc toan tính và đan xen nhau, ví dụ tuyến chính là đại sự triều chính, tuyến phụ là ngoại truyện về đời tư của nhân vật hoặc một sự kiện ít ai biết; hai tuyến soi chiếu nhau. Chỉ dùng chuyện có thật.',
}
HIGHLIGHT=re.compile(r'sử ký|sử chép|chí lược|cương mục|hiến chương|chính sử|dã sử|tài liệu|bộ sách|ghi chép|văn bia|giai thoại|ít ai biết|đời tư|ngoại truyện|tuyến|kiểm chứng|tra cứu|đối chiếu|CẦN KIỂM TRA',re.I)
TRANSCRIPT_ENGINE='http://127.0.0.1:8000/transcript'

def _sec(v):m,s=v.split(':');return int(m)*60+int(s)
def reference(ids=None):
 lines=(Path(__file__).parent/'data'/'aprilynne_transcript.txt').read_text(encoding='utf8').splitlines()
 out=[]
 for i,(name,start,end,timing) in enumerate(CRITERIA):
  if ids is not None and i not in ids:continue
  ex=[l for l in lines if re.match(r'^\[(\d+:\d+)\]',l) and _sec(start)<=_sec(re.match(r'^\[(\d+:\d+)\]',l).group(1))<_sec(end)]
  out.append('%d. %s%s\n%s'%(i,name,' ('+timing+')' if timing else '','\n'.join(ex)))
 return '\n'.join(out)

def units(text):
 """Addressable sentences of the transcript; ChatGPT only chooses where parts end, the text itself is never retyped."""
 return [u for u in re.findall(r'.*?(?:[.!?…。！？]+["”\'’)\]]*(?=\s|$)|\n+|$)',text,re.S) if u]

def acts(length):
 """How many acts a transcript of this length is written in (about 7,000 characters each, 2 to 8)."""
 n=max(2,min(8,round(length/7000)))
 return max(2,n-1),min(8,n+1)

def plan_prompt(text,style):
 us=units(text)
 numbered=json.dumps([[i+1,u] for i,u in enumerate(us)],ensure_ascii=False)
 return ('Bạn là biên tập viên kịch bản YouTube. Đọc toàn bộ transcript (đã đánh số %d đoạn nguồn) và làm hai việc. '
  '1) Lập DÀN Ý cho video sẽ được viết lại từ transcript này theo công thức Aprilynne: title là tiêu đề YouTube chuẩn SEO, gây tò mò, tối đa 70 ký tự, đúng sự thật; '
  'hook là câu mở đầu khớp tiêu đề; question là câu hỏi lớn xuyên suốt; promise là lời hứa với người xem trong 20 giây đầu; '
  'tracks là hai tuyến truyện đối lập nhau về quy mô hoặc toan tính (tuyến chính và một ngoại truyện về đời tư hoặc sự kiện ít ai biết, có thật); '
  'turns là các điểm chuyển nhịp khoảng 2–4 phút một lần; payoff là phần thưởng lớn hé lộ gần cuối; ending là kết ở cao trào; '
  'sources là các sử liệu, tài liệu có thật nên dẫn để thể hiện công sức tìm hiểu; cover là ảnh bìa: nhân vật chính ở giữa, hai bên là hai kết quả đối lập. '
  '2) Chia transcript thành %d–%d HỒI lớn theo các chặng của câu chuyện (ví dụ khởi nghiệp, đoạt quyền, khủng hoảng, chiến tranh, kỷ cương, kết), mỗi hồi khoảng 5.000–10.000 ký tự, không cắt giữa một chặng; mỗi hồi có role là vai trò của nó trong dàn ý. '
  'end là số thứ tự đoạn nguồn CUỐI của phần; phần đầu bắt đầu ở đoạn 1, phần sau bắt đầu ngay sau end của phần trước, end tăng dần, end cuối bằng %d. Không chép lại transcript. '
  'Chỉ trả MỘT JSON: {"plan":{"title":"...","hook":"...","question":"...","promise":"...","tracks":["...","..."],"turns":"...","payoff":"...","ending":"...","sources":"...","cover":"..."},'
  '"branches":[{"title":"tên ngắn","end":1,"role":"vai trò trong dàn ý"}]}.\nPHONG CÁCH KÊNH (để hiểu giọng, chưa viết): %s\nTRANSCRIPT: %s')%(len(us),*acts(len(text)),len(us),json.dumps(style[:3000],ensure_ascii=False),numbered)

def parse_json(text):
 t=str(text or '').strip()
 t=re.sub(r'^```(?:json)?\s*','',t,flags=re.I);t=re.sub(r'\s*```$','',t)
 i=t.find('{');j=t.rfind('}')
 return json.loads(t[i:j+1] if i>=0 and j>i else t)

def accept_plan(reply,text):
 v=parse_json(reply);p=v.get('plan') or {};br=v.get('branches') or []
 if not isinstance(p,dict) or not str(p.get('title') or '').strip():raise ValueError('Dàn ý thiếu tiêu đề')
 us=units(text);start=0;sections=[]
 for i,b in enumerate(br):
  end=b.get('end')
  if not isinstance(end,int) or end<=start or end>len(us):raise ValueError('Mốc chia phần không hợp lệ')
  src=''.join(us[start:end]).strip()
  if src:sections.append({'id':'s%d'%(len(sections)+1),'title':str(b.get('title') or 'Phần %d'%(i+1))[:120],'role':str(b.get('role') or '')[:500],'source':src,'text':''})
  start=end
 if start!=len(us) or not sections:raise ValueError('Các phần chưa bao phủ toàn bộ transcript')
 keys=('title','hook','question','promise','turns','payoff','ending','sources','cover')
 plan={k:str(p.get(k) or '').strip()[:1500] for k in keys};plan['tracks']=[str(x)[:600] for x in (p.get('tracks') or [])][:3]
 return plan,sections

def write_prompt(sec,i,n,plan,style,sections):
 L=len(sec['source'])
 role=['Đây là PHẦN MỞ ĐẦU: câu đầu tiên chính là hook, khớp với tiêu đề; trong 20 giây đầu nêu bối cảnh, câu hỏi lớn, cái giá hoặc phần thưởng và lời hứa; sau đoạn mở đầu chèn một '+CALL_TO_ACTION if i==0 else '',
  'Đây là PHẦN KẾT: hé lộ phần thưởng lớn, kết thúc ở cao trào, rồi kết bằng một '+CALL_TO_ACTION+' và mời bình luận.' if i==n-1 else '',
  'Đây là một hồi ở giữa: nối thẳng từ chỗ hồi trước dừng (không chào lại, không mở bằng "Các bác ạ", không tóm tắt lại); kết hồi bằng sự kiện dẫn sang hồi sau, tối đa một câu hỏi treo.' if 0<i<n-1 else '']
 ctx=' | '.join(x for x in (sections[i-1]['title'] if i>0 else '',sections[i+1]['title'] if i<n-1 else '') if x)
 return ('Bạn là biên tập viên viết lại kịch bản YouTube. Chỉ viết lại PHẦN HIỆN TẠI, không viết các phần khác. Giữ đủ sự kiện và ý nghĩa, không bịa dữ kiện.\n'
  'ĐỘ DÀI: khoảng %d–%d ký tự, gần bằng phần nguồn; không kéo dài, cắt chi tiết thừa và đoạn gây chán.\n'
  'PHONG CÁCH CÁ NHÂN:\n%s\nDÀN Ý APRILYNNE CỦA CẢ VIDEO (viết đúng vai trò của phần này):\n%s\nVAI TRÒ PHẦN NÀY (%d/%d): %s\n%s\n'
  'Đan xen hai tuyến truyện khi phần này có chất liệu; nói tới sử liệu thì kể tự nhiên, chỉ dẫn nguồn có thật, không ghi chú biên tập.\n%s\n'
  'PHẦN LIỀN KỀ: %s\nNGUỒN HỒI TRƯỚC KẾT Ở: %s\nNGUỒN HỒI SAU BẮT ĐẦU: %s\nPHẦN HIỆN TẠI - %s:\n%s\nChỉ trả nội dung kịch bản đã viết lại, không markdown.')%(
  round(L*0.9),round(L*1.3),style,json.dumps({k:plan.get(k) for k in ('title','hook','question','promise','tracks','turns','payoff','ending','sources')},ensure_ascii=False),
  i+1,n,sec.get('role') or 'tiếp nối mạch kể',' '.join(x for x in role if x),FLOW_RULES,ctx,
  sections[i-1]['source'][-600:] if i>0 else '(đây là hồi đầu)',sections[i+1]['source'][:400] if i<n-1 else '(đây là hồi cuối)',sec['title'],sec['source'])

def edit_prompt(sec,i,n,plan,style,sections,issues):
 """One pass over an act already written, with the acts around it: the whole script reads as one story (the step that made the Say Sử script flow)."""
 told=[{'hồi':k+1,'tên':x['title'],'vai trò':x.get('role') or ''} for k,x in enumerate(sections)]
 mine=[x['detail'] for x in issues if x['part']==i+1]
 return ('Bạn là biên tập viên kịch bản YouTube. Biên tập lại HỒI %d/%d cho liền mạch với cả video, KHÔNG thêm sự kiện mới, không kéo dài: bản trả về ngắn hơn hoặc bằng bản hiện tại.\n%s\n'
  'Việc cần làm: xóa câu và ý lặp với chính hồi này hoặc với hồi trước; mỗi giai thoại chỉ kể một lần; xóa ghi chú biên tập và câu rào đón; câu đầu nối thẳng từ câu cuối hồi trước; '
  'khi giọng đánh giá nhân vật đổi thì thêm một câu bắc cầu; giữ giọng kênh, dữ kiện, các đoạn [HÌNH: …].\n'
  'LỖI MÁY ĐÃ ĐO Ở HỒI NÀY: %s\nPHONG CÁCH CÁ NHÂN:\n%s\nDÀN Ý: %s\nCÁC HỒI CỦA VIDEO: %s\nCUỐI HỒI TRƯỚC: %s\nĐẦU HỒI SAU: %s\nHỒI HIỆN TẠI - %s:\n%s\n'
  'Chỉ trả nội dung đầy đủ của hồi này sau khi biên tập, không markdown.')%(
  i+1,n,FLOW_RULES,json.dumps(mine,ensure_ascii=False) if mine else 'không có',style,
  json.dumps({k:plan.get(k) for k in ('title','question','promise','tracks','turns','payoff','ending')},ensure_ascii=False),json.dumps(told,ensure_ascii=False),
  sections[i-1]['text'][-1500:] if i>0 else '(đây là hồi đầu)',sections[i+1]['text'][:800] if i<n-1 else '(đây là hồi cuối)',sec['title'],sec['text'])

def review_prompt(plan,sections,style,last_error=''):
 parts=[]
 for i,s in enumerate(sections):
  t=s['text'];m=len(t)//2
  ex=[t] if len(t)<=1400 else [t[:REVIEW_OPENING],t[m-REVIEW_MIDDLE//2:m+REVIEW_MIDDLE//2],t[-REVIEW_ENDING:]]
  hl=[] if len(t)<=1400 else [p[:400] for p in re.split(r'\n\s*\n',t) if HIGHLIGHT.search(p) and not any(p[:80] in e for e in ex)][:1]
  parts.append(dict({'part':i+1,'title':s['title'],'excerpts':ex},**({'highlights':hl} if hl else {})))
 rules=' '.join('mục %d — %s'%(k,v) for k,v in RULES.items())
 return ('Bạn là biên tập viên kịch bản YouTube. Chỉ trả một JSON hoàn chỉnh.\nPHONG CÁCH CÁ NHÂN: %s\nCÔNG THỨC APRILYNNE:\n%s\n'
  'Đối chiếu cấu trúc toàn video dựa trên các trích đoạn theo đúng thứ tự các phần; highlights là các đoạn nói về nguồn sử liệu, công sức tìm hiểu hoặc tuyến truyện phụ. '
  'Tiêu đề đích là "%s"; chấm mục 0 theo độ khớp của câu mở đầu với tiêu đề này. Chấm từng tiêu chí 0–10 theo đúng ID (0–%d); part là số phần (bắt đầu từ 1) chứa dẫn chứng, evidence là đoạn trích từ phần đó. '
  'Nếu dưới %d, chọn phần cần sửa nhất và ghi cách sửa cụ thể. Mục 1 và 8 cần ảnh bìa/cảnh dựng thật nên trả score:null, part:null, evidence:"". Cách chấm riêng: %s '
  'Trả {"rows":[{"id":0,"score":7,"part":1,"evidence":"...","reason":"...","fix":"..."}]} với đủ %d dòng; reason và fix mỗi dòng tối đa một câu ngắn, trả lời ngay.%s\n%s')%(
  json.dumps(style[:3000],ensure_ascii=False),reference(),plan.get('title',''),len(CRITERIA)-1,THRESHOLD,rules,len(CRITERIA),
  (' LƯU Ý: lần trước bị từ chối vì: '+last_error) if last_error else '',json.dumps({'plan':plan,'parts':parts},ensure_ascii=False))

# One long review made ChatGPT think past the tab watchdog: short reviews instead, each with only the text it needs.
GROUPS=[('open',[0,2,3,4,5,7]),('body',[6,9,10,13]),('end',[11,12])]
BODY_IDS=[6,9,10,13]
BODY_CHUNK=14000   # characters of full script per body review: deep enough to judge pace and boring passages, short enough to answer fast
# A body criterion graded on several chunks: shown research and contrast count where they are strongest; pace and boring passages where they are weakest.
BODY_BEST={6,9}
def body_chunks(sections):
 """Consecutive section indexes, each chunk at most BODY_CHUNK characters (a longer section stays alone)."""
 out=[];cur=[];size=0
 for i,s in enumerate(sections):
  L=len(s.get('text') or '')
  if cur and size+L>BODY_CHUNK:out.append(cur);cur=[];size=0
  cur.append(i);size+=L
 if cur:out.append(cur)
 return out
def review_groups(sections,legacy=False):
 """(name, criteria ids) of one review round. A short script keeps the single 'body' review; a long one is read in full, chunk by chunk."""
 chunks=body_chunks(sections)
 if legacy or len(chunks)<=1:return GROUPS
 return [GROUPS[0]]+[('body%d'%(k+1),BODY_IDS) for k in range(len(chunks))]+[GROUPS[2]]
def combine(groups,got_rows):
 """The 14 rows of a round, plus findings: weak sections seen by the other body chunks, so each of them is repaired too."""
 by={};findings=[]
 for g,ids in groups:
  for r in got_rows[g]:
   old=by.get(r['id'])
   if old is None:by[r['id']]=r;continue
   better=(r['score']>old['score']) if r['id'] in BODY_BEST else (r['score']<old['score'])
   keep,drop=(r,old) if better else (old,r)
   by[r['id']]=keep
   if drop['score']<THRESHOLD and r['id'] not in BODY_BEST:findings.append(drop)
 rows=[by.get(i) or {'id':i,'score':None,'part':None,'evidence':'','reason':'Cần ảnh bìa/cảnh dựng thật','fix':''} for i in range(len(CRITERIA))]
 return rows,findings
def group_parts(g,sections):
 n=len(sections)
 if g=='open':return [{'part':i+1,'title':sections[i]['title'],'text':sections[i]['text']} for i in range(min(2,n))]
 if g=='end':return [{'part':i+1,'title':sections[i]['title'],'text':sections[i]['text']} for i in range(max(0,n-3),n)]
 if g!='body':return [{'part':i+1,'title':sections[i]['title'],'text':sections[i]['text']} for i in body_chunks(sections)[int(g[4:])-1]]
 out=[]
 for i,s in enumerate(sections):
  t=s['text'];m=len(t)//2
  ex=[t] if len(t)<=900 else [t[:250],t[m-100:m+100],t[-250:]]
  hl=[] if len(t)<=900 else [p[:400] for p in re.split(r'\n\s*\n',t) if HIGHLIGHT.search(p) and not any(p[:80] in e for e in ex)][:1]
  out.append(dict({'part':i+1,'title':s['title'],'excerpts':ex},**({'highlights':hl} if hl else {})))
 return out
def group_prompt(g,ids,plan,sections,style,last_error=''):
 rules=' '.join('mục %d — %s'%(k,v) for k,v in RULES.items() if k in ids)
 scope={'open':'phần mở đầu của video (các phần đầu, đầy đủ)','end':'phần kết của video (các phần cuối, đầy đủ)','body':'toàn video qua trích đoạn theo thứ tự; highlights là các đoạn về nguồn sử liệu, công sức tìm hiểu hoặc tuyến truyện phụ'}.get(g)
 if scope is None:
  ch=body_chunks(sections);idx=ch[int(g[4:])-1]
  scope=('đoạn %s/%d của video: TOÀN VĂN các phần %d–%d trên tổng %d phần (mục lục cả video: %s). Đọc từng câu: chỉ ra đoạn lặp ý, giảng giải dài, câu hỏi tu từ lặp mô thức, chỗ nhịp phẳng; '
   'chỗ dẫn sử liệu cụ thể (tên sách, điều sách chép) và chỗ hai tuyến truyện soi chiếu nhau. Chấm theo những gì có trong đoạn này')%(
   g[4:],len(ch),idx[0]+1,idx[-1]+1,len(sections),json.dumps([s['title'] for s in sections],ensure_ascii=False))
 return ('Bạn là biên tập viên kịch bản YouTube. Chấm kỹ nhưng trả lời ngay, chỉ trả một JSON.\nCÔNG THỨC APRILYNNE (chỉ các tiêu chí cần chấm):\n%s\n'
  'Đối chiếu %s. Tiêu đề đích: "%s". Chấm 0–10 đúng các ID %s; part là số phần chứa dẫn chứng, evidence trích nguyên văn từ phần đó, reason nói vì sao được điểm ấy; '
  'nếu dưới %d thì BẮT BUỘC có fix: cách sửa cụ thể (câu/đoạn nào, thêm hay cắt gì), không chung chung. %s'
  'Thêm "facts": tối đa 5 khẳng định sai hoặc đáng ngờ về sự thật trong đoạn được chấm (tên người, quan hệ, ai làm gì, năm), mỗi mục {"part":1,"claim":"trích","fix":"nên sửa thành"}; không có thì trả [].'
  'Trả {"rows":[{"id":%d,"score":7,"part":1,"evidence":"trích ngắn","reason":"một câu","fix":"một câu"}],"facts":[]} gồm đúng %d dòng.%s\nPHONG CÁCH KÊNH: %s\nDÀN Ý: %s\nKỊCH BẢN: %s')%(
  reference(ids),scope,plan.get('title',''),ids,THRESHOLD,('Cách chấm riêng: '+rules+' ') if rules else '',ids[0],len(ids),
  (' LƯU Ý: lần trước bị từ chối vì: '+last_error) if last_error else '',json.dumps(style[:1500],ensure_ascii=False),
  json.dumps({k:plan.get(k) for k in ('title','hook','question','promise','tracks','payoff','ending','sources')},ensure_ascii=False),json.dumps(group_parts(g,sections),ensure_ascii=False))
def accept_group(reply,ids,n):
 v=parse_json(reply);by={r['id']:r for r in v.get('rows') or [] if isinstance(r,dict) and isinstance(r.get('id'),int)}
 out=[]
 for i in ids:
  r=by.get(i)
  if r is None:raise ValueError('Thiếu tiêu chí '+CRITERIA[i][0])
  sc=r.get('score');pt=r.get('part')
  if not isinstance(sc,(int,float)) or not 0<=sc<=10:raise ValueError('Điểm không hợp lệ cho '+CRITERIA[i][0])
  if not isinstance(pt,int) or not 1<=pt<=n:pt=1
  # A low score without a concrete fix cannot drive a repair: ask again.
  if sc<THRESHOLD and len(str(r.get('fix') or '').strip())<8:raise ValueError('Thiếu cách sửa cụ thể cho '+CRITERIA[i][0]+' (điểm dưới %d)'%THRESHOLD)
  out.append({'id':i,'score':float(sc),'part':pt,'evidence':str(r.get('evidence') or '')[:800],'reason':str(r.get('reason') or '')[:800],'fix':str(r.get('fix') or '')[:800]})
 return out

def accept_facts(reply,n):
 """Doubtful facts the grader listed: kept as notes for the editor and given to the repair of their section."""
 try:v=parse_json(reply)
 except ValueError:return []
 out=[]
 for f in (v.get('facts') or [])[:5] if isinstance(v,dict) else []:
  if not isinstance(f,dict) or not str(f.get('claim') or '').strip():continue
  pt=f.get('part')
  out.append({'part':pt if isinstance(pt,int) and 1<=pt<=n else None,'claim':str(f['claim'])[:300],'fix':str(f.get('fix') or '')[:300]})
 return out

def accept_review(reply,n):
 v=parse_json(reply);rows=v.get('rows')
 if not isinstance(rows,list):raise ValueError('Báo cáo không có rows')
 by={}
 for r in rows:
  if isinstance(r,dict) and isinstance(r.get('id'),int):by[r['id']]=r
 out=[]
 for i,(name,*_) in enumerate(CRITERIA):
  r=by.get(i)
  if r is None:raise ValueError('Thiếu tiêu chí '+name)
  if i in VISUAL:out.append({'id':i,'score':None,'part':None,'reason':str(r.get('reason') or ''),'fix':str(r.get('fix') or ''),'evidence':''});continue
  sc=r.get('score');pt=r.get('part')
  if not isinstance(sc,(int,float)) or not 0<=sc<=10:raise ValueError('Điểm không hợp lệ cho '+name)
  if not isinstance(pt,int) or not 1<=pt<=n:pt=1
  out.append({'id':i,'score':float(sc),'part':pt,'evidence':str(r.get('evidence') or '')[:800],'reason':str(r.get('reason') or '')[:800],'fix':str(r.get('fix') or '')[:800]})
 return out

def passed(rows):return sum(1 for r in rows if r['score'] is not None and r['score']>=THRESHOLD)
def total(rows):return sum(r['score'] for r in rows if r['score'] is not None)
def better(rows,best,clean=()):
 """A script that passes the machine check wins; then more criteria passed; on a tie the higher total score (a repair that lifts 6 to 7.5 still counts)."""
 return not best or (not clean,passed(rows),total(rows))>(not best.get('clean'),best['passed'],best.get('total',total(best.get('rows') or [])))
def failing_parts(rows,findings=(),clean=()):
 return sorted({r['part']-1 for r in list(rows)+list(findings) if r['score'] is not None and r['score']<THRESHOLD and r.get('part')}|{x['part']-1 for x in clean if x.get('part')})
def gate(rows,clean):
 """Criterion 13 (cut the boring parts) cannot pass while the machine still measures repetition or notes read aloud."""
 if not clean:return rows
 kinds=script_clean.summary(clean)
 out=[]
 for r in rows:
  if r['id']==13 and r['score'] is not None and r['score']>6:
   r=dict(r,score=6.0,reason='Máy đo còn lỗi liền mạch: '+', '.join('%s %d'%(k,v) for k,v in kinds.items())+'. '+str(r.get('reason') or ''),fix=clean[0]['detail'])
  out.append(r)
 return out

def repair_prompt(sec,i,n,plan,style,rows,sections,findings=(),clean=(),facts=()):
 issues=[r for r in list(rows)+list(findings) if r['part']==i+1 and r['score'] is not None and r['score']<THRESHOLD]
 measured=[x['detail'] for x in clean if x['part']==i+1]
 wrong=[{'khẳng định':f['claim'],'sửa':f['fix']} for f in facts if f.get('part')==i+1]
 rules=' '.join(dict.fromkeys(RULES[r['id']] for r in issues if r['id'] in RULES))
 # Criteria this section already meets: the repair must not break them (e.g. cutting the hook while trimming boring passages).
 keep=[CRITERIA[r['id']][0]+(': "'+r['evidence'][:200]+'"' if r.get('evidence') else '') for r in rows if r['part']==i+1 and r['score'] is not None and r['score']>=THRESHOLD]
 return ('Bạn là biên tập viên kịch bản YouTube. Chỉ sửa PHẦN %d/%d theo các tiêu chí Aprilynne chưa đạt gửi kèm, làm đúng từng "cách sửa". Giữ những đoạn tốt, dữ kiện, giọng kênh và liên kết với các phần khác; '
  'không kéo dài quá %d ký tự; khi tiêu chí là nhịp độ hoặc đoạn gây chán thì ưu tiên CẮT và gộp ý lặp hơn là viết thêm. %s\nPHONG CÁCH CÁ NHÂN:\n%s\nDÀN Ý: %s\nVAI TRÒ PHẦN NÀY: %s\nTIÊU CHÍ CHƯA ĐẠT: %s\n'
  'TIÊU CHÍ ĐANG ĐẠT Ở PHẦN NÀY (giữ nguyên ý và câu dẫn chứng, không làm yếu đi): %s\nLỖI LIỀN MẠCH MÁY ĐÃ ĐO (phải hết sau khi sửa): %s\nKHẲNG ĐỊNH CẦN SỬA CHO ĐÚNG SỰ THẬT: %s\n%s\nĐOẠN CUỐI PHẦN TRƯỚC: %s\nĐOẠN ĐẦU PHẦN SAU: %s\n'
  'PHẦN HIỆN TẠI - %s:\n%s\nChỉ trả nội dung đầy đủ của phần này sau khi sửa, không markdown.')%(
  i+1,n,round(len(sec['source'])*1.4),rules,style,json.dumps(plan,ensure_ascii=False),sec.get('role') or '',
  json.dumps([{'tiêu chí':CRITERIA[r['id']][0],'điểm':r['score'],'lý do':r['reason'],'cách sửa':r['fix']} for r in issues],ensure_ascii=False),
  json.dumps(keep,ensure_ascii=False) if keep else 'không có',
  json.dumps(measured,ensure_ascii=False) if measured else 'không có',json.dumps(wrong,ensure_ascii=False) if wrong else 'không có',FLOW_RULES,
  sections[i-1]['text'][-800:] if i>0 else '',sections[i+1]['text'][:600] if i<n-1 else '',sec['title'],sec['text'])

def studio_report(d):
 """What the Studio Analysis tab shows for a project whose story line AI MANAGER runs: stage, scores with reasons and fixes, scores per round."""
 if not isinstance(d,dict) or not d.get('stage'):return None
 rows=d.get('rows') or []
 cut=lambda v,n:str(v or '')[:n]
 return {'stage':str(d.get('stage')),'round':int(d.get('round') or 0),'rounds':ROUNDS,'maxRounds':MAX_ROUNDS,'needed':PASS_NEEDED,'threshold':THRESHOLD,
  'title':cut((d.get('plan') or {}).get('title'),200),'sections':len(d.get('sections') or []),'passed':passed(rows) if rows else None,'note':cut(d.get('note'),300),
  'error':cut(d.get('last_error'),300),
  'rows':[{'id':r.get('id'),'score':r.get('score'),'part':r.get('part'),'evidence':cut(r.get('evidence'),300),'reason':cut(r.get('reason'),500),'fix':cut(r.get('fix'),500)} for r in rows],
  'findings':[{'id':r.get('id'),'score':r.get('score'),'part':r.get('part'),'fix':cut(r.get('fix'),300)} for r in (d.get('findings') or [])][:30],
  'history':[{'round':h.get('round'),'passed':h.get('passed')} for h in (d.get('history') or [])][-12:],
  'clean':[{'kind':x.get('kind'),'part':x.get('part'),'detail':cut(x.get('detail'),200)} for x in (d.get('clean') or [])][:30],
  'notes':[{'part':x.get('part'),'note':cut(x.get('note'),200)} for x in (d.get('notes') or [])][:30],
  'facts':[{'part':x.get('part'),'claim':cut(x.get('claim'),200),'fix':cut(x.get('fix'),200)} for x in (d.get('facts') or [])][:20]}

def fetch_transcript(url,language='vi'):
 body=json.dumps({'url':url,'languages':[language,'en']}).encode()
 with urllib.request.urlopen(urllib.request.Request(TRANSCRIPT_ENGINE,body,{'content-type':'application/json'},method='POST'),timeout=120) as r:d=json.loads(r.read())
 text=str(d.get('text') or '').strip() or ' '.join(str(s.get('text') or '').strip() for s in d.get('segments') or [] if str(s.get('text') or '').strip())
 if not text:raise RuntimeError('Transcript Engine trả transcript trống')
 return text

class Story:
 def __init__(self,w,script=None):
  self.w=w;self.path=Path(w.folder)/'analysis'/'story.json'
  self.lanes={}
  try:self.d=json.loads(self.path.read_text(encoding='utf8'))
  except FileNotFoundError:
   # A script pasted in Manager (no YouTube link): outlined and split by ChatGPT, kept word for word, then graded and repaired.
   self.d={'stage':'plan','tries':{},'transcript':script,'source':'script'} if script else {'stage':'fetch','tries':{}}
 def save(self):
  from .studio_workflow import atomic
  atomic(self.path,self.d)
 def style(self):return str(self.w.c.get('studio_rewrite_style') or '')
 def wait(self,key,message,**extra):
  self.save();return self.w.wait('story:'+key,1800,dict(studio_stage='Viết kịch bản',studio_message=message,**extra))
 def tasks(self,s,tasks):
  """Make the Studio task list exactly `tasks` (id, title, prompt), hand them to the free tabs and return the replies {id: section}."""
  want=hashlib.sha256(json.dumps([[t['id'],t['prompt']] for t in tasks],ensure_ascii=False).encode()).hexdigest()
  if self.d.get('list')!=want:
   if any(j.get('type')=='transcript_rewrite' for j in s.get('laneJobs') or []):return None
   s=self.w.api.request(self.w.sid,'/rewrite',{'sections':tasks});self.d['list']=want;self.save()
  from .studio_lanes import rewrite_round
  self.lanes=rewrite_round(self.w,s,single=len(tasks)==1)
  return {x.get('id'):x for x in ((s.get('rewrite') or {}).get('sections') or [])}
 def task_id(self,base):return base+'-t%d'%self.d['tries'].get(base,0)
 def retry(self,base,error):
  n=self.d['tries'].get(base,0)+1;self.d['tries'][base]=n;self.d['last_error']=str(error)[:300]
  if n>=TASK_TRIES:raise RuntimeError('ChatGPT không trả được kết quả dùng được cho bước '+base+': '+str(error)[:300])
 def step(self,s):
  w=self.w;d=self.d
  w.post_command(None)  # the Studio tab runs no pipeline of its own for this project
  if d['stage']=='fetch':
   from .studio_workflow import engine_up,start_transcript_engine
   if not engine_up():return self.wait('engine',start_transcript_engine(w.j,w.clock()))
   d['transcript']=fetch_transcript(w.c['studio_youtube_url'],w.c.get('studio_language','vi'));d['stage']='plan';self.save()
  if d['stage']=='plan':
   tid=self.task_id('plan');got=self.tasks(s,[{'id':tid,'title':'Dàn ý Aprilynne','prompt':plan_prompt(d['transcript'],self.style())}])
   r=(got or {}).get(tid) or {}
   if r.get('status')=='done':
    try:
     d['plan'],d['sections']=accept_plan(r.get('text'),d['transcript']);d['stage']='write';d['round']=0
     if d.get('source')=='script':
      for x in d['sections']:x['text']=x['source']
      d['stage']='review'
     self.save()
    except (ValueError,KeyError,TypeError) as e:self.retry('plan',e);return self.wait('plan:retry','Dàn ý chưa hợp lệ, hỏi lại ChatGPT')
   elif r.get('status')=='error':self.retry('plan',r.get('error'));return self.wait('plan:retry','Lập dàn ý lỗi, hỏi lại')
   else:return self.wait('plan','Đang lập dàn ý Aprilynne và chia phần')
  secs=d['sections'];n=len(secs)
  def tidy():
   # Editorial notes never stay in the narration: moved to the notes for the editor.
   texts,notes=script_clean.strip_notes([x['text'] for x in secs])
   for x,t in zip(secs,texts):x['text']=t
   have={(n_['part'],n_['note']) for n_ in d.get('notes') or []}
   d['notes']=(d.get('notes') or [])+[n_ for n_ in notes if (n_['part'],n_['note']) not in have]
  if d['stage']=='write':
   # The task list stays the same for the whole try (changing it while tabs work would block new hand-outs).
   wt=d.get('write_try',0)
   if d.get('write_todo_try')!=wt:d['write_todo']=[x['id'] for x in secs if not x['text']];d['write_todo_try']=wt;self.save()
   tasks=[{'id':'w%d-%s'%(wt,x['id']),'title':x['title'],'prompt':write_prompt(x,i,n,d['plan'],self.style(),secs)} for i,x in enumerate(secs) if x['id'] in d['write_todo']]
   if tasks:
    got=self.tasks(s,tasks)
    if got is None:return self.wait('write:busy','Chờ tab ChatGPT rảnh')
    for i,x in enumerate(secs):
     r=got.get('w%d-%s'%(d.get('write_try',0),x['id'])) or {}
     if r.get('status')=='done' and str(r.get('text') or '').strip():x['text']=str(r['text']).strip()
    if any(not x['text'] for x in secs):
     bad=(self.lanes or {}).get('studio_failed_items')
     if bad:d['write_try']=d.get('write_try',0)+1;self.retry('write',str(bad))
     done=sum(1 for x in secs if x['text'])
     return self.wait('write:%d'%done,'Đang viết theo dàn ý %d/%d phần'%(done,n),studio_rewrite_done=done,studio_rewrite_total=n)
   tidy();d['stage']='edit' if d.get('source')!='script' else 'review';self.save()
  if d['stage']=='edit':
   if 'edit_issues' not in d:d['edit_issues']=script_clean.check([x['text'] for x in secs]);self.save()
   tasks=[{'id':'ed-%s'%x['id'],'title':'Biên tập liền mạch '+x['title'],'prompt':edit_prompt(x,i,n,d['plan'],self.style(),secs,d['edit_issues'])} for i,x in enumerate(secs)]
   got=self.tasks(s,tasks)
   if got is None:return self.wait('edit:busy','Chờ tab ChatGPT rảnh')
   done=[i for i,x in enumerate(secs) if (got.get('ed-%s'%x['id']) or {}).get('status')=='done']
   if len(done)<n and not (self.lanes or {}).get('studio_failed_items'):
    return self.wait('edit:%d'%len(done),'Đang biên tập liền mạch %d/%d hồi'%(len(done),n))
   for i in done:
    t=str(got['ed-%s'%secs[i]['id']].get('text') or '').strip()
    # An edit that grew the act a lot is not an edit: the written act is kept.
    if t and len(t)<=len(secs[i]['text'])*1.15:secs[i]['text']=t
   tidy();d['stage']='review';self.save()
  if d['stage']=='review':
   got_rows=d.setdefault('group_rows',{}).setdefault(str(d['round']),{})
   # A round started before the body was read in chunks keeps its single body review.
   groups=review_groups(secs,legacy='body' in got_rows)
   # The list keeps all groups for the round (a changing list would block handing out work); finished ones are only read.
   todo=[(g,ids) for g,ids in groups] if any(g not in got_rows for g,_ in groups) else []
   tasks=[{'id':self.task_id('rv%d-%s'%(d['round'],g)),'title':'Chấm Aprilynne vòng %d · %s'%(d['round']+1,g),
    'prompt':group_prompt(g,ids,d['plan'],secs,self.style(),d.get('last_error') if d['tries'].get('rv%d-%s'%(d['round'],g)) else '')} for g,ids in todo]
   if tasks:
    got=self.tasks(s,tasks)
    if got is None:return self.wait('review:busy','Chờ tab ChatGPT rảnh')
    for (g,ids),t in zip(todo,tasks):
     if g in got_rows:continue
     base='rv%d-%s'%(d['round'],g)
     # Any try of this group that came back is used; a tab error is re-sent by the lane round itself (same task, list unchanged).
     r=next((x for k,x in got.items() if str(k).startswith(base+'-t') and x.get('status')=='done'),None) or got.get(t['id']) or {}
     if r.get('status')=='error' and t['id'] in ((self.lanes or {}).get('studio_failed_items') or []):self.retry(base,r.get('error'));continue
     if r.get('status')!='done':continue
     try:
      got_rows[g]=accept_group(r.get('text'),ids,n)
      d.setdefault('group_facts',{}).setdefault(str(d['round']),{})[g]=accept_facts(r.get('text'),n)
     except (ValueError,KeyError,TypeError) as e:self.retry(base,e)
    self.save()
    if any(g not in got_rows for g,_ in groups):
     return self.wait('review:%d:%d'%(d['round'],len(got_rows)),'Đang chấm Aprilynne vòng %d/%d (%d/%d nhóm tiêu chí)'%(d['round']+1,ROUNDS,len(got_rows),len(groups)))
   rows,findings=combine(groups,got_rows)
   clean=script_clean.check([x['text'] for x in secs])
   rows=gate(rows,clean)
   facts=[f for g in (d.get('group_facts') or {}).get(str(d['round']),{}).values() for f in g][:10]
   d['rows']=rows;d['findings']=findings;d['clean']=clean;d['facts']=facts
   d.setdefault('history',[]).append({'round':d['round'],'passed':passed(rows),'total':total(rows),'clean':len(clean),'rows':rows,'findings':findings})
   rising=better(rows,d.get('best'),clean)
   if rising:d['best']={'passed':passed(rows),'total':total(rows),'texts':[x['text'] for x in secs],'rows':rows,'findings':findings,'clean':clean,'facts':facts,'round':d['round']}
   elif failing_parts(rows,findings,clean) and d['round']+1<ROUNDS:
    # This round's repairs made the script worse: the next repairs start again from the best version, never from a worse one.
    best=d['best']
    for x,t in zip(secs,best['texts']):x['text']=t
    rows,findings,clean,facts=best['rows'],best.get('findings') or [],best.get('clean') or [],best.get('facts') or []
    d['rows']=rows;d['findings']=findings;d['clean']=clean;d['facts']=facts
    d['note']='Vòng %d kém hơn bản tốt nhất (%d/%d): sửa tiếp từ bản tốt nhất'%(d['round']+1,best['passed'],len(CRITERIA))
   todo=failing_parts(rows,findings,clean)
   best=d['best']
   # Approved: at least PASS_NEEDED criteria at 8 or more AND a clean script (no repetition, no notes read aloud).
   if not todo or (best['passed']>=PASS_NEEDED and not best.get('clean')):
    # Approved: at least PASS_NEEDED criteria at 8 or more (the best version so far goes on to the scenes).
    for x,t in zip(secs,best['texts']):x['text']=t
    d['rows']=best['rows'];d['findings']=best.get('findings') or [];d['clean']=best.get('clean') or [];d['facts']=best.get('facts') or []
    d['stage']='done';d['note']='Duyệt: đạt %d/%d tiêu chí từ 8 điểm (cần %d) sau %d lượt sửa'%(best['passed'],len(CRITERIA)-len(VISUAL),PASS_NEEDED,d['round'])
   elif d['round']+1>=ROUNDS and not (rising and d['round']+1<MAX_ROUNDS):
    best=d['best']
    for x,t in zip(secs,best['texts']):x['text']=t
    d['rows']=best['rows'];d['findings']=best.get('findings') or [];d['clean']=best.get('clean') or [];d['facts']=best.get('facts') or []
    if best['passed']<PASS_AFTER_ROUNDS:
     self.save();raise RuntimeError('Kịch bản chưa đạt Aprilynne sau %d vòng: bản tốt nhất đạt %d/%d (cần %d). Xem điểm trong analysis/story.json.'%(ROUNDS,best['passed'],len(CRITERIA),PASS_AFTER_ROUNDS))
    if best.get('clean'):
     self.save();raise RuntimeError('Kịch bản đạt %d/12 tiêu chí nhưng còn lỗi liền mạch sau %d vòng: %s. Xem analysis/story.json (clean).'%(best['passed'],d['round']+1,', '.join('%s %d'%(k,v) for k,v in script_clean.summary(best['clean']).items())))
    d['stage']='done';d['note']='Hết %d vòng: dùng bản tốt nhất %d/%d'%(ROUNDS,best['passed'],len(CRITERIA))
   else:d['stage']='repair';d['repair']=todo
   self.save()
  if d['stage']=='repair':
   todo=d['repair'];tasks=[{'id':'fix%d-%s'%(d['round'],secs[i]['id']),'title':'Sửa '+secs[i]['title'],'prompt':repair_prompt(secs[i],i,n,d['plan'],self.style(),d['rows'],secs,d.get('findings') or [],d.get('clean') or [],d.get('facts') or [])} for i in todo]
   got=self.tasks(s,tasks)
   if got is None:return self.wait('repair:busy','Chờ tab ChatGPT rảnh')
   fixed=[i for i in todo if (got.get('fix%d-%s'%(d['round'],secs[i]['id'])) or {}).get('status')=='done']
   if len(fixed)<len(todo) and not (self.lanes or {}).get('studio_failed_items'):
    return self.wait('repair:%d:%d'%(d['round'],len(fixed)),'Đang sửa %d/%d phần chưa đạt (vòng %d/%d), đạt %d/%d tiêu chí'%(len(fixed),len(todo),d['round']+1,ROUNDS,passed(d['rows']),len(CRITERIA)))
   for i in fixed:
    t=str(got['fix%d-%s'%(d['round'],secs[i]['id'])].get('text') or '').strip()
    if t:secs[i]['text']=t
   tidy();d['round']+=1;d['stage']='review';self.save()
   return self.wait('repair:done:%d'%d['round'],'Đã sửa, chấm lại vòng %d/%d'%(d['round']+1,ROUNDS))
  if d['stage']=='done':
   script='\n\n'.join(x['text'] for x in secs)
   if str(s.get('script') or '').strip()!=script:
    if s.get('activeJob'):return self.wait('done:busy','Chờ Studio rảnh để lưu kịch bản')
    w.api.request(w.sid,'/script',{'script':script})
   w.j['aprilynne_done']=True;w.j['story_parts']=[{'title':x['title'],'content':x['text']} for x in secs];w.save()
   d['stage']='saved';self.save()
  return None
 def summary(self):
  d=self.d;rows=d.get('rows') or []
  return {'stage':d.get('stage'),'round':d.get('round'),'passed':passed(rows) if rows else None,'sections':len(d.get('sections') or []),'note':d.get('note')}
