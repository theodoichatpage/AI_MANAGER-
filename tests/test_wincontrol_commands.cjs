const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('wincontrol.js', 'utf8');
assert.match(source, /api\('\/api\/automation',\{command:'wincontrol',text:command\}\)/);
assert.doesNotMatch(source, /function winControlPlan\(/);
assert.match(fs.readFileSync('automation_agent/manager_service.py', 'utf8'), /cmd=='wincontrol'/);
assert.match(fs.readFileSync('automation_agent/action_worker.py', 'utf8'), /name=='WINCONTROL_DECIDE'/);
assert.match(fs.readFileSync('automation_agent/runtime.py', 'utf8'), /wincontrol_feedback/);
console.log('WinControl uses the existing ChatGPT MCP and autonomous action/result loop PASS');
