# AI MANAGER v0.2.11 — SetProp regression

Removed SetProp/GetProp entirely from automation_agent. No ctypes SetPropW and no writing properties to Edge. The Agent stores schema-2 HWND/PID/process-start/profile mappings in edge_windows.json. Previous mappings require fresh verification; project/queue/task/checkpoint data are not reset. Before each Edge action it checks the current window/process and reads the native profile evidence again, protecting against same-PID HWND reuse. Unsupported/missing proof still blocks input.

OPEN_APP failure displays the latest task's error and its ID, exits verifying state and enables Retry Edge. Existing STOP, Chrome and CapCut workflows are unchanged. Toast stays bottom-right for 4 seconds. Old errors from an earlier task of the same app are not re-announced over newer tasks.

Diagnostics contain real Agent PID/source/version/build fingerprint/commit and installed pywin32 version. Worker identity is separate. Manager rejects a mismatched Agent source/version. ZIP build_info.json records the source commit and must match the source fingerprint; if unknown/changed, the commit is reported as unknown rather than invented.

Windows API contract scans source imports/references and uses real installed modules + hasattr, including win32gui/win32api/win32process/win32con/propsys/pscon plus win32job/win32clipboard/pythoncom. Constants are checked too. Non-Windows explicitly SKIPs. The baseline v0.2.10 inventory must FAIL on the real missing SetProp; the new source must PASS. Run automatically at Windows launcher startup and shown in Agent diagnostics. A Windows GitHub Actions workflow also runs the real-module contract; its result must be reported separately from Linux unit tests and Edge acceptance.

Windows steps: close old Manager/server; extract single AI_MANAGER_v0.2.11 folder; launch MO_AI_MANAGER.bat; Edge → choose profile → Open Edge → select verified window → Run Edge test → View image. On failure, the retry button becomes available and diagnostics identify the exact Agent build. No cookie/token/password access, new profiles or AI API.

Windows API existence checks do not prove Edge profile detection, focus, screenshot, login persistence or STOP on a real Edge session. Those remain Windows user acceptance checks.
