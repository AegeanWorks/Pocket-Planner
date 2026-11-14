# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: Overdue lists never include completed tasks
- **Date**: 2026-11-04
- **Status**: Accepted
- **Context**: `list --overdue --all` returned completed past-due tasks, so finished work kept surfacing as needing action.
- **Decision**: The overdue filter excludes done tasks regardless of `include_done`; `--all` still shows completed tasks in the plain list.
- **Consequences**: Overdue output always means "open work needing action"; anyone auditing finished late work uses `list --all`.

### ADR-002: CLI supports reopen and rm alongside done
- **Date**: 2026-11-04
- **Status**: Accepted
- **Context**: A mis-tapped `done` was irreversible via the CLI and junk tasks could only be removed by hand-editing the JSON store.
- **Decision**: Added `reopen <id>` (clears done and completed_at, errors when the task is still open or missing) and `rm <id>` (alias `delete`; removes only the target, errors on a missing id).
- **Consequences**: Full task lifecycle via CLI; `rm` is destructive by design and has no undo short of restoring the file.

### ADR-003: In-place edit plus hardened store loading
- **Date**: 2026-11-06
- **Status**: Accepted
- **Context**: Fixing a title, priority, due date, or tag required delete plus re-add, losing the id and created_at. Loading also crashed on unknown future fields and accepted malformed due/tags shapes that later broke filtering.
- **Decision**: Added `edit <id>` with `--title/--priority/--due/--clear-due/--tag/--clear-tags` (no-op and conflicting flags error) and `list --priority`; hardened `TaskStore.load` to ignore unknown fields, coerce `""` due to null, validate due/tags shapes, and normalize tags; `validate_due` strips whitespace and blank means null; blank `--tag` filter is ignored.
- **Consequences**: Tasks can be corrected without id churn; older clients tolerate newer stores, while genuinely corrupt due/tags still fail loud as RuntimeError.

### ADR-004: Unknown task fields survive writes; due-format tightening deferred
- **Date**: 2026-11-14
- **Status**: Accepted
- **Context**: Reforge run-1 found that `load` dropped unknown fields while `save` rewrote each task from `Task` alone, so the first write from this client permanently deleted fields a newer store carried; ADR-003's tolerance promise held only until that write. The same review flagged untested shape guards, `date.fromisoformat` accepting non-`YYYY-MM-DD` forms on Python 3.11+, and LICENSE references to `licenses/ACL-1.0.md` and `licenses/CONTRIBUTING_CLA.md` that this repository does not ship.
- **Decision**: `TaskStore` keeps each loaded task's unknown fields keyed by task id and merges them back in `save`, and tests pin the non-object root and task guards. Strict `YYYY-MM-DD` shape checking before `fromisoformat` is deferred because it would reject stores a 3.11+ runtime already accepted, so it needs a migration decision first. The license file paths are fixed upstream in the shared Aegean licensing text, not by editing a per-project copy.
- **Consequences**: Older clients round-trip future fields without interpreting them; extras are re-emitted only for tasks still present, so deleting a task drops its extras with it; due parsing remains runtime-family dependent until the migration decision lands.

### ADR-005: Store validates field types and never reissues a deleted id
- **Date**: 2026-11-14
- **Status**: Accepted
- **Context**: The audit of the Reforge reviews found that a parseable store carrying wrong field types (`id: "x"`, `priority: "high"`, `done: "yes"`) loaded intact and then crashed `add_task` with an uncaught `TypeError` instead of the documented `RuntimeError`; deleting the highest id made the next `add` reuse it, silently repointing any saved reference; and `edit --due ""` cleared a due date the README says needs `--clear-due`.
- **Decision**: `TaskStore.load` validates `id`, `title`, `priority`, `done`, `created_at` and `completed_at` types alongside the existing due and tag checks. The store file gains a root `next_id`; `add_task` takes its id from it, and `save` advances it past the highest id it has issued or seen. A blank `--due` on `edit` now errors and names `--clear-due`.
- **Consequences**: Malformed stores fail as `RuntimeError` before any mutation. Ids stay stable references after deletions for every store written by this version; a legacy store without `next_id` falls back to max-id+1 until its first write, so one reuse is still possible there. Older clients ignore the extra root key, and unknown task fields remain preserved per task as ADR-004 says.

### ADR-006: Store rejects duplicate ids and non-positive next_id, and preserves unknown root keys
- **Date**: 2026-11-14
- **Status**: Accepted
- **Context**: Delivery-verification probes over the store-integrity commits found that a store listing two tasks with the same `id` loaded silently; two visible tasks then shared one identity, per-task unknown fields collided on the same extras key, and `done`/`edit`/`rm` acted only on the first match, breaking the stable-reference promise harder than the reuse bug ADR-005 fixed. `next_id: -7` also loaded intact, laundering a nonsense counter, and unknown root-level keys were silently dropped on the first write - an asymmetry with ADR-004, which preserves unknown per-task fields.
- **Decision**: `TaskStore.load` rejects duplicate task ids and a stored `next_id` below 1 as corrupt (`RuntimeError`, same wrapper as every other guard). Unknown root keys are captured into `_root_extras` and merged back on `save`, exactly mirroring the per-task extras mechanism, so a write no longer deletes root-level metadata a newer client stored.
- **Consequences**: Duplicate-id stores fail loud instead of exposing ambiguous identity; the id counter must be a positive integer. Round-tripping root keys removes the write asymmetry without interpreting them, so older and newer clients alike keep opaque root metadata across this client's writes. No migration needed: every store this version wrote was already conformant.

