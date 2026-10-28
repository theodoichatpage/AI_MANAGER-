const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('automation.js','utf8'),c);
assert.equal(vm.runInContext('autoAttr(\'"<&\\\'\')',c),'&quot;&lt;&amp;&#39;');
console.log('HTML attribute escaping PASS');
