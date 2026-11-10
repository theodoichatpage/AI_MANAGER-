import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const {Client}=await import(pathToFileURL(path.join(input.sdk_root,'dist/esm/client/index.js')));
const {StdioClientTransport}=await import(pathToFileURL(path.join(input.sdk_root,'dist/esm/client/stdio.js')));
const client=new Client({name:'existing-windows-agent',version:'1.0.0'});
const transport=new StdioClientTransport({command:input.node,args:[input.server,'--browser-url',input.browser_url,'--no-usage-statistics','--no-performance-crux','--no-javascript-evaluation'],stderr:'pipe'});
let errors='';transport.stderr?.on('data',d=>errors+=String(d));
try {
 await client.connect(transport);
 const call=async(name,args={})=>{const r=await client.callTool({name,arguments:args});if(r.isError)throw new Error(JSON.stringify(r.content));return r.content.filter(x=>x.type==='text').map(x=>x.text).join('\n');};
 const pages=await call('list_pages');
 const matches=[...pages.matchAll(/^(\d+):.*?\((https?:\/\/[^)]+)\)(?:\s|$)/gm)].filter(m=>m[2]===input.page_url);
 if(matches.length!==1)throw new Error('EXACT_OWNED_PAGE_REQUIRED');
 const pageId=Number(matches[0][1]);
 const snapshot=await call('take_snapshot',{pageId});
 if(input.operation==='snapshot')console.log(JSON.stringify({snapshot,url:input.page_url}));
 else if(input.operation==='fill_click'){
   const unique=(role,names)=>{const lines=snapshot.split('\n');const hits=[];
     for(const line of lines){const m=line.match(/^\s*uid=(\S+)\s+(\S+)(?:\s+("(?:[^"\\]|\\.)*"))?/);
       if(m&&m[2]===role&&m[3]&&names.includes(JSON.parse(m[3])))hits.push(m[1]);}
     if(hits.length!==1)throw new Error('ACCESSIBLE_ELEMENT_NOT_UNIQUE '+role+' '+hits.length);
     return hits[0];};
   const field=unique('textbox',['Message ChatGPT','Ask anything','Message','Send a message']);
   await call('fill',{pageId,uid:field,value:input.text});
   const after=await call('take_snapshot',{pageId});
   const buttons=[...after.matchAll(/^\s*uid=(\S+)\s+button\s+("(?:[^"\\]|\\.)*")/gm)].filter(m=>['Send prompt','Send message','Send'].includes(JSON.parse(m[2])));
   if(buttons.length!==1)throw new Error('SEND_BUTTON_NOT_UNIQUE');
   await call('click',{pageId,uid:buttons[0][1]});
   console.log(JSON.stringify({clicked:true,url:input.page_url}));
 } else throw new Error('UNSUPPORTED_OPERATION');
} catch(e){console.log(JSON.stringify({error:String(e),server_stderr:errors.slice(-500)}));process.exitCode=1;}
finally {await client.close();}
