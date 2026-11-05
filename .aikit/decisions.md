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
