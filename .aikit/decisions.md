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
