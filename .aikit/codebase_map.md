# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document catalogues Python modules, classes, and exported functions. See Map Coverage for any stack it does not index.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `2`
- **Total Classes**: `5`
- **Total Top-Level Functions**: `17`
- **Total Class Methods**: `90`
- **Total Source Lines**: `1343`

## 🧭 Map Coverage
- **Indexed**: python (`2` module(s))
- **Not indexed by this map**: none (no non-Python source files were found)

---

## 📦 Modules & Exported Symbols

### [`pocket_planner.py`](pocket_planner.py)
> *Pocket Planner: a small local-first task manager.*

**Size**: `626` lines (`24167` bytes)

**Classes:**
- `class Task`
- `class TaskStore`
  - Method `.__init__(path, *, replace_tries, retry_delay, lock_wait, stale_after)`
  - Property `._backup_path`
  - Property `._rotated_backup_path`
  - Property `._lock_path`
  - Method `._acquire_lock()`
  - Method `._release_lock()`
  - Method `.transaction()` - *Lock, load, yield the task list, save on a clean exit, release always.*
  - Method `.load()`
  - Method `.next_task_id(tasks)` - *The next id this store issues; never an id a deleted task already used.*
  - Method `.save(tasks)`
  - Method `._sync_directory()`
- `class Stats`

**Functions:**
- `def now()`
- `def validate_priority(value)`
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
- `def next_task(store)`
- `def task_stats(store)`
- `def render_task(task)`
- `def build_parser()`
- `def main(argv)`

---

### [`tests/test_pocket_planner.py`](tests/test_pocket_planner.py)
**Size**: `717` lines (`29157` bytes)

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
  - Method `.test_save_writes_schema_version()`
  - Method `.test_legacy_store_without_schema_version_loads()`
  - Method `.test_newer_schema_version_fails_load()`
  - Method `.test_invalid_schema_version_fails_load()`
  - Method `.test_legacy_tasks_without_metadata_still_load()`
  - Method `.test_metadata_is_persisted_and_filterable()`
  - Method `.test_relative_due_dates_freeze_to_absolute_iso_dates()`
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
  - Method `.test_save_rotates_two_backup_generations()`
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
  - Method `.test_locked_store_refuses_mutator_with_runtime_error()`
  - Method `.test_stale_lock_is_broken_and_mutation_succeeds()`
  - Method `.test_error_inside_transaction_releases_lock_and_writes_nothing()`
  - Method `.test_second_store_is_locked_out_while_a_transaction_is_open()`
  - Method `.test_second_process_writer_wins_the_lock_after_release()`
  - Method `.test_next_task_returns_top_open_task_in_due_order()`
  - Method `.test_next_task_without_open_tasks_raises()`
  - Method `.test_edit_noop_and_conflicts_raise()`
- `class MainTests`
  - Method `.setUp()`
  - Method `.tearDown()`
  - Method `.run_main(*argv)`
  - Method `.test_main_search_matches_title_and_tags_case_insensitively()`
  - Method `.test_main_sort_priority_orders_and_bad_sort_is_argparse_rejected()`
  - Method `.test_main_stats_prints_summary_and_priorities()`
  - Method `.test_main_bad_priority_is_argparse_rejected_with_usage_error()`
  - Method `.test_main_next_prints_top_open_task_and_empty_store_fails_cleanly()`
  - Method `.test_main_stats_json_prints_parseable_summary()`
  - Method `.test_main_relative_due_round_trips_through_add_and_edit()`
  - Method `.test_main_added_task_is_persisted()`

---
