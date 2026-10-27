# Phase 2
Persist queue and checkpoints atomically in SQLite, reconcile Phase 1 project folders, enforce transitions under a single lock, and recover interrupted work paused. A separate simulation worker supplies progress events. Expose local control API and show queue/log in existing dashboard. Verify sequencing, pause, failure, retry, stop and restart before committing.
