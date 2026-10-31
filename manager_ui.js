/* AI Manager main screen.
   Layout follows the user's mockup: header, "Quản lý dự án" on the left, "Tạo / Chỉnh sửa dự án" on the right,
   progress of the selected project below. Everything else (scenes, images, separation details) belongs to Studio.
   Settings (gear) open a popup: manager_settings.js. */
let mgSel='',mgForms={},mgSearch='',mgMenu='',mgBusy='',mgMsg='',mgErr='',mgProfilesAsked=false;
const MG_ICONS={
 doc:'M7 3h7l5 5v13H7z M14 3v5h5 M10 12h6 M10 16h6',
 link:'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1 M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
 wand:'M4 20 15 9 M14 4v2 M14 12v2 M10 8h2 M18 8h2 M17 5l1-1 M17 11l1 1',
 image:'M4 5h16v14H4z M4 16l5-5 4 4 3-3 4 4 M15 9.5a1.5 1.5 0 1 0 0-.01',
 save:'M5 4h11l3 3v13H5z M8 4v5h7V4 M8 20v-6h8v6',
 play:'M7 4v16l13-8z',
 pause:'M6 5h4v14H6z M14 5h4v14h-4z',
 plus:'M12 5v14 M5 12h14',
 search:'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M20 20l-4-4',
 gear:'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
 dots:'M12 5h.01 M12 12h.01 M12 19h.01',
 pen:'M4 20h4L19 9l-4-4L4 16z',copy:'M9 9h11v11H9z M5 15H4V4h11v1',trash:'M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13',
 back:'M15 18l-6-6 6-6'};
