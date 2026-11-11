import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const {Client}=await import(pathToFileURL(path.join(input.sdk_root,'dist/esm/client/index.js')));
const {StdioClientTransport}=await import(pathToFileURL(path.join(input.sdk_root,'dist/esm/client/stdio.js')));
const client=new Client({name:'existing-windows-agent',version:'1.0.0'});
const transport=new StdioClientTransport({command:process.execPath,args:[input.server,'--browser-url',input.browser_url,'--no-usage-statistics','--no-performance-crux','--no-javascript-evaluation'],stderr:'pipe'});
let errors='';transport.stderr?.on('data',d=>errors+=String(d));
try {
 await client.connect(transport);
 const call=async(name,args={})=>{const r=await client.callTool({name,arguments:args});if(r.isError)throw new Error(JSON.stringify(r.content));return r.content.filter(x=>x.type==='text').map(x=>x.text).join('\n');};
 if(input.operation==='tools') {
  const result=await client.listTools();console.log(JSON.stringify(result.tools.filter(t=>['list_pages','select_page','navigate_page','take_snapshot','fill','click','wait_for'].includes(t.name))));
 } else {
  if(input.disconnect_once_marker&&!fs.existsSync(input.disconnect_once_marker)){fs.writeFileSync(input.disconnect_once_marker,'actual upstream transport closed before a read');await transport.close();throw new Error('MCP_CONNECTION_CLOSED_IN_STAGING; read not performed');}
  const pages=await call('list_pages');
  const matches=[...pages.matchAll(/^(\d+):.*?\((https?:\/\/[^)]+)\)(?:\s|$)/gm)].filter(m=>m[2]===input.page_url);
  if(matches.length!==1)throw new Error('EXACT_OWNED_PAGE_REQUIRED '+pages);
  const pageId=Number(matches[0][1]);const a=input.action;let result={backend:'chrome-devtools-mcp',page_id:pageId};
  if(a.action==='READ_URL')result.url=input.page_url;
  else if(a.action==='OPEN_URL') {await call('navigate_page',{pageId,type:'url',url:a.url,handleBeforeUnload:'dismiss',timeout:10000});result.requested_url=a.url;result.context={expected_url:a.url};}
  else {
   const snapshot=await call('take_snapshot',{pageId});
   if(a.action==='CHATGPT_SNAPSHOT')result={...result,snapshot,url:input.page_url};
   else if(a.action==='CHATGPT_SEND'){
    // take_snapshot prints names and values verbatim (inner quotes are not escaped) and a value may run over several
    // lines (the composer puts a line break around links). Lines that do not start a new uid belong to the element
    // above; a value is the text between ' value="' and the element's closing quote.
    const plain=q=>{try{return JSON.parse(q)}catch{return q.slice(1,-1)}};
    const logical=raw=>raw.split('\n').reduce((rows,line)=>{if(/^\s*uid=/.test(line)||!rows.length)rows.push(line);else rows[rows.length-1]+='\n'+line;return rows},[]);
    const elements=raw=>logical(raw).map(line=>line.match(/^\s*uid=(\S+)\s+(\S+)(?:\s+("(?:[^"\\]|\\.)*"))?([\s\S]*)$/)).filter(Boolean).map(m=>({uid:m[1],role:m[2],name:m[3]?plain(m[3]):'',extra:m[4]}));
    const valueOf=extra=>{const i=extra.indexOf(' value="');if(i<0)return null;const rest=extra.slice(i+8).replace(/\s+$/,'');return rest.endsWith('"')?rest.slice(0,-1):null};
    const same=(x,y)=>x.replace(/\s+/g,'')===y.replace(/\s+/g,'');
    const tag=a.text.startsWith('[')?a.text.slice(0,a.text.indexOf(']')+1):'';
    const fields=elements(snapshot).filter(e=>e.role==='textbox'&&['Message ChatGPT','Ask anything','Ask ChatGPT','Message','Send a message'].includes(e.name));
    if(fields.length!==1||/\b(disabled|readonly)\b/.test(fields[0].extra.split(' value="')[0]))throw new Error('COMPOSER_NOT_UNIQUE_OR_READY');
    // An unsent draft blocks the send, unless it is this prompt (or an earlier unsent try of the same exchange id).
    const previous=valueOf(fields[0].extra);
    if(previous&&previous.trim()&&!same(previous,a.text)&&!(tag.length>1&&previous.trim().startsWith(tag)))throw new Error('UNSENT_DRAFT_PRESENT');
    await call('fill',{pageId,uid:fields[0].uid,value:a.text});
    const filled=await call('take_snapshot',{pageId});
    const verified=elements(filled).filter(e=>e.role==='textbox'&&e.name===fields[0].name);
    const value=verified.length===1?valueOf(verified[0].extra):null;
    if(value===null||!same(value,a.text))throw new Error('COMPOSER_VALUE_UNVERIFIED_NO_SEND');
    const buttons=elements(filled).filter(e=>e.role==='button'&&['Send prompt','Send message','Send'].includes(e.name)&&!e.extra.includes('disabled'));
    if(buttons.length!==1)throw new Error('SEND_BUTTON_NOT_UNIQUE');
    await call('click',{pageId,uid:buttons[0].uid});result={...result,clicked:true,url:input.page_url};
   }
   else if(a.action==='READ_TITLE'){const m=snapshot.match(/RootWebArea\s+("(?:[^"\\]|\\.)*")/);if(!m)throw new Error('TITLE_NOT_OBSERVED');result={...result,title:JSON.parse(m[1]),snapshot};}
   else if(a.action==='WAIT_PAGE')result={...result,url:input.page_url,page_accessible:true};
   else {
    const selector=a.selector||{};const name=selector.name??selector.title;
    const role=selector.role??({Edit:'textbox',Button:'button',Text:'status'}[selector.control_type]);
    if(typeof name!=='string'||!role)throw new Error('ACCESSIBLE_NAME_AND_ROLE_REQUIRED');
    const lines=snapshot.split('\n');const found=[];
    for(let i=0;i<lines.length;i++){
     const m=lines[i].match(/^(\s*)uid=(\S+)\s+(\S+)(?:\s+("(?:[^"\\]|\\.)*"))?/);
     if(m&&m[3]===role&&m[4]&&JSON.parse(m[4])===name)found.push({uid:m[2],index:i,indent:m[1].length});
    }
    if(found.length!==1)throw new Error('ELEMENT_NOT_UNIQUE_OR_MISSING '+name+' '+found.length+' '+snapshot);
    const f=found[0];let stop=f.index+1;
    while(stop<lines.length&&/^\s*uid=/.test(lines[stop])&&lines[stop].search(/\S/)>f.indent)stop++;
    const element={uid:f.uid,name,role,text:lines.slice(f.index,stop).join('\n')};
    if(a.action==='TYPE_TEXT'){await call('fill',{pageId,uid:f.uid,value:a.text});result.characters=a.text.length;}
    else if(a.action==='CLICK'){await call('click',{pageId,uid:f.uid});result.method='MCP click on a11y uid';}
    else if(!['FIND_ELEMENT','READ_ELEMENT','WAIT_ELEMENT'].includes(a.action))throw new Error('UNSUPPORTED_DOM_ACTION');
    result.element=element;
   }
  }
  console.log(JSON.stringify(result));
 }
} catch(e){console.log(JSON.stringify({error:String(e),server_stderr:errors.slice(-1000)}));process.exitCode=1;}
finally {await client.close();}