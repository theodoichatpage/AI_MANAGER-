// The send refuses a draft the user typed, but replaces WinControl's own unsent prompt from an interrupted task.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'..','automation_agent','chrome_mcp_bridge.mjs'),'utf8');
const start=src.indexOf("    const plain=q=>"),stop=src.indexOf("    await call('fill'",start);
assert(start>0&&stop>start,'draft check block found');
const check=new Function('a','snapshot',src.slice(start,stop)+"\n    return 'SEND';");
const snap=value=>'uid=1_0 RootWebArea "ChatGPT"\n  uid=1_6 textbox "Ask anything" multiline'+(value==null?'':' value="'+value+'"')+'\n';
const prompt='[wincontrol-new-1] WinControl task. JSON only';
const run=(draft,text=prompt)=>{try{return check({text},snap(draft))}catch(e){return e.message}};
assert.equal(run(null),'SEND','empty composer');
assert.equal(run('[wincontrol-old-3] WinControl tool result; continue autonomously'),'SEND','own stale prompt of an interrupted task is replaced');
assert.equal(run('[wincontrol-new-1] partial'),'SEND','an earlier try of this same exchange');
assert.equal(run('Ghi chú tôi đang gõ dở'),'UNSENT_DRAFT_PRESENT','text the user typed is never replaced');
assert.equal(run('[wincontrol-old-3] x','Hello from elsewhere'),'UNSENT_DRAFT_PRESENT','only a WinControl prompt may replace a WinControl draft');
console.log('bridge draft rules PASS');