function mgSvg(n,fill){return `<svg viewBox="0 0 24 24"${fill?' style="fill:currentColor;stroke:none"':''}><path d="${MG_ICONS[n]}"/></svg>`}
function mgProjects(){return (state.projects||[]).filter(p=>!p.simulation_test_key).sort((a,b)=>String(b.created_at||'').localeCompare(String(a.created_at||'')))}
function mgDate(v){const d=new Date(v||0);return isNaN(d)||!v?'':d.toLocaleDateString('vi-VN',{day:'2-digit',month:'2-digit',year:'numeric'})+' '+d.toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit'})}
function mgCurrent(){const list=mgProjects();if(!list.some(p=>p.id===mgSel))mgSel=list[0]?.id||'';return list.find(p=>p.id===mgSel)}
function mgForm(p){
 if(!mgForms[p.id]){const link=p.youtube_url||'',script=p.script||'';
  mgForms[p.id]={youtube_url:link,script,rewrite_style:p.rewrite_style||'',image_style:p.image_style||'',
   use_link:p.use_link??Boolean(link),use_script:p.use_script??(!link&&Boolean(script)),use_rewrite:p.rewrite??true,use_image:p.images??true,
   download:p.download??true,separate:p.separate??false,parallax:p.parallax??false}}
 return mgForms[p.id];
}
function mgSet(key,value){const p=mgCurrent();if(p)mgForm(p)[key]=value}
function mgDefaultLanes(){
 if(!mgProfilesAsked&&typeof refreshEdgeProfiles==='function'){mgProfilesAsked=true;refreshEdgeProfiles(true).then(()=>render()).catch(()=>{})}
 const dirs=(typeof edgeProfiles!=='undefined'?edgeProfiles:[]).map(x=>x.directory).filter(Boolean);
 const order=['Default',...dirs.filter(d=>d!=='Default')].filter((d,i,a)=>a.indexOf(d)===i&&(d==='Default'||dirs.includes(d))).slice(0,3);
 return order.map(profile=>({browser:'edge',profile}));
}
function mgHeader(){
 const cat=state.studio_catalog||{},studioOn=Boolean(cat.studio_tab_open),chatOn=Boolean(cat.chat_connected);
 return `<header class="mg-head"><img class="mg-logo" src="/logo.svg" alt="AI Manager"><div><div class="mg-title">AI <b>MANAGER</b></div><div class="mg-sub">for VIDEO IMAGE STUDIO <span class="mg-ver">v${esc(state.version||'')}</span></div></div>
 <div class="mg-pills"><span class="mg-pill"><i class="${studioOn?'on':''}"></i><span>Studio: <b class="${studioOn?'on':''}">${studioOn?'Đã kết nối':'Chưa mở'}</b></span></span><span class="mg-pill"><i class="${chatOn?'on':''}"></i><span>ChatGPT: <b class="${chatOn?'on':''}">${chatOn?'Đã kết nối':'Chưa kết nối'}</b></span></span>
 <button class="mg-icon-btn mg-gear ${typeof mgSet2!=='undefined'&&mgSet2.open?'on':''}" title="Cài đặt" onclick="mgSet2.open?mgCloseSettings():mgOpenSettings()">${mgSvg('gear')}</button></div></header>`;
}
function mgListHTML(){
 const q=mgSearch.trim().toLowerCase(),list=mgProjects().filter(p=>!q||p.name.toLowerCase().includes(q));
 return list.map(p=>`<div class="mg-item ${p.id===mgSel?'sel':''}" onclick="mgPick('${p.id}')">${mgSvg('doc')}<div class="t"><div class="n" title="${autoAttr(p.name)}">${esc(p.name)}</div><div class="d">${esc(mgDate(p.created_at))}</div></div><button class="k" title="Tuỳ chọn" onclick="event.stopPropagation();mgMenu=mgMenu==='${p.id}'?'':'${p.id}';render()">${mgSvg('dots')}</button>${mgMenu===p.id?`<div class="mg-menu" onclick="event.stopPropagation()"><button onclick="mgRename('${p.id}')">${mgSvg('pen')} Sửa tên</button><button onclick="mgCopy('${p.id}')">${mgSvg('copy')} Sao chép</button><button class="del" onclick="mgDelete('${p.id}')">${mgSvg('trash')} Xóa</button></div>`:''}</div>`).join('')||`<div class="mg-note" style="padding:10px">${q?'Không có dự án khớp.':'Chưa có dự án.'}</div>`;
}
function mgFormHTML(p){
 if(!p)return `<section class="mg-card"><h2>${mgSvg('doc')} Tạo / Chỉnh sửa dự án</h2><div class="mg-note">Bấm “Tạo dự án mới” để bắt đầu.</div></section>`;
 const f=mgForm(p),busy=['running','paused'].includes((state.queue.find(x=>x.id===p.id)||{}).status);
 const check=(key,label,hint='')=>`<label><input type="checkbox" class="mg-check" ${f[key]?'checked':''} onchange="mgSet('${key}',this.checked);render()"> ${label}${hint?` <small>${hint}</small>`:''}</label>`;
 return `<section class="mg-card"><h2>${mgSvg('doc')} Tạo / Chỉnh sửa dự án</h2><div class="mg-form">
 <div class="mg-field">${check('use_link','Link tham khảo','(YouTube / Bài viết...)')}<div class="mg-input ${f.use_link?'':'off'}">${mgSvg('link')}<input id="neo_mg_link" placeholder="https://..." value="${autoAttr(f.youtube_url)}" oninput="mgSet('youtube_url',this.value)" onblur="render()"></div></div>
 <div class="mg-field">${check('use_script','Kịch bản')}<div class="mg-input ${f.use_script?'':'off'}">${mgSvg('doc')}<textarea id="neo_mg_script" class="one" placeholder="Nhập nội dung kịch bản..." oninput="mgSet('script',this.value)" onfocus="this.classList.remove('one')" onblur="this.classList.add('one');render()">${esc(f.script)}</textarea></div></div>
 <div class="row2"><div class="mg-field">${check('use_rewrite','Prompt viết lại kịch bản')}<div class="mg-input ${f.use_rewrite?'':'off'}">${mgSvg('wand')}<textarea id="neo_mg_rewrite" placeholder="Nhập prompt viết lại kịch bản..." oninput="mgSet('rewrite_style',this.value)" onblur="render()">${esc(f.rewrite_style)}</textarea></div></div>
 <div class="mg-field">${check('use_image','Prompt tạo ảnh')}<div class="mg-input ${f.use_image?'':'off'}">${mgSvg('image')}<textarea id="neo_mg_image" placeholder="Nhập prompt tạo ảnh..." oninput="mgSet('image_style',this.value)" onblur="render()">${esc(f.image_style)}</textarea></div></div>
 <button class="mg-btn outline" ${mgBusy?'disabled':''} onclick="mgSave('${p.id}')">${mgSvg('save')} Lưu prompt</button></div></div>
 <div class="mg-actions"><button class="mg-btn primary" ${mgBusy||busy?'disabled':''} onclick="mgDeploy('${p.id}')">${mgSvg('play',1)} ${mgBusy==='deploy'?'Đang triển khai…':'Triển khai toàn bộ'}</button><button class="mg-btn outline" onclick="mgStop()">${mgSvg('pause')} Dừng toàn bộ</button>
 <label class="mg-opt"><input type="checkbox" class="mg-check" ${f.download?'checked':''} onchange="mgSet('download',this.checked)"> Tải ảnh</label><label class="mg-opt"><input type="checkbox" class="mg-check" ${f.separate?'checked':''} onchange="mgSet('separate',this.checked)"> Tách ảnh</label><label class="mg-opt" title="Sau khi tách ảnh: Parallax25D làm video 2.5D cho mỗi cảnh (Dự án\Video Parallax)"><input type="checkbox" class="mg-check" ${f.parallax?'checked':''} onchange="mgSet('parallax',this.checked)"> Video Parallax</label>
 ${mgErr?`<span class="mg-note err">${esc(mgErr)}</span>`:mgMsg?`<span class="mg-note ok">${esc(mgMsg)}</span>`:''}</div></section>`;
}
// What Studio itself holds for a linked project (it may be worked on in Studio directly, not by a Manager run).
let mgPlans={};
function mgPlan(p){
 const sid=p.studio_project_id||p.studio_import_id;if(!sid)return null;const e=mgPlans[sid];
 if(!e||(Date.now()-e.at>60000&&!e.busy)){mgPlans[sid]={...(e||{}),at:Date.now(),busy:true};api('/api/studio-plan',{studio_project_id:sid}).then(d=>{mgPlans[sid]={at:Date.now(),data:d};render()}).catch(()=>{mgPlans[sid]={...(mgPlans[sid]||{}),busy:false}})}
 return e?.data||null;
}
function mgStatusHTML(p){
 if(!p)return `<section class="mg-card mg-status"><div class="mg-empty">Chưa chọn dự án.</div></section>`;
 const q=state.queue.find(x=>x.id===p.id)||{},task=(state.automation?.tasks||[]).find(t=>t.id===q.automation_task_id),c={...(task?.context||{})};
 // Not running in Manager: show Studio's own numbers, so work done in Studio is visible here too.
 const plan=q.status!=='running'?mgPlan(p):null;
 if(plan){c.studio_total_parts=plan.parts;c.studio_completed_parts=plan.parts_done;c.studio_scope_total=plan.scenes;c.studio_images_generated=plan.images_done;if(!c.studio_stage)c.studio_stage=plan.active_job?'Studio đang xử lý':'Theo dữ liệu Studio';}
 const studioBusy=Boolean(plan?.active_job);
 const label=studioBusy?'Studio đang chạy':(typeof names!=='undefined'&&names[q.status])||q.status||'Chưa chạy';
 const cls=q.status==='running'||studioBusy?'run':['failed','needs_review'].includes(task?.status)?'err':'';
 const bar=(l,a,b)=>{const pct=b?Math.round(100*(a||0)/b):0;return `<div class="mg-bar"><div class="l">${l}</div><div class="v">${b?`${a||0}/${b}`:'—'}</div><div class="p"><i style="width:${pct}%"></i></div></div>`};
 const lanes=c.studio_lanes||[];
 const errs=[];if(task?.error&&['failed','needs_review','stopped'].includes(task.status))errs.push(task.error);(c.studio_attention||[]).forEach(a=>errs.push(a));
 if(c.studio_failed_items?.length)errs.push(c.studio_failed_items.length+' mục lỗi: '+c.studio_failed_items.slice(0,5).join(', '));
 if(c.studio_files_failed?.length)errs.push('Tải/tách ảnh lỗi: '+c.studio_files_failed.slice(0,5).join(', '));
 if(c.studio_message)errs.push(c.studio_message);
 if(!task&&!q.status&&!plan)return `<section class="mg-card mg-status"><div class="mg-empty">Dự án chưa chạy. Nhập thông tin rồi bấm “Triển khai toàn bộ”.</div></section>`;
 return `<section class="mg-card mg-status"><div class="mg-stage"><h2 style="margin:0">Tiến độ</h2><span class="mg-badge ${cls}">${esc(label)}</span><span class="mg-note">${esc(c.studio_stage||q.current_stage||'')}</span></div>
 <div class="mg-bars">${bar('Phân cảnh (phần)',c.studio_completed_parts,c.studio_total_parts)}${bar('Ảnh đã tạo',c.studio_images_generated,c.studio_scope_total)}${bar('Ảnh đã tải',c.studio_files_saved??c.studio_images_saved,c.studio_files_total??c.studio_scope_total)}${bar('Ảnh đã tách',c.studio_separated,c.studio_separate_total)}</div>
 ${lanes.length?`<div class="mg-sec">Tab ChatGPT</div>${lanes.map((l,i)=>`<div class="mg-lane"><b>Tab ${i+1}</b> ${esc(l.label||'')}<span>${l.cooldown?'Nghỉ tạo ảnh':!l.job?'Rảnh':l.kind==='image_generation'?'Tạo ảnh '+esc(l.job):'Phân cảnh '+esc(l.job)}</span></div>`).join('')}`:''}
 ${errs.length?`<div class="mg-sec">Thông báo</div>${errs.map(e=>`<div class="mg-err">${esc(e)}</div>`).join('')}`:''}
 <div class="mg-sec">Thư mục</div><div class="mg-note">${esc(p.folder||'')}</div></section>`;
}
function mgHTML(){
 const p=mgCurrent();
 return `${mgHeader()}<div class="mg-body"><div class="mg-card mg-side"><h2>${mgSvg('doc')} Quản lý dự án</h2><button class="mg-btn primary wide" onclick="mgNew()">${mgSvg('plus')} Tạo dự án mới</button>
 <div class="mg-search">${mgSvg('search')}<input id="neo_mg_search" placeholder="Tìm dự án..." value="${autoAttr(mgSearch)}" oninput="mgSearch=this.value;document.querySelector('.mg-list').innerHTML=mgListHTML()"></div><div class="mg-list" data-scroll-key="mg-list">${mgListHTML()}</div></div>
 <div class="mg-main">${mgFormHTML(p)}${mgStatusHTML(p)}</div></div>`;
}
function mgPick(id){mgSel=id;mgMenu='';mgMsg='';mgErr='';render()}
async function mgRun(kind,fn){mgBusy=kind;mgErr='';mgMsg='';render();try{await fn()}catch(e){mgErr=e.message}finally{mgBusy='';await refresh().catch(()=>{});render()}}
function mgNew(){const name=prompt('Tên dự án mới:','');if(!name||!name.trim())return;mgRun('new',async()=>{const p=await api('/api/project',{name:name.trim(),script:''});mgSel=p.id;mgMsg='Đã tạo “'+p.name+'”. Nhập link hoặc kịch bản rồi bấm Triển khai toàn bộ.'})}
function mgRename(id){mgMenu='';const p=state.projects.find(x=>x.id===id);const name=prompt('Tên mới:',p?.name||'');if(!name||!name.trim()||name.trim()===p?.name){render();return}mgRun('rename',async()=>{await api('/api/project-action',{id,action:'rename',name:name.trim()});mgMsg='Đã đổi tên'+(p?.studio_project_id?'; Studio nhận tên mới khi tab Studio mở':'')})}
function mgCopy(id){mgMenu='';mgRun('copy',async()=>{const r=await api('/api/project-action',{id,action:'copy'});mgSel=r.id;mgMsg='Đã sao chép thành “'+r.name+'”.'})}
function mgDelete(id){mgMenu='';const p=state.projects.find(x=>x.id===id);if(!confirm('Xóa dự án “'+(p?.name||'')+'”?\n\nThư mục được chuyển vào _Thung_rac trong thư mục dự án, không bị xóa hẳn.')){render();return}mgRun('delete',async()=>{await api('/api/project-action',{id,action:'delete'});delete mgForms[id];mgSel='';mgMsg='Đã chuyển vào thùng rác.'})}
async function mgSaveForm(id){const f=mgForms[id];if(!f)return;await api('/api/project-action',{id,action:'update',youtube_url:f.youtube_url,script:f.script,rewrite_style:f.rewrite_style,image_style:f.image_style,use_link:f.use_link,use_script:f.use_script,rewrite:f.use_rewrite,images:f.use_image,download:f.download,separate:f.separate,parallax:f.parallax})}
function mgSave(id){mgRun('save',async()=>{await mgSaveForm(id);delete mgForms[id];mgMsg='Đã lưu'})}
function mgDeploy(id){mgRun('deploy',async()=>{
 const p=state.projects.find(x=>x.id===id),f=mgForm(p);await mgSaveForm(id);
 const link=f.use_link?f.youtube_url.trim():'',script=f.use_script?f.script:'';
 let tasks=['analysis','scenes',...(f.use_image?['images']:[]),...(f.download?['sync']:[]),...(f.separate?['separate']:[]),...(f.parallax?['parallax']:[])];
 // A project already on Studio with "Prompt tạo ảnh" unticked: only download / separate the images it already has.
 const filesOnly=Boolean(p.studio_project_id)&&!f.use_image&&(f.download||f.separate||f.parallax);
 if(filesOnly)tasks=tasks.filter(t=>t==='sync'||t==='separate'||t==='parallax');
 const lanes=(p.lanes&&p.lanes.length?p.lanes:null)||p.work_config?.lanes||mgDefaultLanes();
 if(!p.studio_project_id){
  if(!link&&!script.trim())throw Error('Tích và nhập Link tham khảo hoặc Kịch bản');
  await api('/api/studio-deploy',{project:id,youtube_url:link,script:link?'':script,rewrite:f.use_rewrite,rewrite_style:f.use_rewrite?f.rewrite_style:'',image_style:f.use_image?f.image_style:'',tasks,lanes});
 }else{
  await api('/api/automation',{command:'studio_attach',project:id,studio_project_id:p.studio_project_id,studio_url:p.studio_url,browser:'edge',browser_profile:lanes[0]?.profile||p.browser_profile||'Default',work_config:{tasks,scopes:{},error_policy:'continue',retry_limit:2,rerun:false,lanes,separate_layers:p.separate_layers||3}});
  await api('/api/queue',{action:'start_batch',ids:[id]});
 }
 delete mgForms[id];mgMsg=filesOnly?'Đã triển khai: chỉ '+[f.download?'tải ảnh':'',f.separate?'tách ảnh':'',f.parallax?'làm video Parallax':''].filter(Boolean).join(', ')+' từ ảnh đã có.':'Đã triển khai. Manager đang mở Studio và ChatGPT.';
})}
function mgStop(){if(typeof stopEverything==='function')stopEverything();else api('/api/queue',{action:'stop_all'}).then(refresh)}
document.addEventListener('click',e=>{if(mgMenu&&!e.target.closest('.mg-menu,.mg-item .k')){mgMenu='';render()}});
(function mgInstall(){
 document.body.classList.add('mg');
 const base=render;
 render=function(){
  if(pointerHeld||document.activeElement?.id?.startsWith('neo_')||document.activeElement?.id?.startsWith('auto_'))return;
  const list=document.querySelector('.mg-list'),top=list?list.scrollTop:0,modal=document.querySelector('.mgs-modal'),mtop=modal?modal.scrollTop:0;
  if(page==='Cài đặt')page='Studio Automation';  // settings live in the popup now
  base();const extra=$('extra');
  extra.innerHTML=mgHTML()+(typeof mgSettingsHTML==='function'?mgSettingsHTML():'');const nl=document.querySelector('.mg-list');if(nl)nl.scrollTop=top;
  const nm=document.querySelector('.mgs-modal');if(nm)nm.scrollTop=mtop;
 };
 render();
})();
