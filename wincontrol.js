/* WinControl command surface. All production control is delegated to MAN's existing APIs. */
let winControlBusy=false;
let winControlReply='';
let winControlLastTask='';

function winControlHTML(){
 const a=state.automation||{},tasks=[...(a.tasks||[])].reverse();
 const current=tasks.find(t=>t.id===winControlLastTask)||tasks.find(t=>t.status==='running')||tasks.find(t=>t.id===a.current_task)||null;
 const results=current?.results||[];
 const timeline=results.slice(-8).map((r,i)=>`<li><b>${esc(r.action||'Bước')}</b><span>${esc(r.success?'Hoàn tất':r.status||'Đang xử lý')}</span>${r.error?`<small class="wc-error">${esc(r.error)}</small>`:''}</li>`).join('');
 const err=current?.error||current?.results?.slice(-1)[0]?.error||'';
 let resultText=winControlReply;
 if(current?.current_stage==='WinControl'&&current.status==='completed'){const lastDecision=[...results].reverse().find(r=>r.action==='WINCONTROL_DECIDE'&&r.success);resultText=lastDecision?.result?.decision?.summary||'ChatGPT confirmed completion.'}
 else if(current?.current_stage==='WinControl'&&current.status==='needs_review')resultText='WinControl stopped for review: '+(err||'The result needs verification.');
 else if(current?.current_stage==='WinControl'&&current.status==='failed')resultText='WinControl task failed: '+(err||'No error details.');
 return `<div class="wc-page"><section class="card wc-header"><div><h1>WinControl</h1><p>Nhận lệnh Windows qua Agent hiện có; MAN tiếp tục sở hữu hàng đợi sản xuất.</p></div><div class="wc-agent ${a.online?'online':'offline'}"><b>Agent ${a.online?'Online':'Offline'}</b><small>${a.pid?'PID '+esc(a.pid):esc(a.error||'Chưa có tiến trình')}</small></div></section>
 <section class="card wc-command"><form onsubmit="winControlSubmit(event)"><label for="win_command">Lệnh tiếng Việt</label><textarea id="win_command" maxlength="4000" placeholder="Ví dụ: Kiểm tra MAN, các dự án và tác vụ đang lỗi."></textarea><div class="wc-buttons"><button class="btn primary" type="submit" ${winControlBusy?'disabled':''}>${winControlBusy?'Đang xử lý…':'Gửi nhiệm vụ'}</button><button class="btn danger" type="button" onclick="winControlStop()" ${!(current&&current.current_stage==='WinControl'&&current.status==='running')?'disabled':''}>Dừng an toàn · giữ checkpoint</button><button class="btn" type="button" onclick="winControlSubmitStatus()">Làm mới trạng thái</button></div></form><p class="muted">Lệnh Windows được gửi qua Agent API. Lệnh Studio phải đi qua MAN; không gửi thẳng tới Extension/ChatGPT.</p></section>
 <section class="wc-grid"><article class="card"><h2>Nhiệm vụ hiện tại</h2>${current?`<p><b>${esc(current.current_stage||'Automation')}</b> · ${esc(current.status)} · bước ${Number(current.next_action||0)+1}/${current.actions?.length||0}</p><p>${esc(current.current_action||'Đang chờ bước tiếp theo')}</p><ul class="wc-timeline">${timeline||'<li>Chưa có bước được ghi nhận.</li>'}</ul>${err?`<div class="wc-error-box"><b>Lỗi</b><p>${esc(err)}</p></div>`:''}`:'<p class="muted">Agent chưa có nhiệm vụ đang chạy.</p>'}</article>
 <article class="card"><h2>Kết quả</h2><div id="win_result" class="wc-result" aria-live="polite">${resultText?esc(resultText):'Type a request for ChatGPT to operate Windows or inspect MAN.'}</div><small>Trạng thái được làm mới cùng dữ liệu MAN; thao tác quan trọng được lưu trong TaskStore.</small></article></section></div>`;
}

