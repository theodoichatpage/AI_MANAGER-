# WinControl P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a usable Vietnamese WinControl surface to the existing Windows Agent and verify that commands reach real Agent/MAN state without disturbing existing production checkpoints.

**Architecture:** Extend the existing local Manager UI and its authenticated Agent client/API rather than adding another executable, Agent, queue, or service. Keep production actions routed through MAN and Studio; expose only read-only observations and explicit, checkpointed Agent actions. The current package has no supported non-Codex-CLI reasoning provider, so natural-language planning must fail closed until one is configured rather than pretending a deterministic parser is autonomous AI.

**Tech Stack:** Existing Python `http.server`, AgentRuntime/TaskStore, JavaScript UI shell, Node UI tests, Python unittest.

**Spec:** User P0 WinControl requirements dated 2026-11-10.

## Global Constraints

- Reuse the single existing Windows Agent and local APIs.
- Preserve every existing queue, task, and checkpoint; never retry unknown ChatGPT/Studio commands.
- Project selection must resolve from live MAN ID/name data; no project-specific IDs or names in operational code.
- Do not modify billing, MAN/Studio production records, Extension, or external service configuration.
- Do not claim AI autonomy while the only available visual planner requires Codex CLI.

## Review Focus

- Ambiguous project names must be rejected without action; prove with a duplicate-name test.
- Natural-language actions must not bypass TaskStore/ActionExecutor; prove the UI calls the local API and returns a task ID.
- Stop must preserve checkpoint and avoid converting stopped work to running; prove no automatic requeue path.
- UI status must distinguish Agent, task, and external Studio errors; prove error and result render.
- New UI must not render untrusted project/task text as HTML; prove escaping behavior.

---

### Task 1: WinControl command surface

**Files:**
- Modify: `ui_shell.js`
- Modify: `automation.css`
- Modify: `server.py`
- Test: `tests/test_wincontrol_ui.cjs`
- Test: `tests/test_wincontrol_api.py`

**Interfaces:**
- `GET /api/wincontrol` returns `{agent, projects, queue, tasks, logs}` from existing in-process services.
- `POST /api/wincontrol` accepts `{command, request_id}` and returns `{accepted, task_id?, result?, error?}`; all writes must go through existing AutomationService/TaskStore.

- [ ] Test UI entry/form/polling and Vietnamese escaping.
- [ ] Test ID/name project resolution, ambiguity rejection, and read-only status.
- [ ] Add the small UI page and same-origin API routes.
- [ ] Verify against the live local Agent without changing any production task.

### Task 2: Real Windows safe workflow

**Files:**
- Modify: `automation_agent/window_manager.py`
- Modify: `automation_agent/action_worker.py`
- Modify: `automation_agent/task_store.py`
- Test: `tests/test_wincontrol_windows.py`

**Interfaces:**
- Allow only the built-in Notepad executable as a new app target.
- A test workflow must open, type, save, reopen, and verify a file through UIA and TaskStore checkpoints.

- [ ] Add unit coverage for the safe app allowlist and checkpointed sequence.
- [ ] Add the narrow implementation.
- [ ] Run Test 1 only on the Windows desktop when the deployment can be performed safely.

### Task 3: Deployment and acceptance

**Files:**
- Modify: `README.md`
- Create: `evidence/wincontrol_p0_acceptance.json`

- [ ] Verify Agent/API/UI identity and preserved queue/checkpoint state.
- [ ] Run the requested operational tests that do not require external billing or Codex CLI.
- [ ] Mark AI autonomy and production as blocked unless an independently available reasoning provider and restored Studio egress are evidenced.
