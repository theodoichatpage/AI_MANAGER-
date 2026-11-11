/* WinControl chat and jobs view. Execution stays in the existing Agent and TaskStore. */
let winControlBusy=false;
let winControlReply='';
let winControlLastTask='';
let winControlTab='chat';

function winControlTasks(){
 return (state.automation?.tasks||[]).filter(t=>t.current_stage==='WinControl'||t.context?.wincontrol_task).slice().reverse();
}
function winControlSelected(){
 const tasks=winControlTasks();
 return tasks.find(t=>t.id===winControlLastTask)||tasks.find(t=>t.status==='running')||tasks[0]||null;
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
   messages.push({kind:'assistant',title:'ChatGPT',text:decision.summary||'ChatGPT đã phân tích trạng thái.'});
   if(decision.status==='continue'&&decision.actions?.[0])messages.push({kind:'tool',title:'Hành động được chọn',text:decision.actions[0].action});
   continue;
  }
  const detail=row.error||winControlDetails(row.result);
  if(detail)messages.push({kind:row.success?'tool':'error',title:row.action||'Kết quả công cụ',text:detail});
 }
 const last=messages[messages.length-1];
 if(task.status==='completed'&&last?.kind!=='assistant')messages.push({kind:'assistant',title:'ChatGPT',text:'Nhiệm vụ đã hoàn tất.'});
 if(task.status==='needs_review')messages.push({kind:'error',title:'Cần kiểm tra',text:task.error||'WinControl dừng an toàn tại checkpoint.'});
 if(task.status==='failed')messages.push({kind:'error',title:'Lỗi',text:task.error||'Nhiệm vụ gặp lỗi.'});
 return messages;
}
function winControlChatHTML(task){
 const messages=winControlMessages(task);
 const empty=!messages.length;
 const transcript=messages.map(m=>`<article class="wc-message ${m.kind}"><small>${esc(m.title)}</small><div>${esc(m.text)}</div></article>`).join('');
 const prompt=empty?`<div class="wc-welcome"><div class="wc-mark">W</div><h1>WinControl</h1><p>Giao một nhiệm vụ bằng tiếng Việt. ChatGPT sẽ quyết định từng bước và Agent sẽ xác minh kết quả.</p></div>`:'';
 return `<section class="wc-chat-view">${prompt}<div class="wc-transcript" id="wc_transcript">${transcript}</div><form class="wc-composer" onsubmit="winControlSubmit(event)"><textarea id="win_command" maxlength="4000" rows="1" placeholder="Gửi lệnh cho WinControl" aria-label="Lệnh WinControl" ${winControlBusy?'disabled':''}></textarea><div class="wc-compose-actions"><span>${winControlBusy?'Đang xử lý…':task?`${esc(task.status)} · ${esc(task.current_action||'Đang chờ')}`:'ChatGPT điều khiển · Windows Agent hiện có'}</span><div>${task?.status==='running'?`<button class="wc-stop" type="button" onclick="winControlStop()">Dừng an toàn</button>`:''}<button class="wc-send" type="submit" ${winControlBusy?'disabled':''} aria-label="Gửi nhiệm vụ">${winControlBusy?'…':'↑'}</button></div></div></form>${winControlReply?`<div class="wc-live-result" aria-live="polite">${esc(winControlReply)}</div>`:''}</section>`;
}
function winControlJobsHTML(){
 const tasks=winControlTasks();
 if(!tasks.length)return '<div class="wc-empty-jobs">Chưa có công việc. Bắt đầu bằng một lệnh trong tab Trò chuyện.</div>';
 return `<div class="wc-job-list">${tasks.map(t=>`<button class="wc-job ${t.id===winControlLastTask?'selected':''}" onclick="winControlSelectTask('${esc(t.id)}')"><span class="wc-job-status ${esc(t.status)}"></span><span><b>${esc(t.context?.wincontrol_command||t.command||'Nhiệm vụ WinControl')}</b><small>${esc(t.status)} · ${esc(t.current_action||'Chưa có bước')} · ${Number(t.results?.length||0)} bước đã ghi nhận</small>${t.error?`<small class="wc-job-error">${esc(t.error)}</small>`:''}</span></button>`).join('')}</div>`;
}
function winControlHTML(){
 const task=winControlSelected();
 return `<main class="wc-shell"><header class="wc-top"><div><b>WinControl</b><small class="${state.automation?.online?'online':'offline'}">Windows Agent ${state.automation?.online?'đang hoạt động':'ngoại tuyến'}</small></div><nav class="wc-tabs" aria-label="WinControl"><button class="${winControlTab==='chat'?'active':''}" onclick="winControlTab='chat';render()">Trò chuyện</button><button class="${winControlTab==='jobs'?'active':''}" onclick="winControlTab='jobs';render()">Công việc ${winControlTasks().length?`<i>${winControlTasks().length}</i>`:''}</button></nav><button class="wc-refresh" onclick="winControlSubmitStatus()" aria-label="Làm mới">↻</button></header>${winControlTab==='chat'?winControlChatHTML(task):`<section class="wc-jobs-view"><h1>Công việc</h1><p>Theo dõi nhiệm vụ và checkpoint của Agent hiện có.</p>${winControlJobsHTML()}</section>`}</main>`;
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
 event?.preventDefault?.();const field=document.getElementById('win_command');const command=String(field?.value||'').trim();if(!command||winControlBusy)return;
 winControlBusy=true;winControlReply='';winControlTab='chat';render();
 try{
  const result=await api('/api/automation',{command:'wincontrol',text:command});
  if(result.task_id)winControlLastTask=result.task_id;
  else winControlReply=[result.summary,result.message].filter(Boolean).join('\n')||JSON.stringify(result);
  state=await api('/api/state');
 }catch(e){winControlReply='Chưa thực thi: '+e.message}
 finally{winControlBusy=false;render()}
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
 const nav=document.querySelector('aside')||document.querySelector('.neo-main-nav');
 if(nav&&!nav.querySelector('[data-page="WinControl"]')){const button=document.createElement('button');button.dataset.page='WinControl';button.textContent='WinControl';button.onclick=()=>goPage('WinControl');nav.appendChild(button)}
 if(typeof render!=='function')return;
 const base=render;
 render=function(){base();if(page!=='WinControl')return;for(const id of ['mainToolbar','mainStats','mainNotice','studioPanel','extensionPanel','windowsAgentPanel','dashboard']){const el=document.getElementById(id);if(el)el.hidden=true}const extra=document.getElementById('extra');if(extra){extra.hidden=false;extra.innerHTML=winControlHTML();const transcript=document.getElementById('wc_transcript');if(transcript)transcript.scrollTop=transcript.scrollHeight;const field=document.getElementById('win_command');if(field&&!winControlBusy)field.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();field.form.requestSubmit()}})}document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page==='WinControl'))};
})();
