# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `2`
- **Total Classes**: `3`
- **Total Top-Level Functions**: `11`
- **Total Class Methods**: `32`
- **Total Source Lines**: `574`

---

## 📦 Modules & Exported Symbols

### [`pocket_planner.py`](pocket_planner.py)
> *Pocket Planner: a small local-first task manager.*

**Size**: `333` lines (`12733` bytes)

**Classes:**
- `class Task`
- `class TaskStore`
  - Method `.__init__(path)`
  - Method `.load()`
  - Method `.save(tasks)`

**Functions:**
- `def now()`
- `def validate_due(value)`
- `def normalize_tags(tags)`
- `def add_task(store, title, priority, due, tags)`
- `def complete_task(store, task_id)`
- `def reopen_task(store, task_id)`
- `def delete_task(store, task_id)`
- `def edit_task(store, task_id, title, priority, due, clear_due, tags, clear_tags)`
- `def list_tasks(store, include_done, tag, overdue, priority)`
- `def build_parser()`
- `def main(argv)`

---

### [`tests/test_pocket_planner.py`](tests/test_pocket_planner.py)
**Size**: `241` lines (`8871` bytes)

**Classes:**
- `class PocketPlannerTests`
  - Method `.setUp()`
  - Method `.tearDown()`
  - Method `.test_add_persists_and_normalizes_title()`
  - Method `.test_list_orders_open_tasks_by_priority()`
  - Method `.test_complete_sets_timestamp_and_hides_from_default_list()`
  - Method `.test_save_is_valid_json()`
  - Method `.test_legacy_tasks_without_metadata_still_load()`
  - Method `.test_metadata_is_persisted_and_filterable()`
  - Method `.test_invalid_due_date_is_rejected()`
  - Method `.test_empty_title_and_bad_priority_are_rejected()`
  - Method `.test_complete_missing_or_already_done_raises()`
  - Method `.test_overdue_excludes_completed_tasks()`
  - Method `.test_overdue_lists_only_open_past_due_tasks()`
  - Method `.test_delete_removes_only_the_target()`
  - Method `.test_delete_missing_id_raises()`
  - Method `.test_reopen_restores_completed_task()`
  - Method `.test_reopen_open_or_missing_task_raises()`
  - Method `.test_corrupt_store_raises_runtime_error()`
  - Method `.test_store_missing_tasks_key_raises_runtime_error()`
  - Method `.test_unknown_fields_are_ignored_for_forward_compat()`
  - Method `.test_empty_due_string_loads_as_none()`
  - Method `.test_invalid_due_on_load_raises_runtime_error()`
  - Method `.test_non_list_tags_on_load_raises_runtime_error()`
  - Method `.test_due_whitespace_is_stripped()`
  - Method `.test_blank_tag_filter_returns_unfiltered_list()`
  - Method `.test_priority_filter_selects_only_matching()`
  - Method `.test_edit_updates_title_priority_due_and_tags()`
  - Method `.test_edit_clear_due_and_tags()`
  - Method `.test_edit_noop_and_conflicts_raise()`

---