### ADR-007: Save keeps a .bak, retries the replace, and defers advisory locking
- **Date**: 2026-11-14
- **Status**: Accepted
- **Context**: PRINCIPLE-013 names temp+fsync+replace with retries, a directory fsync and a `.bak` for state files; inspection of `save` found a single unretried `os.replace`, no directory sync, and no recovery copy, so a crash mid-save or a rename blocked by a stale handle lost the store head.
- **Decision**: `save` first moves the previous store to `.bak`, writes the temp file, and retries `os.replace` up to five times with a flat injectable delay (default 50ms). On POSIX the directory is fsynced after the replace; on Windows the flush is skipped because a directory handle cannot be durably flushed there and the file's own fsync bounds the window. `load` falls back to `.bak` when the main file is missing, which makes the backup move part of the recovery contract. Advisory locking is deferred: the CLI is single-user and each command performs one load-modify-save, so a lost-update window remains between two simultaneous commands; adopting the 3s/30s lock pattern would require a transaction wrapper across the mutators and lands when a real concurrent need appears.
- **Consequences**: Every completed write leaves the previous store recoverable from `.bak`; a crash between the backup move and the replace leaves the main file absent until the next save and reads serve the backup. Retry delays are flat rather than exponential, enough for transient Windows handle contention. Two simultaneous writers can each overwrite the other - a documented single-writer stance, revisited with the locking ADR if the store ever serves a second process.

### ADR-008: Due dates canonicalize to YYYY-MM-DD at every entry point
- **Date**: 2026-11-14
- **Status**: Accepted
- **Context**: ADR-004 deferred strict due-shape checking because `date.fromisoformat` also accepts compact (`20261102`) and week (`2026-W44-2`) dates on Python 3.11+, so a store written by a 3.11 runtime could contain values a 3.10 runtime rejects, and the CLI accepted runtime-dependent shapes depending on the interpreter that ran it.
- **Decision**: A single `canonical_due` helper defines the acceptance set: compact 8-digit dates are accepted and rewritten to `YYYY-MM-DD`; week dates, partial forms and any other shape fail `ValueError` before `fromisoformat` runs, identically on every supported runtime. `validate_due` (CLI add/edit) and the load path both go through it, and the load path's wrapped `RuntimeError` message is unchanged.
- **Consequences**: This resolves the migration decision ADR-004 deferred: stores written by 3.11 runtimes with non-canonical due values self-heal on load and persist canonical form on the next write (a one-time normalizing write), while week dates - never deliberately usable - fail loud instead of being laundered. Due values are comparable and filterable consistently across runtimes; clients relying on week-date input must switch to `YYYY-MM-DD` (or `YYYYMMDD`).

### ADR-009: Store carries a root schema_version; newer stores fail load
- **Date**: 2026-11-14
- **Status**: Accepted
- **Context**: Successive store-contract changes (root `next_id`, root extras, due canonicalization) each had to argue from the absence of any format marker; nothing in a store file told a reader which writer produced it, so a future format change could silently misread older or newer shapes.
- **Decision**: `save` writes a root `schema_version` equal to module constant `SCHEMA_VERSION` (currently 2). `load` accepts a missing key (every legacy store) and requires a positive integer otherwise; a value greater than `SCHEMA_VERSION` fails load with a `RuntimeError` that names both versions. The key is a known root key, so unlike opaque root extras it is owned by the writer, never re-merged from loaded data.
- **Consequences**: Newer stores written by a future client are refused with an actionable message instead of being misinterpreted; migration tooling gets an explicit anchor. Version 2 acknowledges that the store now guarantees `next_id`, root-extras round-tripping and canonical due values - stores whose writer predates those guarantees load as version-less legacy and conform on their first write, so no data migration is required.

### ADR-010: Advisory locking closes the ADR-007 deferral
- **Date**: 2026-11-14
- **Status**: Accepted
- **Context**: ADR-007 kept a single-writer stance and deferred advisory locking "when a real concurrent need appears". The store now serves more than interactive typing: `stats --json` targets scripts and agents, which routinely run alongside manual CLI use, so two simultaneous load-modify-save cycles on one store stopped being hypothetical and the lost-update window started trading real edits.
- **Decision**: `TaskStore` gains an advisory lock file beside the store (`<store>.lock`, created with `O_CREAT|O_EXCL`, holding pid and timestamp) and a `transaction()` contextmanager: acquire (wait up to 3s, retrying at the save retry delay), load, yield the task list, save on a clean exit, release on every exit path. All five mutators (add, done, reopen, rm, edit) run their load-modify-save inside that transaction and their input validation stays lock-free before acquisition. A lock older than 30s is treated as stale and broken. `save` remains an unlocked primitive used only inside a transaction; reads stay lock-free behind the atomic replace. Timing is injectable (`lock_wait`, `retry_delay`, `stale_after`) so tests run in milliseconds.
- **Consequences**: Simultaneous writers serialize: the loser gets `Error: store is locked by another process` and exit 1 instead of silently overwriting the winner, and a crashed writer's orphan lock self-heals after 30s. The concurrency model is one writer per process (the CLI shape); nested transactions in one process reuse the held lock. A live writer whose transaction exceeds 30s can have its lock broken by a peer - accepted because transactions are single-digit-millisecond operations. The lock file appears beside stores and is left behind only by a killed process. ADR-007's single-writer stance ends; its recovery contract (`.bak` fallback, atomic replace, retries) is unchanged.



