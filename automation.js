/* Simple app controls; Windows results always come from the local Agent. */
let toastState=null,toastTimer=null,edgeDiagnosticReport=null;const shownAutomationErrors=new Set();
let pointerHeld=false,autoNotice='',autoError='',advancedInspection=null,advancedOpen=false;
let edgeProfiles=[],edgeProfile='',edgeProfilesLoaded=false,edgeInstalled=null,edgeRunning=false,edgeURL='https://chatgpt.com';
const appUI={edge:{windows:[],selected:null,checked:false,loading:false,error:'',task:null},chrome:{windows:[],selected:null,checked:false,loading:false,error:'',task:null},capcut:{windows:[],selected:null,checked:false,loading:false,error:'',task:null}};
let autoDraft={app:'chrome',url:'https://example.com',hwnd:'',selector:'{"auto_id":"1001","control_type":"Edit"}',actions:'[{"action":"WAIT","seconds":2,"timeout":5}]',project:'',chrome_path:'',capcut_path:''};
const seenOpenTasks=new Set();let discoveryStarted=false,lastAgentPid=null;
if(typeof document!=='undefined'){document.addEventListener('pointerdown',()=>pointerHeld=true);document.addEventListener('pointerup',()=>pointerHeld=false);document.addEventListener('pointercancel',()=>pointerHeld=false);}
function autoAttr(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
function keepAutoDraft(){for(const key of Object.keys(autoDraft)){const e=$('auto_'+key);if(e&&document.activeElement===e)autoDraft[key]=e.value;}}
function autoField(key){return $('auto_'+key)?.value??autoDraft[key];}
function appName(app){return app==='edge'?'Microsoft Edge':app==='chrome'?'Google Chrome':'CapCut'}
function sameWindow(a,b){return !!a&&!!b&&a.hwnd===b.hwnd&&a.pid===b.pid&&a.process_started===b.process_started}
function setAppWindows(app,windows){
 const u=appUI[app],old=u.selected;u.windows=windows.filter(w=>w.process===(app==='edge'?'msedge.exe':app+'.exe')&&(app!=='edge'||w.browser_profile===edgeProfile));u.checked=true;
 u.selected=old?u.windows.find(w=>sameWindow(w,old))||null:u.windows.length===1?u.windows[0]:null;
 if(old&&!u.selected)u.error='Cửa sổ đã đóng hoặc thay đổi. Vui lòng chọn lại.';
}
function selectAppWindow(app,value){const u=appUI[app];u.selected=u.windows.find(w=>String(w.hwnd)===String(value))||null;u.error='';const select=$('auto_window_'+app);if(select)select.blur();render()}
async function refreshAppWindows(app,quiet=false){
 const u=appUI[app];if(u.loading)return;u.loading=true;u.error='';if(!quiet)render();
 try{const r=await api('/api/automation',{command:'test',kind:'find',app,...(app==='edge'?{browser_profile:edgeProfile}:{})});if(!r.success)throw Error(r.error||'Không đọc được cửa sổ');setAppWindows(app,r.result.windows||[])}catch(e){u.error=e.message;u.selected=null;u.checked=false}finally{u.loading=false;render()}
}
async function agentCommand(command,extra={}){
 keepAutoDraft();autoError='';
 try{const r=await api('/api/automation',{command,...extra});if(r.task_id)autoNotice='Đã nhận yêu cầu. Theo dõi tiến trình bên dưới.';if(r.action)advancedInspection=r;await refresh();return r}catch(e){autoError=e.message;render();return null}
}
async function openApplication(app){
 if(app==='edge'&&!edgeProfile){appUI.edge.error='Chọn Edge Profile trước.';render();return}
 const u=appUI[app];u.error='';u.loading=true;render();
 try{const r=await agentCommand('submit',{actions:[{action:'OPEN_APP',target_app:app,timeout:app==='edge'?25:30,...(app==='edge'?{browser_profile:edgeProfile}:{})}]});if(r)u.task=r.task_id;else u.error=autoError}finally{u.loading=false;render()}
}
async function runAppTest(app,project=null){
 const u=appUI[app];if(u.loading)return;await refreshAppWindows(app,true);
 if(!u.selected){u.error=u.windows.length?'Hãy chọn một cửa sổ trong danh sách trước khi chạy.':'Chưa có cửa sổ. Bấm Mở '+appName(app)+' trước.';render();return}
 const target={...u.selected,target_app:app};
 const r=await agentCommand('test',{kind:app==='edge'?'edge_workflow':app==='chrome'?'chrome_workflow':'capcut_workflow',app,hwnd:target.hwnd,context:target,url:app==='edge'?edgeURL:autoField('url'),project,...(app==='edge'?{browser_profile:edgeProfile}:{})});if(r)u.task=r.task_id;
}
async function stopEverything(){autoError='';try{await api('/api/queue',{action:'stop_all'});autoNotice='Đã dừng toàn bộ công việc. Tiến trình đã hoàn thành vẫn được giữ.';await refresh()}catch(e){autoError=e.message;render()}}
async function customAgentActions(){try{await agentCommand('submit',{actions:JSON.parse(autoField('actions'))})}catch(e){autoError=e.message;render()}}
async function customElementAction(){try{await agentCommand('submit',{actions:[{action:'FIND_ELEMENT',target_app:autoField('app'),hwnd:Number(autoField('hwnd'))||undefined,selector:JSON.parse(autoField('selector'))}]})}catch(e){autoError=e.message;render()}}
async function queueAgentWorkflow(){const project=autoField('project');if(!project){autoError='Chọn dự án trước khi thêm vào hàng đợi.';render();return}await runAppTest(autoField('app'),project)}
function humanAction(action){return {STUDIO_READY:'Kiểm tra đúng Studio/ChatGPT',STUDIO_ANALYZE:'Phân tích cấu trúc',STUDIO_SCENES:'Phân cảnh từng phần',OPEN_APP:'Mở ứng dụng',WAIT_WINDOW:'Chờ cửa sổ',FIND_WINDOW:'Chọn cửa sổ',FOCUS_WINDOW:'Đưa cửa sổ lên trước',OPEN_URL:'Mở trang kiểm tra',WAIT_PAGE:'Chờ trang hiển thị',SCREENSHOT:'Chụp ảnh',STOP:'Dừng công việc',TYPE_TEXT:'Nhập văn bản kiểm tra',READ_ELEMENT:'Đọc kết quả',WAIT:'Chờ',ERROR:'Có lỗi'}[action]||'Xử lý thao tác'}
function humanError(error){if(!error)return '';if(/HWND|PID|Cửa sổ đích không còn|Cửa sổ không thuộc/.test(error))return 'Cửa sổ đã đóng hoặc thay đổi. Nhấn nút làm mới và chọn lại cửa sổ.';if(/Có nhiều cửa sổ/.test(error))return 'Có nhiều cửa sổ đang mở. Chọn đúng cửa sổ trong danh sách.';if(/focus/.test(error))return 'Chưa đưa được cửa sổ lên trước. Thử chọn lại cửa sổ rồi chạy kiểm tra.';return error}
function taskApp(t){return t?.context?.target_app||t?.target_app||t?.actions?.find(a=>a.target_app)?.target_app}
function renderAgentStatus(){
 const a=state.automation||{},online=a.online&&a.windows;
 $('windowsAgentStatus').textContent='Windows Agent: '+(online?'Đã kết nối':'Mất kết nối');
 $('windowsAgentPanel').innerHTML=`<b>Windows Agent: ${online?'🟢 Đã kết nối':'🔴 Mất kết nối'}</b>${a.error?`<p class="agent-error">${esc(a.error)}</p>`:''}<p>${online?'Sẵn sàng nhận công việc.':'Bấm Khởi động Agent để kết nối lại.'}</p><button class="btn" onclick="agentCommand('start_agent')">Khởi động Agent</button> <button class="btn" onclick="agentCommand('stop_agent')">Dừng Agent</button>`;
}
function syncAppUI(){
 const a=state.automation||{};
 if(a.online&&a.pid!==lastAgentPid){lastAgentPid=a.pid;discoveryStarted=false}
 if(a.online&&a.windows&&!discoveryStarted){discoveryStarted=true;Promise.resolve().then(()=>{refreshAppWindows('chrome',true);refreshAppWindows('capcut',true);refreshEdgeProfiles(true)})}
 for(const t of a.tasks||[]){if(t.status==='completed'&&t.actions.length===1&&t.actions[0].action==='OPEN_APP'&&!seenOpenTasks.has(t.id)){seenOpenTasks.add(t.id);const app=taskApp(t);if(appUI[app])Promise.resolve().then(()=>refreshAppWindows(app,true))}}
}
function appIcon(app){if(app==='edge')return '<span style="font-size:32px;color:#087fc0">◉</span>';return app==='chrome'?'<span class="chrome-logo"><i></i></span>':'<span class="capcut-logo">⋈</span>'}
function appCard(app){
 const u=appUI[app],online=Boolean(state.automation?.online&&state.automation?.windows),busy=u.loading;
 const selected=u.selected,options=u.windows.map(w=>`<option value="${w.hwnd}" ${sameWindow(selected,w)?'selected':''}>${esc(w.title)}</option>`).join('');
 const title=appName(app),badge=u.loading?'Đang kiểm tra…':u.checked?(u.windows.length?'Đang mở':'Chưa mở'):'Chưa kiểm tra';
 return `<article class="app-control-card"><div class="app-card-title">${appIcon(app)}<h2>${title}</h2><span class="agent-pill ${u.checked&&u.windows.length?'good':''}">${esc(badge)}</span></div>
 <section class="app-step"><span class="step-number">1</span><div><b>Mở ứng dụng</b><p>Khởi động ${title} nếu chưa mở.</p></div><button class="btn" ${!online||busy?'disabled':''} onclick="openApplication('${app}')">▶ Mở ${app==='chrome'?'Chrome':'CapCut'}</button></section>
 <section class="app-step window-step"><span class="step-number">2</span><div><b>Chọn cửa sổ</b><p>Chọn cửa sổ ${app==='chrome'?'Chrome':'CapCut'} cần kiểm tra.</p><div class="window-picker"><select id="auto_window_${app}" aria-label="Cửa sổ ${title}" onchange="selectAppWindow('${app}',this.value)" ${!online||busy?'disabled':''}><option value="">${u.loading?'Đang tìm cửa sổ…':u.windows.length?'Chọn cửa sổ…':'Chưa có cửa sổ'}</option>${options}</select><button class="btn refresh-window" title="Làm mới danh sách cửa sổ" ${!online||busy?'disabled':''} onclick="refreshAppWindows('${app}')">↻</button></div><p class="${selected?'selection-ok':'muted'}">${selected?'✓ Đã chọn cửa sổ':u.windows.length>1?'Có nhiều cửa sổ — hãy chọn một cửa sổ.':'Bấm làm mới sau khi mở ứng dụng.'}</p></div></section>
 <section class="app-step test-step"><span class="step-number">3</span><div><b>Chạy kiểm tra</b><p>${app==='chrome'?'Mở trang web kiểm tra trong cửa sổ đã chọn.':'Đưa cửa sổ lên trước và chụp ảnh.'}</p>${app==='chrome'?`<input id="auto_url" aria-label="Địa chỉ trang kiểm tra" value="${autoAttr(autoDraft.url)}" oninput="autoDraft.url=this.value">`:'<div class="app-test-spacer"></div>'}</div><button class="btn primary run-test" ${!online||busy?'disabled':''} onclick="runAppTest('${app}')">▶ Chạy kiểm tra ${app==='chrome'?'Chrome':'CapCut'}</button></section></article>`;
}
function progressHTML(task){
 if(!task)return '<h3>Tiến trình hiện tại</h3><p class="muted">Chọn ứng dụng và bấm Chạy kiểm tra để bắt đầu.</p>';
 const labels=taskApp(task)==='edge'?['Mở Edge / xác minh profile','Chọn cửa sổ','Mở trang','Chụp ảnh']:taskApp(task)==='chrome'?['Mở Chrome','Chọn cửa sổ','Mở trang','Chụp ảnh']:['Mở CapCut','Chọn cửa sổ','Đưa lên trước','Chụp ảnh'];
 const groups=['chrome','edge'].includes(taskApp(task))?[['OPEN_APP'],['WAIT_WINDOW','FIND_WINDOW','FOCUS_WINDOW'],['OPEN_URL','WAIT_PAGE'],['SCREENSHOT']]:[['OPEN_APP'],['WAIT_WINDOW','FIND_WINDOW'],['FOCUS_WINDOW'],['SCREENSHOT']];
 const done=task.results.filter(r=>r.success).map(r=>r.action),failed=['failed','needs_review','timeout'].includes(task.status),percent=Math.round(100*task.next_action/task.actions.length);
 const status=task.status==='completed'?'Đã thực hiện xong':failed?'Cần xử lý':task.status==='running'?'Đang kiểm tra '+(taskApp(task)==='edge'?'Edge':taskApp(task)==='chrome'?'Chrome':'CapCut'):({paused:'Đã tạm dừng',stopped:'Đã dừng',waiting:'Đang chờ',held:'Chờ chạy từ hàng đợi'}[task.status]||'Chờ xử lý');
 return `<div class="progress-title"><h3>Tiến trình hiện tại</h3><span class="agent-pill ${failed?'bad':task.status==='completed'?'good':''}">${esc(status)}</span></div><div class="app-workflow">${groups.map((group,i)=>{const complete=group.every(name=>!task.actions.some(a=>a.action===name)||done.includes(name))&&group.some(name=>done.includes(name));return `<div class="workflow-item ${complete?'done':group.includes(task.current_action)&&task.status==='running'?'active':''}"><span>${complete?'✓':i+1}</span><b>${labels[i]}</b></div>`}).join('')}</div><div class="app-progress"><i style="width:${percent}%"></i></div><p>${task.status==='running'?esc(humanAction(task.current_action))+'…':esc(status)} · ${percent}%</p>${failed?`<div class="agent-error">${esc(humanError(task.error))}</div>`:''}`;
}
function automationHTML(){
 syncAppUI();const a=state.automation||{},online=a.online&&a.windows,tasks=[...(a.tasks||[])].reverse(),current=tasks.find(t=>t.id===a.current_task)||tasks[0],logs=a.logs||[];
 const options=state.projects.map(p=>`<option value="${autoAttr(p.id)}" ${autoDraft.project===p.id?'selected':''}>${esc(p.name)} · ${esc(p.browser||'chrome')} / ${esc(p.browser_profile||'Default')}</option>`).join('');
 return `<section class="application-controls"><div class="application-heading"><div><h1>Điều khiển ứng dụng</h1><p>Chọn ứng dụng và chạy kiểm tra trong 3 bước</p></div><span class="agent-pill ${online?'good':'bad'}">● Windows Agent: ${online?'Đã kết nối':'Mất kết nối'}</span><button class="btn stop-everything" onclick="stopEverything()">■ DỪNG TẤT CẢ</button></div>${!online?`<div class="agent-error">${esc(a.error||'Agent chưa sẵn sàng.')} <button class="btn" onclick="agentCommand('start_agent')">Khởi động Agent</button></div>`:''}${automationToastHTML()}<div class="app-card-grid">${appCard('chrome')}${appCard('capcut')}${edgeCard()}</div><section class="card app-progress-card">${progressHTML(current)}</section>
 <div class="app-bottom-grid"><section class="card"><h3>Kết quả gần nhất</h3>${['chrome','capcut','edge'].map(app=>{const t=tasks.find(t=>taskApp(t)===app);const shot=t?.results?.filter(r=>r.result?.screenshot).at(-1)?.result?.screenshot;return `<div class="recent-app">${appIcon(app)}<b>${app==='edge'?'Edge':app==='chrome'?'Chrome':'CapCut'}</b><span>${!t?'Chưa kiểm tra':t.status==='completed'?'✓ Đã thực hiện xong':t.status==='running'?'Đang thực hiện':esc(humanError(t.error)||'Chưa hoàn tất')}</span>${shot?`<a class="btn" href="/api/automation/screenshot/${autoAttr(shot)}" target="_blank" rel="noopener">Xem ảnh</a>`:''}</div>`}).join('')}<p class="muted">Mở ảnh để kiểm tra nội dung thực tế của cửa sổ.</p></section><section class="card"><h3>Hoạt động gần đây</h3>${logs.slice(0,5).map(l=>`<div class="activity-row"><time>${esc(new Date(l.timestamp*1000).toLocaleTimeString('vi-VN'))}</time><span>${esc(humanAction(l.action))}${l.result==='completed'?' — Hoàn tất':l.error?' — '+esc(humanError(l.error)):''}</span></div>`).join('')||'<p class="muted">Chưa có hoạt động.</p>'}</section></div>
 <details class="card app-advanced" ${advancedOpen?'open':''} ontoggle="advancedOpen=this.open"><summary>Cài đặt nâng cao</summary><div class="advanced-body"><h3>Hàng đợi dự án</h3><select id="auto_app" onchange="autoDraft.app=this.value"><option value="chrome" ${autoDraft.app==='chrome'?'selected':''}>Chrome</option><option value="edge" ${autoDraft.app==='edge'?'selected':''}>Edge</option><option value="capcut" ${autoDraft.app==='capcut'?'selected':''}>CapCut</option></select><select id="auto_project" onchange="autoDraft.project=this.value"><option value="">Chọn dự án…</option>${options}</select><button class="btn" onclick="saveProjectBrowser()">Lưu trình duyệt/profile cho dự án</button><button class="btn" onclick="queueAgentWorkflow()">Đưa kiểm tra vào hàng đợi dự án</button><p class="muted">Sau khi gắn workflow cho dự án, bấm Chạy tất cả tại Hàng đợi.</p>
 <h3>Danh tính Agent đang chạy</h3><pre>${esc(JSON.stringify(a.agent_identity||{},null,2))}</pre><h3>Kiểm tra API Windows thật</h3><pre>${esc(JSON.stringify(a.windows_api_contract||{},null,2))}</pre><h3>Công cụ kỹ thuật</h3><button class="btn" onclick="agentCommand('ping')">Kiểm tra kết nối Agent</button><button class="btn" onclick="agentCommand('test',{kind:'processes'})">Danh sách process</button><button class="btn" onclick="agentCommand('test',{kind:'safe_input'})">Test nhập văn bản an toàn</button><button class="btn" onclick="agentCommand('stop_agent')">Dừng Agent</button><p>PID: ${esc(a.pid??'—')} · Uptime: ${duration(a.uptime||0)}</p><label>HWND cho công cụ UIA</label><input id="auto_hwnd" value="${autoAttr(autoDraft.hwnd)}" oninput="autoDraft.hwnd=this.value"><label>Selector UIA</label><input id="auto_selector" value="${autoAttr(autoDraft.selector)}" oninput="autoDraft.selector=this.value"><button class="btn" onclick="customElementAction()">Đọc element</button><label>Chuỗi Action JSON</label><textarea id="auto_actions" oninput="autoDraft.actions=this.value">${esc(autoDraft.actions)}</textarea><button class="btn" onclick="customAgentActions()">Gửi Action</button>
 <h3>Đường dẫn ứng dụng</h3><label>Chrome.exe</label><input id="auto_chrome_path" value="${autoAttr(autoDraft.chrome_path)}" oninput="autoDraft.chrome_path=this.value"><label>CapCut.exe</label><input id="auto_capcut_path" value="${autoAttr(autoDraft.capcut_path)}" oninput="autoDraft.capcut_path=this.value"><button class="btn" onclick="agentCommand('settings',{chrome_path:autoField('chrome_path'),capcut_path:autoField('capcut_path')})">Lưu và khởi động lại Agent</button>
 ${advancedInspection?`<pre>${esc(JSON.stringify(advancedInspection,null,2))}</pre>`:''}<h3>Chi tiết task</h3>${tasks.slice(0,20).map(t=>`<details><summary>${esc(t.id)} · ${esc(t.status)}</summary><pre>${esc(JSON.stringify(t,null,2))}</pre>${['paused','failed','stopped'].includes(t.status)&&!t.project?`<button class="btn" onclick="agentCommand('resume',{task_id:'${autoAttr(t.id)}'})">Tiếp tục checkpoint</button>`:''}</details>`).join('')}${edgeDiagnosticReport?`<h3>Chẩn đoán Edge</h3><button class="btn" onclick="copyEdgeDiagnostics()">Sao chép chẩn đoán</button><pre>${esc(JSON.stringify(edgeDiagnosticReport,null,2))}</pre>`:''}<h3>Nhật ký kỹ thuật</h3><pre>${esc(JSON.stringify(logs.slice(0,100),null,2))}</pre></div></details></section>`;
}

async function refreshEdgeProfiles(quiet=false){
 if(!quiet)autoError='';
 try{const r=await api('/api/automation',{command:'edge_profiles'});if(!r.success)throw Error(r.error||'Không đọc được profile Edge');edgeProfiles=r.result.profiles||[];edgeInstalled=r.result.installed;edgeRunning=Boolean(r.result.running);edgeProfilesLoaded=true;if(!edgeProfiles.some(p=>p.directory===edgeProfile)){edgeProfile=edgeProfiles[0]?.directory||'';appUI.edge.selected=null}await refreshAppWindows('edge',true)}catch(e){appUI.edge.error=e.message}render();
}
function chooseEdgeProfile(value){edgeProfile=value;appUI.edge.selected=null;appUI.edge.windows=[];appUI.edge.checked=false;$('auto_edge_profile')?.blur();refreshAppWindows('edge',true)}
async function saveProjectBrowser(){const project=autoField('project'),browser=autoField('app');if(!project||!['chrome','edge'].includes(browser)){autoError='Chọn dự án và Chrome hoặc Edge.';render();return}const r=await agentCommand('project_browser',{project,browser,browser_profile:browser==='edge'?edgeProfile:'Default'});if(r){autoNotice='Đã lưu trình duyệt/profile cho dự án.';render()}}
function edgeCard(){
 const u=appUI.edge,online=Boolean(state.automation?.online&&state.automation?.windows),busy=u.loading;
 const profiles=edgeProfiles.map(p=>`<option value="${autoAttr(p.directory)}" ${p.directory===edgeProfile?'selected':''}>${esc(p.directory)} — ${esc(p.name)}</option>`).join('');
 const windows=u.windows.map(w=>`<option value="${w.hwnd}" ${sameWindow(w,u.selected)?'selected':''}>${esc(w.title)}</option>`).join('');
 const task=[...(state.automation?.tasks||[])].reverse().find(t=>taskApp(t)==='edge');
 const opening=['running','waiting'].includes(task?.status)&&task?.actions?.length===1&&task.actions[0].action==='OPEN_APP';
 const failure=['failed','timeout','needs_review'].includes(task?.status)?task.error:'';
 return `<article class="app-control-card edge-card"><div class="app-card-title">${appIcon('edge')}<h2>Microsoft Edge</h2><span class="agent-pill ${u.windows.length?'good':''}">${edgeInstalled===false?'Chưa cài Edge':u.windows.length?'Sẵn sàng':edgeRunning?'Chưa xác minh':'Chưa mở'}</span></div>
 <section class="app-step"><span class="step-number">1</span><div><b>Mở ứng dụng</b><p ${failure?'role="alert"':''}>${failure?esc('Tác vụ '+task.id.slice(0,8)+': '+failure):'Mở profile đã chọn bên dưới.'}</p></div><button class="btn" ${!online||busy||!edgeProfile||opening?'disabled':''} onclick="openApplication('edge')">${opening?'Đang xác minh…':failure?'↻ Thử lại Edge':'▶ Mở Edge'}</button></section>
 <section class="app-step window-step"><span class="step-number">2</span><div><b>Chọn Edge Profile</b><p>Dùng phiên đăng nhập có sẵn.</p><div class="window-picker"><select id="auto_edge_profile" ${!online||busy||opening?'disabled':''} onchange="chooseEdgeProfile(this.value)"><option value="">Chọn Edge Profile</option>${profiles}</select><button class="btn refresh-window" title="Làm mới profile" onclick="refreshEdgeProfiles()" ${!online?'disabled':''}>↻</button></div><p class="muted">${opening?'Đang đọc profile từ Windows, tối đa 25 giây.':u.selected?'✓ Đã xác minh profile và cửa sổ':edgeProfilesLoaded&&!edgeProfiles.length?'Không tìm thấy profile. Mở Edge rồi làm mới.':'Chọn profile rồi bấm Mở Edge.'} <button class="edge-diagnostic-link" ${!online?'disabled':''} onclick="diagnoseEdge()">Chẩn đoán Edge</button></p></div></section>
 <section class="app-step test-step"><span class="step-number">3</span><div><b>Chọn cửa sổ và kiểm tra</b><div class="window-picker"><select id="auto_window_edge" onchange="selectAppWindow('edge',this.value)" ${!online||busy?'disabled':''}><option value="">${opening?'Đang xác minh cửa sổ…':'Chọn cửa sổ Edge…'}</option>${windows}</select><button class="btn refresh-window" title="Làm mới cửa sổ" onclick="refreshAppWindows('edge')" ${!online?'disabled':''}>↻</button></div><input id="auto_edge_url" aria-label="URL kiểm tra Edge" value="${autoAttr(edgeURL)}" oninput="edgeURL=this.value"></div><button class="btn primary run-test" ${!online||busy||!u.selected||opening?'disabled':''} onclick="runAppTest('edge')">▶ Chạy kiểm tra Edge</button></section>
 </article>`;
}

function automationToastHTML(){
 let message=autoError||autoNotice,kind=autoError?'error':'info';autoError='';autoNotice='';
 for(const [app,u] of Object.entries(appUI))if(u.error&&!shownAutomationErrors.has(app+u.error)){shownAutomationErrors.add(app+u.error);if(!message){message=u.error;kind='error'}}
 const newestByApp=new Map();for(const t of [...(state.automation?.tasks||[])].reverse()){const app=taskApp(t);if(!newestByApp.has(app))newestByApp.set(app,t)}
 const failed=[...newestByApp.values()].find(t=>['failed','timeout','needs_review'].includes(t.status)&&t.error);
 if(failed&&!shownAutomationErrors.has(failed.id)){shownAutomationErrors.add(failed.id);if(!message){message=failed.error;kind='error'}}
 if(message){
  toastState={message,kind};if(toastTimer)clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>{toastState=null;toastTimer=null;if(typeof render==='function')render()},4000);
 }
 if(!toastState)return '';
 return `<div class="automation-toast ${toastState.kind}" role="status"><span>${esc(toastState.message)}</span><button aria-label="Đóng thông báo" onclick="dismissAutomationToast()">×</button></div>`;
}
function dismissAutomationToast(){if(toastTimer)clearTimeout(toastTimer);toastTimer=null;toastState=null;render()}
async function diagnoseEdge(){
 if(!edgeProfile){autoError='Chọn profile trước khi chẩn đoán.';render();return}
 autoNotice='Đang đọc chẩn đoán Edge, không thao tác vào trình duyệt.';render();
 const r=await agentCommand('edge_diagnostics',{browser_profile:edgeProfile});
 if(r){edgeDiagnosticReport=r.success?r.result:{...r.result,error:r.error,status:r.status};advancedOpen=true;autoNotice='Đã có chẩn đoán. Mở Cài đặt nâng cao → Sao chép chẩn đoán.';render()}
}
async function copyEdgeDiagnostics(){
 try{await navigator.clipboard.writeText(JSON.stringify(edgeDiagnosticReport,null,2));autoNotice='Đã sao chép chẩn đoán Edge.'}catch(e){autoError='Không sao chép được. Chọn nội dung chẩn đoán bên dưới để sao chép.'}render();
}
