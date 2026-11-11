/* WinControl chat and jobs view. Execution stays in the existing Agent and TaskStore. */
let winControlBusy=false;
let winControlReply='';
let winControlLastTask='';
let winControlTab='chat';
let winControlDraft='';
let winControlFocus=false;
let winControlCaret=[0,0];
let winControlPending=null;
let winControlSent='';

function winControlTasks(){
 return (state.automation?.tasks||[]).filter(t=>t.current_stage==='WinControl'||t.context?.wincontrol_task).slice().reverse();
}
function winControlSelected(){
 const tasks=winControlTasks();
 const running=tasks.find(t=>t.status==='running'||t.status==='waiting');
 if(winControlLastTask==='new')return running||null;
 return tasks.find(t=>t.id===winControlLastTask)||running||null;
}
function winControlDetails(value){
 if(value===null||value===undefined)return '';
 if(typeof value==='string')return value;
 if(value.path)return String(value.path);
 if(value.window?.title)return String(value.window.title);
 if(value.decision?.summary)return String(value.decision.summary);
 try{return JSON.stringify(value).slice(0,500)}catch{return String(value)}
}
function winControlMessages(task){
 if(!task)return [];
 const messages=[];
 const command=task.context?.wincontrol_command||task.command||'';
 if(command)messages.push({kind:'user',title:'Bạn',text:command});
 for(const row of task.results||[]){
  if(row.action==='OBSERVE_CHATGPT'||row.action==='SEND_CHATGPT')continue;
  const decision=row.result?.decision;
  if(row.action==='WINCONTROL_DECIDE'&&decision){
   if(decision.status==='invalid'){messages.push({kind:'tool',title:'WinControl',text:'Phản hồi ChatGPT chưa đúng định dạng; đã yêu cầu ChatGPT trả lời lại.'});continue}
   messages.push({kind:'assistant',title:'ChatGPT',text:decision.summary||'ChatGPT đã phân tích trạng thái.'});
   if(decision.status==='continue'&&decision.actions?.[0])messages.push({kind:'tool',title:'Bước tiếp theo',text:winControlActionName(decision.actions[0])});
   continue;
  }
  const detail=row.error||winControlDetails(row.result);
  if(detail)messages.push({kind:row.success?'tool':'error',title:(row.success?'Kết quả · ':'Lỗi · ')+(row.action||'công cụ'),text:detail});
 }
 const last=messages[messages.length-1];
 if(task.status==='completed'&&last?.kind!=='assistant')messages.push({kind:'assistant',title:'ChatGPT',text:'Nhiệm vụ đã hoàn tất.'});
 if(task.status==='needs_review')messages.push({kind:'error',title:'Cần kiểm tra',text:task.error||'WinControl dừng an toàn tại checkpoint.'});
 if(task.status==='failed')messages.push({kind:'error',title:'Lỗi',text:task.error||'Nhiệm vụ gặp lỗi.'});
 return messages;
}
function winControlActionName(a){
 const names={OPEN_APP:'Mở ứng dụng',WAIT_WINDOW:'Chờ cửa sổ',FOCUS_WINDOW:'Đưa cửa sổ lên trước',TYPE_TEXT:'Nhập văn bản',HOTKEY:'Bấm phím tắt',CLICK:'Bấm',SCREENSHOT:'Chụp màn hình',LIST_WINDOWS:'Liệt kê cửa sổ',LIST_PROCESSES:'Liệt kê tiến trình',ENSURE_TEMP_DIR:'Chuẩn bị thư mục tạm',VERIFY_FILE:'Kiểm tra tệp',OPEN_FILE:'Mở tệp',MAN_STATUS:'Kiểm tra MAN, Studio, Extension',WAIT:'Chờ',READ_ELEMENT:'Đọc phần tử',FIND_ELEMENT:'Tìm phần tử',WAIT_ELEMENT:'Chờ phần tử'};
 const extra=a.target_app?' · '+a.target_app:a.keys?' · '+a.keys:a.path?' · '+a.path:'';
 return (names[a.action]||a.action)+extra;
}
function winControlStatus(task){
 if(winControlBusy)return 'Đang gửi…';
 if(!task)return 'ChatGPT điều khiển · Windows Agent thực thi';
 const step={OBSERVE_CHATGPT:'Đang đọc ChatGPT',SEND_CHATGPT:'Đang gửi cho ChatGPT',WINCONTROL_DECIDE:'ChatGPT đang trả lời…'}[task.current_action]||(task.current_action?'Đang thực hiện: '+winControlActionName({action:task.current_action}):'Đang chờ');
 return {running:step,waiting:'Đang xếp hàng',completed:'Hoàn tất',needs_review:'Dừng an toàn · cần kiểm tra',failed:'Lỗi',stopped:'Đã dừng'}[task.status]||task.status;
}
function winControlNew(){winControlLastTask='new';winControlReply='';winControlTab='chat';render()}
function winControlChatHTML(task){
 const messages=winControlMessages(task);
 if(winControlSent&&!messages.length)messages.push({kind:'user',title:'Bạn',text:winControlSent});
 const empty=!messages.length;
 const transcript=messages.map(m=>`<article class="wc-message ${m.kind}"><small>${esc(m.title)}</small><div>${esc(m.text)}</div></article>`).join('');
 const prompt=empty?`<div class="wc-welcome"><div class="wc-mark">W</div><h1>WinControl</h1><p>Giao một nhiệm vụ bằng tiếng Việt. ChatGPT sẽ quyết định từng bước và Agent sẽ xác minh kết quả.</p></div>`:'';
 return `<section class="wc-chat-view${empty?" empty":""}">${prompt}<div class="wc-transcript" id="wc_transcript">${transcript}</div><form class="wc-composer" onsubmit="winControlSubmit(event)"><textarea id="win_command" maxlength="4000" rows="1" placeholder="Gửi lệnh cho WinControl" aria-label="Lệnh WinControl" ${winControlBusy?'disabled':''}></textarea><div class="wc-compose-actions"><span>${esc(winControlStatus(task))}</span><div>${task&&task.status!=='running'?`<button class="wc-stop" type="button" onclick="winControlNew()">Nhiệm vụ mới</button>`:''}${task?.status==='running'?`<button class="wc-stop" type="button" onclick="winControlStop()">Dừng an toàn</button>`:['needs_review','paused','stopped'].includes(task?.status)?`<button class="wc-stop" type="button" onclick="winControlResume()">Tiếp tục</button>`:''}<button class="wc-send" type="submit" ${winControlBusy?'disabled':''} aria-label="Gửi nhiệm vụ">${winControlBusy?'…':'↑'}</button></div></div></form>${winControlReply?`<div class="wc-live-result" aria-live="polite">${esc(winControlReply)}</div>`:''}</section>`;
}
function winControlJobsHTML(){
 const tasks=winControlTasks();
 if(!tasks.length)return '<div class="wc-empty-jobs">Chưa có công việc. Bắt đầu bằng một lệnh trong tab Trò chuyện.</div>';
 return `<div class="wc-job-list">${tasks.map(t=>`<button class="wc-job ${t.id===winControlLastTask?'selected':''}" onclick="winControlSelectTask('${esc(t.id)}')"><span class="wc-job-status ${esc(t.status)}"></span><span><b>${esc(t.context?.wincontrol_command||t.command||'Nhiệm vụ WinControl')}</b><small>${esc(t.status)} · ${esc(t.current_action||'Chưa có bước')} · ${Number(t.results?.length||0)} bước đã ghi nhận</small>${t.error?`<small class="wc-job-error">${esc(t.error)}</small>`:''}</span></button>`).join('')}</div>`;
}
function winControlHTML(){
 const task=winControlSelected();
 return `<main class="wc-shell"><header class="wc-top"><div><button class="wc-back" type="button" onclick="goPage('Studio Automation')" aria-label="Quay lại Điều phối">←</button><b>WinControl</b><small class="${state.automation?.online?'online':'offline'}">Windows Agent ${state.automation?.online?'đang hoạt động':'ngoại tuyến'}</small></div><nav class="wc-tabs" aria-label="WinControl"><button class="${winControlTab==='chat'?'active':''}" onclick="winControlTab='chat';render()">Trò chuyện</button><button class="${winControlTab==='jobs'?'active':''}" onclick="winControlTab='jobs';render()">Công việc ${winControlTasks().length?`<i>${winControlTasks().length}</i>`:''}</button></nav><button class="wc-refresh" onclick="winControlSubmitStatus()" aria-label="Làm mới">↻</button></header>${winControlTab==='chat'?winControlChatHTML(task):`<section class="wc-jobs-view"><h1>Công việc</h1><p>Theo dõi nhiệm vụ và checkpoint của Agent hiện có.</p>${winControlJobsHTML()}</section>`}</main>`;
}
function winControlSelectTask(id){winControlLastTask=id;winControlTab='chat';winControlReply='';render()}
function winControlFormatState(s){
 const projects=s.projects||[],queue=new Map((s.queue||[]).map(p=>[p.id,p]));
 const failures=(s.automation?.tasks||[]).filter(t=>['failed','needs_review','timeout'].includes(t.status));
 const lines=[`Windows Agent: ${s.automation?.online?'online':'offline'}`,`Dự án MAN: ${projects.length}`];
 for(const p of projects){const q=queue.get(p.id)||{};lines.push(`${p.name} [${p.id}] — ${q.status||p.status||'chưa có trạng thái'}`)}
 lines.push(`Tác vụ lỗi/cần xem xét: ${failures.length}`);
 for(const t of failures.slice(-8))lines.push(`${t.id} — ${t.status} — ${t.current_action||''}${t.error?' — '+t.error:''}`);
 return lines.join('\n');
}
async function winControlSubmitStatus(){
 try{const s=await api('/api/state');state=s;winControlReply=winControlFormatState(s);render()}
 catch(e){winControlReply='Không đọc được MAN/Agent: '+e.message;render()}
}
async function winControlSubmit(event){
 event?.preventDefault?.();const field=document.getElementById('win_command');const command=String(field?.value||winControlDraft||'').trim();if(!command||winControlBusy)return;
 // One id per typed command: a double click or a resent request returns the same task instead of a second one.
 const requestId=winControlPending?.text===command?winControlPending.id:'req-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,10);
 winControlPending={text:command,id:requestId};
 winControlBusy=true;winControlReply='';winControlTab='chat';winControlSent=command;render();
 try{
  const result=await api('/api/automation',{command:'wincontrol',text:command,request_id:requestId});
  // The redraw copies the box back into the draft, so the box itself is emptied too once the task exists.
  if(result.task_id){winControlLastTask=result.task_id;winControlDraft='';winControlPending=null;const box=document.getElementById('win_command');if(box)box.value=''}
  else winControlReply=[result.summary,result.message].filter(Boolean).join('\n')||JSON.stringify(result);
  state=await api('/api/state');
 }catch(e){winControlReply='Chưa thực thi: '+e.message}
 finally{winControlBusy=false;winControlSent='';render()}
}
async function winControlResume(){
 // Continues from the checkpoint; the Agent refuses when the stopped step is not safe to repeat (e.g. typing).
 const task=winControlSelected();if(!task)return;
 try{await api('/api/automation',{command:'resume',task_id:task.id});winControlReply='Đã tiếp tục từ checkpoint.';state=await api('/api/state')}
 catch(e){winControlReply='Không tiếp tục được: '+e.message}
 render();
}
async function winControlStop(){
 const task=winControlTasks().find(t=>t.id===winControlLastTask)||winControlSelected();
 if(!task||task.status!=='running'){winControlReply='Không có nhiệm vụ WinControl đang chạy để dừng.';render();return}
 try{await api('/api/automation',{command:'wincontrol_cancel',task_id:task.id});winControlReply='Đã yêu cầu dừng an toàn; checkpoint được giữ lại.';state=await api('/api/state')}
 catch(e){winControlReply='Dừng an toàn thất bại: '+e.message}
 render();
}
(function installWinControlPage(){
 if(typeof UI_PAGES!=='undefined'&&!UI_PAGES.includes('WinControl'))UI_PAGES.push('WinControl');
 // The visible navigation is the shell's header nav; the old document.querySelector('aside') sidebar is hidden by ui_shell.js.
 const nav=document.querySelector('.neo-main-nav')||document.querySelector('aside');
 if(nav&&!nav.querySelector('[data-page="WinControl"]')){const button=document.createElement('button');button.dataset.page='WinControl';button.textContent='WinControl';button.onclick=()=>goPage('WinControl');nav.appendChild(button)}
 if(typeof render!=='function')return;
 const base=render;
 render=function(){
  // The page refreshes every 2 s; keep what the user is typing, the caret and focus across the redraw.
  const old=document.getElementById('win_command');
  if(old){winControlDraft=old.value;winControlFocus=document.activeElement===old;winControlCaret=[old.selectionStart,old.selectionEnd]}
  base();
  if(page!=='WinControl'){
   // MAN v0.2.25 (manager_ui.js) hides the old header and redraws its own top bar on every render: add the entry there.
   const pills=document.querySelector('.mg-pills');
   if(pills&&!pills.parentElement.querySelector('.wc-entry')){const entry=document.createElement('button');entry.type='button';entry.className='wc-entry';entry.dataset.page='WinControl';entry.textContent='WinControl';entry.title='Giao nhiệm vụ cho WinControl';entry.onclick=()=>goPage('WinControl');pills.after(entry)}
   return;
  }
  for(const id of ['mainToolbar','mainStats','mainNotice','studioPanel','extensionPanel','windowsAgentPanel','dashboard']){const el=document.getElementById(id);if(el)el.hidden=true}
  const extra=document.getElementById('extra');if(!extra)return;
  const html=winControlHTML();
  if(extra.dataset.wc!==html||extra.hidden||!extra.querySelector('.wc-shell')){extra.hidden=false;extra.innerHTML=html;extra.dataset.wc=html;
   const transcript=document.getElementById('wc_transcript');if(transcript)transcript.scrollTop=transcript.scrollHeight}
  const field=document.getElementById('win_command');
  if(field){
   if(field.value!==winControlDraft)field.value=winControlDraft;
   if(!field.dataset.bound){field.dataset.bound='1';field.addEventListener('input',()=>{winControlDraft=field.value});field.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();field.form.requestSubmit()}})}
   if(winControlFocus&&document.activeElement!==field&&!winControlBusy){field.focus();try{field.setSelectionRange(...winControlCaret)}catch{}}
  }
  document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page==='WinControl'))};
})();
