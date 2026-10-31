/* Settings popup (gear, top right). Layout from the user's mockup, AI Manager's own style (14px text, 32px controls,
   black + lime). Two tabs: Kết nối, Dữ liệu. A connection that is not up shows "Đang chờ". */
let mgSet2={open:false,tab:'conn',sys:null,msg:'',err:'',timer:null,checked:false};
Object.assign(MG_ICONS,{
 x:'M6 6l12 12 M18 6 6 18',db:'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6 M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
 win:'M3 5l8-1v7H3z M13 4l8-1v8h-8z M3 13h8v7l-8-1z M13 13h8v8l-8-1z',
 chat:'M12 3a9 9 0 0 0-7.8 13.5L3 21l4.6-1.2A9 9 0 1 0 12 3z M8 10h8 M8 14h5',
 studio:'M4 4h16v16H4z M10 8.5v7l6-3.5z',pic:'M4 5h16v14H4z M4 16l5-5 4 4 3-3 4 4 M15 9.5a1.5 1.5 0 1 0 0-.01',
 cpu:'M7 7h10v10H7z M10 10h4v4h-4z M9 3v4 M15 3v4 M9 17v4 M15 17v4 M3 9h4 M3 15h4 M17 9h4 M17 15h4',
 ram:'M3 8h18v8H3z M7 8v8 M11 8v8 M15 8v8 M5 16v3 M19 16v3',disk:'M4 14h16v6H4z M6 14l2-9h8l2 9 M16 17h.01',
 folder:'M3 7h7l2 2h9v11H3z M3 7V5h7l2 2',log:'M6 3h9l4 4v14H6z M9 11h7 M9 15h7',
 refresh:'M20 12a8 8 0 1 1-2.3-5.7 M20 4v5h-5',puzzle:'M9 3h6v4a2 2 0 1 0 0 4v4h-4a2 2 0 1 0-4 0H3V9h4a2 2 0 1 0 0-4V3z',
 list:'M8 6h12 M8 12h12 M8 18h12 M4 6h.01 M4 12h.01 M4 18h.01',chip:'M9 9h6v6H9z M12 2v4 M12 18v4 M2 12h4 M18 12h4 M5 5l3 3 M16 16l3 3 M5 19l3-3 M16 8l3-3',
 bolt:'M13 2 4 14h7l-1 8 9-12h-7z'});
function mgOpenSettings(){mgSet2.open=true;mgSet2.msg='';mgSet2.err='';mgSysPoll();
 if(!mgSet2.checked&&typeof appCall==='function'){mgSet2.checked=true;appCall('update-check')}render()}
