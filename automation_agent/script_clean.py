"""Machine checks of a written script, exact and free (no ChatGPT): what made the Thái sư script tiring to hear.
- Editorial notes read aloud ([CẦN KIỂM TRA], "tư liệu đầu vào"…) are taken out of the narration into notes.
- One greeting, one "let's go", the call to subscribe only at the start and the end.
- No sentence or paragraph told twice, catchphrases at most twice, hedging at most once,
  at most one hanging question at the end of a section and not a question every few lines.
Each problem names its section so the repair knows where to work."""
import re,unicodedata

# Read aloud by mistake: notes for the editor, never for the viewer.
NOTE_TAG=re.compile(r'\[\s*(?:CẦN KIỂM TRA|CAN KIEM TRA|KIỂM TRA|GHI CHÚ|TODO|NOTE)[^\]]*\]',re.I)
NOTE_PHRASES=[r'theo tư liệu (?:được )?cung cấp',r'tư liệu đầu vào',r'phần tư liệu này',r'nguồn đầu vào',r'(?:đã )?được cung cấp trong tư liệu']
HEDGES=[r'đây là cách em (?:ví von|diễn giải|hình dung)',r'không phải lời (?:nói|thoại) (?:được )?ghi chép',r'em không tự thêm',r'em không (?:dám )?khẳng định',r'chỉ là (?:cách )?(?:em )?(?:suy đoán|suy diễn)']
GREETING=r'chào mừng (?:quý |các )?(?:bạn|bác|vị)'
LETS_GO=r'vào video (?:thôi|nào)'
CALL=r'(?:bấm|nhấn|ấn) (?:nút )?(?:theo dõi|đăng ký|đăng kí|like|thích)|đăng ký kênh|subscribe'
# The channel's own words: fine once or twice, tiring when every section has them.
CATCHPHRASES=['level max','canh hẹ','knockout','các bác thử nghĩ xem','công là công, tội là tội','công là công tội là tội']
ADDRESS=r'^(?:nhưng |và |thế nhưng |vâng, )?các bác ạ\b'
LIMITS={'catchphrase':2,'hedge':1,'questions_per_1000':1.0,'ending_questions':1}

def _flat(t):return re.sub(r'\s+',' ',unicodedata.normalize('NFC',t)).strip().lower()
def _sentences(t):return [s.strip() for s in re.split(r'(?<=[.!?…])\s+',t) if s.strip()]
def _paragraphs(t):return [p.strip() for p in re.split(r'\n\s*\n',t) if p.strip()]
def _count(pattern,t):return len(re.findall(pattern,t,re.I))

def strip_notes(texts):
 """Take editorial notes out of the narration. Returns the cleaned texts and the notes (section, sentence) for the editor."""
 out=[];notes=[]
 for i,t in enumerate(texts):
  for s in _sentences(t):
   if NOTE_TAG.search(s):notes.append({'part':i+1,'note':NOTE_TAG.sub('',s).strip()[:400]})
  c=NOTE_TAG.sub('',t)
  c=re.sub(r'[ \t]+([.,!?…])',r'\1',c);c=re.sub(r'[ \t]{2,}',' ',c)
  out.append(c.strip())
 return out,notes

def _shingles(t,k=5):
 w=re.findall(r'\w+',_flat(t))
 return {' '.join(w[i:i+k]) for i in range(max(0,len(w)-k+1))}