function winControlFormatState(s,projectId){
 const projects=(s.projects||[]).filter(p=>!projectId||p.id===projectId);
 const q=new Map((s.queue||[]).map(p=>[p.id,p]));
 const tasks=(s.automation?.tasks||[]).filter(t=>!projectId||t.project===projectId||t.current_project===projectId);
 const failures=tasks.filter(t=>['failed','needs_review','timeout'].includes(t.status));
 const lines=[`Windows Agent: ${s.automation?.online?'online':'offline'}${s.automation?.pid?' · PID '+s.automation.pid:''}`,`Dự án: ${projects.length}`];
 for(const p of projects){const row=q.get(p.id)||{};lines.push(`• ${p.name} [${p.id}] — ${row.status||p.status||'chưa có trạng thái hàng đợi'}${row.current_stage?' · '+row.current_stage:''}`)}
 lines.push(`Tác vụ Agent liên quan: ${tasks.length}; lỗi/cần xem xét: ${failures.length}`);
 for(const t of tasks.slice(-8)){lines.push(`• ${t.id} — ${t.status} — ${t.current_action||t.current_stage||'chưa chạy'}${t.error?' — '+t.error:''}`)}
 if(s.automation?.error)lines.push(`Lỗi Agent: ${s.automation.error}`);
 return lines.join('\n');
}

async function winControlSubmitStatus(){
 try{winControlBusy=true;const s=await api('/api/state');state=s;winControlReply=winControlFormatState(s);const el=document.getElementById('win_result');if(el)el.textContent=winControlReply;render()}catch(e){winControlReply='Không đọc được MAN/Agent: '+e.message;const el=document.getElementById('win_result');if(el)el.textContent=winControlReply}finally{winControlBusy=false}
}
async function winControlSubmit(event){
 event?.preventDefault?.();const field=document.getElementById('win_command');const command=String(field?.value||'').trim();if(!command)return;
 winControlBusy=true;const box=document.getElementById('win_result');if(box)box.textContent='Planning with ChatGPT through the existing Chrome MCP and checking Agent/MAN state.';
 try{
  const result=await api('/api/automation',{command:'wincontrol',text:command});
  if(result.task_id){winControlLastTask=result.task_id;winControlReply=`Submitted Agent task ${result.task_id}; verifying its live result.`}
  else if(result.projects){const live=await api('/api/state');state=live;winControlReply=winControlFormatState(live);}
  else winControlReply=[result.summary,result.message].filter(Boolean).join('\n')||JSON.stringify(result,null,2);
  const live=await api('/api/state');state=live;
  if(box)box.textContent=winControlReply;else render();
 }catch(e){winControlReply='Not executed: '+e.message;if(box)box.textContent=winControlReply;else render()}
 finally{winControlBusy=false}
}
async function winControlStop(){
 const task=[...(state.automation?.tasks||[])].find(t=>t.id===winControlLastTask);
 if(!task||task.current_stage!=='WinControl'||task.status!=='running'){winControlReply='No active WinControl task to stop.';const el=document.getElementById('win_result');if(el)el.textContent=winControlReply;return}
 try{await api('/api/automation',{command:'wincontrol_cancel',task_id:task.id});winControlReply='Agent was asked to stop this WinControl task safely. Its checkpoint is retained; uncertain actions will not be retried.';await refresh()}catch(e){winControlReply='Safe stop failed: '+e.message}const el=document.getElementById('win_result');if(el)el.textContent=winControlReply
}

(function installWinControlPage(){
 if(typeof UI_PAGES==='undefined'||typeof goPage!=='function'||typeof render!=='function')return;
 if(!UI_PAGES.includes('WinControl'))UI_PAGES.push('WinControl');
 const nav=document.querySelector('aside')||document.querySelector('.neo-main-nav');
 if(nav&&!nav.querySelector('[data-page="WinControl"]')){
  const button=document.createElement('button');button.className='btn';button.dataset.page='WinControl';button.textContent='WinControl';button.setAttribute('aria-label','Mở giao diện WinControl');button.onclick=()=>goPage('WinControl');nav.appendChild(button);
 }
 const base=render;
 render=function(){if(document.activeElement?.id==='win_command')return;base();if(page!=='WinControl')return;
  for(const id of ['mainToolbar','mainStats','mainNotice','studioPanel','extensionPanel','windowsAgentPanel','dashboard']){const el=document.getElementById(id);if(el)el.hidden=true}
  const extra=document.getElementById('extra');if(extra){extra.hidden=false;extra.innerHTML=winControlHTML()}
  document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page==='WinControl'));
 };
})();