function mgCloseSettings(){mgSet2.open=false;clearTimeout(mgSet2.timer);render()}
function mgSysPoll(){clearTimeout(mgSet2.timer);if(!mgSet2.open)return;api('/api/app',{action:'system'}).then(r=>{mgSet2.sys=r;render()}).catch(()=>{}).finally(()=>{if(mgSet2.open)mgSet2.timer=setTimeout(mgSysPoll,5000)})}
async function mgAct(action,extra={},done){mgSet2.msg='';mgSet2.err='';render();try{const r=await api('/api/app',{action,...extra});mgSet2.msg=done?done(r):''}catch(e){mgSet2.err=e.message}render()}
function mgGB(n){return (n/1073741824).toFixed(n>1073741824*100?0:1)+' GB'}
function mgConnRow(icon,title,sub,on,stateText,detail,btn){return `<div class="mgs-row"><div class="mgs-ic">${mgSvg(icon)}</div><div class="mgs-t"><b>${title}</b><small>${sub}</small></div><div class="mgs-st"><span class="${on?'on':''}"><i></i>${esc(stateText)}</span><small>${esc(detail||'')}</small></div>${btn}</div>`}
function mgVerRow(icon,title,ver,tag,cls){return `<div class="mgs-row mgs-ver"><div class="mgs-ic">${mgSvg(icon)}</div><div class="mgs-t"><b>${title}</b></div><span class="mgs-v">${esc(ver?'v'+ver:'—')}</span><span class="mgs-tag ${cls||''}">${esc(tag)}</span></div>`}
function mgConnTab(){
 const a=state.automation||{},e=state.extension||{},cat=state.studio_catalog||{},ident=a.agent_identity||{},eu=state.extension_update||{},sys=mgSet2.sys,eng=sys&&sys.engine;
 const extOk=e.status==='responding'||Boolean(cat.chat_connected),extVer=e.version||eu.installed||'';
 const tools=typeof appTools!=='undefined'?appTools:{},u=tools.update,busy=tools.busy;
 const manTag=!u?['Chưa kiểm tra','']:!u.ok?['Không kiểm tra được','warn']:u.behind?['Có bản mới','warn']:['Mới nhất','ok'];
 const extTag=!eu.installed?['Đang tải','warn']:eu.latest&&eu.latest!==eu.installed?['Có bản mới','warn']:['Mới nhất','ok'];
 const agTag=!a.online?['Đang chờ','']:ident.version&&ident.version!==state.version?['Cần khởi động lại','warn']:['Mới nhất','ok'];
 const pct=(x,y)=>y?Math.min(100,Math.round(100*x/y)):0;
 const tile=(icon,label,value,p)=>`<div class="mgs-tile"><div class="mgs-tile-top"><div class="mgs-ic">${mgSvg(icon)}</div><div><div class="l">${label}</div><div class="v">${value}</div></div></div><div class="p"><i style="width:${p}%"></i></div></div>`;
 const upd=u&&u.ok&&u.behind&&!u.dirty
  ?`<button class="mg-btn primary wide" ${busy?'disabled':''} onclick="appCall('update-apply')">${mgSvg('refresh')} Cập nhật ngay (${u.behind} bản mới)</button>`
  :`<button class="mg-btn outline wide" ${busy?'disabled':''} onclick="mgUpdateCheck()">${mgSvg('refresh')} ${busy==='update-check'?'Đang kiểm tra…':'Kiểm tra cập nhật'}</button>`;
 return `<div class="mgs-grid">
 <section class="mg-card"><h2>${mgSvg('list')} Trạng thái kết nối</h2><p class="mgs-sub">Kiểm tra và quản lý các thành phần cần thiết</p>
 ${mgConnRow('win','Windows Agent','Điều khiển Windows, mở ứng dụng',a.online,a.online?'Đã kết nối':'Đang chờ',ident.version?'v'+ident.version:'',`<button class="mg-btn" onclick="agentCommand('start_agent')">Khởi động lại</button>`)}
 ${mgConnRow('chat','ChatGPT + Extension','Kết nối và gửi lệnh qua Extension',extOk,extOk?'Đã kết nối':'Đang chờ',extVer?'v'+extVer:'',`<button class="mg-btn" onclick="mgExtCheck()">Kiểm tra</button>`)}
 ${mgConnRow('studio','VIDEO IMAGE STUDIO','Kết nối với Studio',cat.studio_tab_open,cat.studio_tab_open?'Đã kết nối':'Đang chờ',cat.studio_tab_open?'Đang mở':'Chưa mở',`<button class="mg-btn" onclick="mgAct('open-studio',{},()=>'Đã mở Studio trong Edge')">Mở Studio</button>`)}
 ${mgConnRow('pic','Local Engine (tách ảnh)','Xử lý và tách ảnh',Boolean(eng),eng?'Đang chạy':sys?'Đang chờ':'Đang kiểm tra',eng&&eng.version?'v'+eng.version:'',`<button class="mg-btn" onclick="mgSysPoll()">Kiểm tra</button>`)}
 </section>
 <section class="mg-card"><h2>${mgSvg('chip')} Thông tin phiên bản</h2><p class="mgs-sub">Phiên bản hiện tại và kiểm tra cập nhật</p>
 ${mgVerRow('gear','AI Manager',state.version,...manTag)}${mgVerRow('puzzle','ChatGPT Extension',eu.installed||e.version,...extTag)}${mgVerRow('win','Windows Agent',ident.version,...agTag)}
 <div class="mgs-update">${upd}</div>
 ${u&&u.ok&&u.dirty?`<div class="mg-note">Có thay đổi chưa lưu trong thư mục AI Manager, chưa thể tự cập nhật.</div>`:''}
 </section>
 <section class="mg-card"><h2>${mgSvg('bolt')} Trạng thái hệ thống</h2><p class="mgs-sub">Tài nguyên và hoạt động</p><div class="mgs-tiles">
 ${tile('cpu','CPU',sys?Math.round(sys.cpu)+'%':'…',sys?sys.cpu:0)}${tile('ram','RAM',sys?mgGB(sys.ram_used)+' / '+mgGB(sys.ram_total):'…',sys?pct(sys.ram_used,sys.ram_total):0)}${tile('disk','Dung lượng ổ đĩa',sys?mgGB(sys.disk_used)+' / '+mgGB(sys.disk_total):'…',sys?pct(sys.disk_used,sys.disk_total):0)}
 </div></section>
 <section class="mg-card"><h2>Thao tác nhanh</h2><p class="mgs-sub">Các hành động thường dùng</p><div class="mgs-quick">
 <button class="mg-btn" onclick="mgAct('open-root')">${mgSvg('folder')} Mở thư mục dự án</button><button class="mg-btn" onclick="mgAct('open-backups')">${mgSvg('folder')} Mở thư mục backup</button>
 <button class="mg-btn" onclick="mgAct('open-logs')">${mgSvg('log')} Xem log hệ thống</button><button class="mg-btn danger" onclick="mgCleanTemp()">${mgSvg('trash')} Xóa dữ liệu tạm</button>
 </div></section></div>`;
}
function mgDataTab(){
 const t=typeof appTools!=='undefined'?appTools:{status:{}},st=t.status||{},b=t.busy,mb=n=>(n/1048576).toFixed(n>1048576*10?0:1)+' MB';
 const icon={ok:'✓',warn:'!',missing:'✕'};
 const progress=st.running?`<div class="mg-note">${st.kind==='backup'?'Đang sao lưu':'Đang khôi phục'}… ${st.done}/${st.total} tệp</div>`:st.error?`<div class="mg-note err">${esc(st.error)}</div>`:st.result?`<div class="mg-note ok">Đã khôi phục ${st.result.added.length} dự án${st.result.skipped.length?' · bỏ qua '+st.result.skipped.length+' dự án đã có':''}</div>`:'';
 const profiles=typeof edgeProfiles!=='undefined'?edgeProfiles:[];
 return `<div class="mgs-grid">
 <section class="mg-card"><h2>${mgSvg('folder')} Thư mục dự án</h2><p class="mgs-sub">Mỗi dự án có một thư mục riêng: kịch bản, phân cảnh, ảnh, ảnh tách</p>
 <div class="mgs-path">${esc((state.config||{}).root||'Chưa chọn')}</div><div class="mgs-btns"><button class="mg-btn" onclick="rootDialog.showModal()">Đổi thư mục</button><button class="mg-btn" onclick="mgAct('open-root')">${mgSvg('folder')} Mở thư mục</button></div></section>
 <section class="mg-card"><h2>${mgSvg('db')} Sao lưu và khôi phục</h2><p class="mgs-sub">Gói mọi dự án và cài đặt vào một tệp, dùng khi đổi máy. Khôi phục không ghi đè dự án đã có.</p>
 <div class="mgs-btns"><button class="mg-btn primary" ${b||st.running?'disabled':''} onclick="appCall('backup')">Sao lưu ngay</button><button class="mg-btn" onclick="mgAct('open-backups')">${mgSvg('folder')} Mở thư mục backup</button></div>${progress}
 <div class="mgs-btns"><select id="neo_mg_restore" class="mgs-select" onchange="appTools.restorePath=this.value;this.blur();render()"><option value="">Chọn bản sao lưu…</option>${(st.backups||[]).map(x=>`<option value="${autoAttr(x.path)}" ${t.restorePath===x.path?'selected':''}>${esc(x.name)} · ${mb(x.size)}</option>`).join('')}</select><button class="mg-btn" ${!t.restorePath||b||st.running?'disabled':''} onclick="appCall('restore',{path:appTools.restorePath})">Khôi phục</button></div></section>
 <section class="mg-card"><h2>${mgSvg('chat')} Hồ sơ Edge chạy ChatGPT</h2><p class="mgs-sub">Mỗi hồ sơ Edge đăng nhập ChatGPT là một tab chạy song song (máy có ${profiles.length} hồ sơ)</p>
 <div class="mgs-btns"><select id="neo_main_profile" class="mgs-select" onchange="uiChooseMainProfile(this.value)">${profiles.map(p=>`<option value="${autoAttr(p.directory)}" ${studioDraft.profile===p.directory?'selected':''}>${esc(p.name||p.directory)}</option>`).join('')||'<option>Đang đọc hồ sơ Edge…</option>'}</select><button class="mg-btn" onclick="refreshEdgeProfiles().then(render)">Đọc lại</button><button class="mg-btn" onclick="uiCloneProfile()">+ Tạo hồ sơ phụ</button></div>
 <details class="mgs-guide"><summary>Cài Extension cho hồ sơ mới</summary><ol><li><button class="mg-btn" onclick="api('/api/extension-update',{action:'open'})">Mở thư mục Extension</button></li><li>Trong Edge mở <code>edge://extensions</code>, bật Chế độ nhà phát triển.</li><li>Bấm Tải tiện ích đã giải nén, chọn thư mục ở bước 1, rồi đăng nhập chatgpt.com.</li></ol></details></section>
 <section class="mg-card"><h2>${mgSvg('win')} Ứng dụng trên máy</h2><p class="mgs-sub">Cài biểu tượng, tải bản cài cho máy mới, kiểm tra máy này</p>
 <div class="mgs-btns"><button class="mg-btn" ${b?'disabled':''} onclick="appCall('install')">Cài thành ứng dụng</button><a class="mg-btn" href="${autoAttr(state.download_url||'')}" target="_blank" rel="noopener">Tải bản cài v${esc(state.version||'')}</a><button class="mg-btn" ${b?'disabled':''} onclick="appCall('setup-check')">${b==='setup-check'?'Đang kiểm tra…':'Kiểm tra máy này'}</button></div>
 ${t.check?`<div class="mgs-check">${t.check.map(i=>`<div class="${i.state}"><span>${icon[i.state]}</span><div><b>${esc(i.label)}</b><small>${esc(i.detail)}</small>${i.fix&&i.state!=='ok'?`<small class="fix">→ ${esc(i.fix)}</small>`:''}</div></div>`).join('')}</div>`:''}
 ${t.msg?`<div class="mg-note ok">${esc(t.msg)}</div>`:''}</section></div>`;
}
function mgUpdateCheck(){appCall('update-check');api('/api/extension-update',{action:'check'}).then(refresh).catch(()=>{})}
function mgExtCheck(){mgSet2.msg='';mgSet2.err='';api('/api/extension-update',{action:'check'}).then(async()=>{await refresh();const e=state.extension||{},cat=state.studio_catalog||{};mgSet2.msg=e.status==='responding'||cat.chat_connected?'Extension đang phản hồi':'Chưa thấy Extension phản hồi. Mở Studio và một tab ChatGPT đã đăng nhập; máy mới cần cài Extension (tab Dữ liệu).';render()}).catch(e=>{mgSet2.err=e.message;render()})}
function mgCleanTemp(){if(!confirm('Xóa dữ liệu tạm?\n\nChỉ xóa ảnh chụp chẩn đoán và bộ nhớ đệm. Dự án, ảnh và thùng rác không bị đụng tới.'))return;mgAct('clean-temp',{},r=>'Đã xóa '+r.files+' tệp tạm ('+(r.freed/1048576).toFixed(1)+' MB)')}
function mgSettingsHTML(){
 if(!mgSet2.open)return '';
 const tab=(k,icon,label)=>`<button class="mgs-tab ${mgSet2.tab===k?'on':''}" onclick="mgSet2.tab='${k}';mgSet2.msg='';mgSet2.err='';render()">${mgSvg(icon)} ${label}</button>`;
 return `<div class="mgs-bg" onclick="if(event.target===this)mgCloseSettings()"><div class="mgs-modal">
 <div class="mgs-head"><div class="mgs-ic big">${mgSvg('gear')}</div><div><h1>Cài đặt</h1><p>Thiết lập và quản lý AI Manager</p></div><button class="mg-icon-btn" title="Đóng" onclick="mgCloseSettings()">${mgSvg('x')}</button></div>
 <div class="mgs-tabs">${tab('conn','link','Kết nối')}${tab('data','db','Dữ liệu')}</div>
 ${mgSet2.err?`<div class="mg-note err mgs-msg">${esc(mgSet2.err)}</div>`:mgSet2.msg?`<div class="mg-note ok mgs-msg">${esc(mgSet2.msg)}</div>`:''}
 ${mgSet2.tab==='data'?mgDataTab():mgConnTab()}</div></div>`;
}
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&mgSet2.open&&!document.querySelector('dialog[open]'))mgCloseSettings()});
