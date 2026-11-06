const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function ui(fetch){
 const c=vm.createContext({MG_ICONS:{},document:{addEventListener(){}},state:{version:'0.2.23',download_url:'https://github.com/theodoichatpage/AI_MANAGER-/archive/refs/heads/main.zip'},esc:String,autoAttr:String,mgSvg:()=>'',render(){},fetch,AbortSignal});
 vm.runInContext(fs.readFileSync('manager_settings.js','utf8'),c);return c;
}
test('download label never claims installed 0.2.23 is the available release',()=>{
 const c=ui();assert.doesNotMatch(vm.runInContext('mgDataTab()',c),/Tải bản cài v0\.2\.23/);
});
test('published 0.2.24 labels the download while installed version stays 0.2.23',async()=>{
 const c=ui(async()=>({ok:true,json:async()=>({version:'0.2.24'})}));
 await vm.runInContext('mgCheckDownload()',c);
 assert.match(vm.runInContext('mgDataTab()',c),/Tải bản cài v0\.2\.24/);
 assert.equal(c.state.version,'0.2.23');
});
test('network failure or invalid manifest does not invent a release version',async()=>{
 for(const fetch of [async()=>{throw Error('offline')},async()=>({ok:true,json:async()=>({version:'<bad>'})})]){
 const c=ui(fetch);await vm.runInContext('mgCheckDownload()',c);
 const html=vm.runInContext('mgDataTab()',c);assert.match(html,/Tải bản cài mới nhất/);assert.doesNotMatch(html,/Tải bản cài v0\.2\.23/);
 }
});
