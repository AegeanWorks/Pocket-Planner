# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document catalogues Python modules, classes, and exported functions. See Map Coverage for any stack it does not index.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `2`
- **Total Classes**: `4`
- **Total Top-Level Functions**: `14`
- **Total Class Methods**: `61`
- **Total Source Lines**: `1003`

## 🧭 Map Coverage
- **Indexed**: python (`2` module(s))
- **Not indexed by this map**: none (no non-Python source files were found)

---

## 📦 Modules & Exported Symbols

### [`pocket_planner.py`](pocket_planner.py)
> *Pocket Planner: a small local-first task manager.*

**Size**: `504` lines (`19808` bytes)

**Classes:**
- `class Task`
- `class TaskStore`
  - Method `.__init__(path, *, replace_tries, retry_delay)`
  - Property `._backup_path`
  - Method `.load()`
  - Method `.next_task_id(tasks)` - *The next id this store issues; never an id a deleted task already used.*
  - Method `.save(tasks)`
  - Method `._sync_directory()`
- `class Stats`

**Functions:**
- `def now()`
- `def canonical_due(value)`
- `def validate_due(value)`
- `def normalize_tags(tags)`
- `def add_task(store, title, priority, due, tags)`
- `def complete_task(store, task_id)`
- `def reopen_task(store, task_id)`
- `def delete_task(store, task_id)`
- `def edit_task(store, task_id, title, priority, due, clear_due, tags, clear_tags)`
- `def _sort_key(name)`
- `def list_tasks(store, include_done, tag, overdue, priority, query, sort)`
- `def task_stats(store)`
- `def build_parser()`
- `def main(argv)`

---

### [`tests/test_pocket_planner.py`](tests/test_pocket_planner.py)
**Size**: `499` lines (`19001` bytes)

**Classes:**
- `class PocketPlannerTests`
  - Method `.setUp()`
  - Method `.tearDown()`
  - Method `.test_add_persists_and_normalizes_title()`
  - Method `.test_list_orders_open_tasks_by_priority()`
  - Method `.test_list_search_matches_title_and_tags_case_insensitively()`
  - Method `.test_list_sort_orders()`
  - Method `.test_list_rejects_unknown_sort()`
  - Method `.test_stats_counts_open_done_overdue_and_priorities()`
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
  - Method `.test_non_object_store_root_raises_runtime_error()`
  - Method `.test_non_positive_next_id_raises_runtime_error()`
  - Method `.test_non_object_task_raises_runtime_error()`
  - Method `.test_duplicate_task_ids_raise_runtime_error()`
  - Method `.test_unknown_fields_are_ignored_for_forward_compat()`
  - Method `.test_unknown_task_fields_survive_an_unrelated_write()`
  - Method `.test_unknown_root_keys_survive_an_unrelated_write()`
  - Method `.test_save_keeps_a_bak_of_the_previous_store()`
  - Method `.test_load_falls_back_to_bak_when_store_is_missing()`
  - Method `.test_save_retries_transient_replace_failures()`
  - Method `.test_empty_due_string_loads_as_none()`
  - Method `.test_invalid_due_on_load_raises_runtime_error()`
  - Method `.test_basic_iso_due_is_canonicalized_on_load()`
  - Method `.test_week_date_due_is_rejected()`
  - Method `.test_compact_due_is_canonicalized_on_add()`
  - Method `.test_non_integer_id_raises_runtime_error()`
  - Method `.test_out_of_range_priority_raises_runtime_error()`
  - Method `.test_non_boolean_done_raises_runtime_error()`
  - Method `.test_non_string_title_raises_runtime_error()`
  - Method `.test_non_string_created_at_raises_runtime_error()`
  - Method `.test_non_string_completed_at_raises_runtime_error()`
  - Method `.test_boolean_priority_raises_runtime_error()`
  - Method `.test_due_whitespace_is_stripped()`
  - Method `.test_deleted_task_id_is_not_reused()`
  - Method `.test_legacy_store_without_next_id_still_assigns_fresh_ids()`
  - Method `.test_edit_blank_due_requires_clear_due()`
  - Method `.test_blank_tag_filter_returns_unfiltered_list()`
  - Method `.test_priority_filter_selects_only_matching()`
  - Method `.test_api_boolean_priority_is_rejected()`
  - Method `.test_edit_updates_title_priority_due_and_tags()`
  - Method `.test_edit_clear_due_and_tags()`
  - Method `.test_edit_noop_and_conflicts_raise()`

---
