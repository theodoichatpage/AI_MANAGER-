# 0.2.25 ? reconciled production-source snapshot

This source-only release preserves 29 local commits and 3 GitHub commits since their common ancestor. The live local checkout previously identified itself as 0.2.23; GitHub already contained 0.2.24. The reconciled branch is 0.2.25 and does not change the installed application.

Included: existing story/review and Studio coordination changes, single-project queue deployment and download-label fixes. The merge preserves explicit transcript redo, avoids restarting a completed owned transcript command, and retains review fingerprint/progress and pipeline counters.

Excluded: unaccepted Windows Control/Maintenance Mode candidates (`integration_reports/`), handoff checkpoints, credentials, authenticated profiles, databases, user projects/media, logs and backups. Removed 34 tracked Python bytecode files from this release tree. Existing ancestor commits are retained without history rewriting. The bundled `automation_agent/data/aprilynne_transcript.txt` is a source-required style reference, not a production project export; application logo/icon assets are also retained.

Validation on Windows/Python 3.15 in an isolated worktree: 84 Python tests passed across the affected workflow, story, deploy, import, lanes, reconciliation, queue, presence, identity and merge-regression suites; 3 download-label Node tests passed; Studio UI binding/progress assertions passed; changed JavaScript syntax checks and Git whitespace checks passed. External services are fixtures where the tests specify them. No live production pipeline E2E acceptance, service restart, deployment, candidate activation, or merge into main was performed.

Security review covers newly introduced historical blobs, final source files, filenames and new commit messages using credential-pattern checks. This is a scoped review, not a guarantee that arbitrary secrets are detectable. Local audit evidence is retained outside this branch.

Rollback for consumers: keep the previous installed version and configuration; publishing this branch itself changes no runtime state. Review and explicit deployment remain separate steps.
