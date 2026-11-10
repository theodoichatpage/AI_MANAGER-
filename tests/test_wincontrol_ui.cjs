const assert = require('node:assert/strict');
const fs = require('node:fs');
const shell = fs.readFileSync('ui_shell.js', 'utf8');
const page = fs.readFileSync('index.html', 'utf8');
const server = fs.readFileSync('server.py', 'utf8');

assert.match(page, /src="\/manager_settings\.js"><\/script><script src="\/wincontrol\.js"/);
assert.match(fs.readFileSync('wincontrol.js', 'utf8'), /WinControl/);
assert.match(fs.readFileSync('wincontrol.js', 'utf8'), /winControlHTML\(\)/);
assert.match(server, /path=='\/wincontrol\.js'/);
assert.match(fs.readFileSync('wincontrol.js', 'utf8'), /api\('\/api\/automation'/);
assert.match(fs.readFileSync('wincontrol.js', 'utf8'), /wincontrol_cancel/);
assert.match(fs.readFileSync('wincontrol.js', 'utf8'), /Dừng an toàn/);
console.log('WinControl UI to live Agent/MAN API wiring PASS');