def check(texts):
 """Problems of the whole script: [{'kind','part','count','limit','detail'}]. Empty means clean."""
 n=len(texts);issues=[]
 def add(kind,part,count,limit,detail):issues.append({'kind':kind,'part':part,'count':count,'limit':limit,'detail':detail[:300]})
 for i,t in enumerate(texts):
  for p in [NOTE_TAG.pattern]+NOTE_PHRASES:
   c=_count(p,t)
   if c:add('note',i+1,c,0,'Ghi chú biên tập trong lời đọc: '+(re.search(p,t,re.I).group(0)))
 # Greeting and "let's go": once, in the opening; the call to subscribe only in the first and last section.
 for kind,p,label in (('greeting',GREETING,'lời chào'),('lets_go',LETS_GO,'"Vào video thôi"')):
  where=[i for i,t in enumerate(texts) if re.search(p,t,re.I)]
  total=sum(_count(p,t) for t in texts)
  if total>1:
   for i in where[1:] or where:add(kind,i+1,total,1,'Có %d lần %s; chỉ giữ một lần ở mở đầu'%(total,label))
 for i,t in enumerate(texts):
  if 0<i<n-1 and re.search(CALL,t,re.I):add('call',i+1,_count(CALL,t),0,'Kêu gọi đăng ký/theo dõi ở giữa video; chỉ ở đầu và cuối')
 # The same sentence twice anywhere.
 seen={}
 for i,t in enumerate(texts):
  for s in _sentences(t):
   f=_flat(s)
   if len(f)<40 or f.startswith('['):continue
   if f in seen and seen[f]!=(i+1):add('duplicate',i+1,2,1,'Câu lặp lại (đã có ở phần %d): "%s"'%(seen[f],s[:120]))
   elif f in seen:add('duplicate',i+1,2,1,'Câu lặp lại trong cùng phần: "%s"'%s[:120])
   else:seen[f]=i+1
 # The same passage told twice in other words (an anecdote told again, a summary of what was just said).
 paras=[(i,p,_shingles(p)) for i,t in enumerate(texts) for p in _paragraphs(t) if len(p)>=200 and not p.lstrip().startswith('[')]
 for a in range(len(paras)):
  for b in range(a+1,len(paras)):
   x,y=paras[a][2],paras[b][2]
   if x and y and len(x&y)/min(len(x),len(y))>=0.45:
    add('retold',paras[b][0]+1,2,1,'Đoạn kể lại ý đã có ở phần %d: "%s"'%(paras[a][0]+1,paras[b][1][:120]))
 # Catchphrases and hedging over the whole video.
 whole='\n'.join(texts)
 for phrase in CATCHPHRASES:
  c=whole.lower().count(phrase)
  if c>LIMITS['catchphrase']:
   for i in [i for i,t in enumerate(texts) if phrase in t.lower()][LIMITS['catchphrase']:]:add('catchphrase',i+1,c,LIMITS['catchphrase'],'Câu cửa miệng "%s" dùng %d lần (tối đa %d)'%(phrase,c,LIMITS['catchphrase']))
 hedges=[(i,m.group(0)) for i,t in enumerate(texts) for p in HEDGES for m in re.finditer(p,t,re.I)]
 if len(hedges)>LIMITS['hedge']:
  for i,h in hedges[LIMITS['hedge']:]:add('hedge',i+1,len(hedges),LIMITS['hedge'],'Câu rào đón lặp: "%s"; gom về một câu ở đầu video'%h)
 # Every section opening with the same call to the viewers.
 opens=[i for i,t in enumerate(texts) if re.search(ADDRESS,_flat(t))]
 if len(opens)>max(2,n//4):
  for i in opens[max(2,n//4):]:add('opening',i+1,len(opens),max(2,n//4),'Phần mở lại bằng "Các bác ạ" như một tập phim mới; nối thẳng từ phần trước')
 # Questions: one hanging question at most at the end of a section, and not one every few lines.
 for i,t in enumerate(texts):
  tail=_sentences(t)[-3:]
  q=sum(1 for s in tail if s.endswith('?'))
  if q>LIMITS['ending_questions'] and i<n-1:add('questions',i+1,q,LIMITS['ending_questions'],'Kết phần bằng %d câu hỏi liền nhau; giữ tối đa một câu hỏi treo'%q)
 qs=whole.count('?');limit=max(6,round(len(whole)/1000*LIMITS['questions_per_1000']))
 if qs>limit:
  dense=sorted(range(n),key=lambda i:-texts[i].count('?')/max(1,len(texts[i])))[:max(1,n//4)]
  for i in sorted(dense):add('questions',i+1,qs,limit,'Cả bài có %d câu hỏi tu từ (tối đa khoảng %d): đổi bớt thành câu kể'%(qs,limit))
 return issues

def summary(issues):
 """Counts per kind, for the report."""
 out={}
 for x in issues:out[x['kind']]=out.get(x['kind'],0)+1
 return out
