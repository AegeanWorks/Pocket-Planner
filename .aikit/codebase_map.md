# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `2`
- **Total Classes**: `3`
- **Total Top-Level Functions**: `8`
- **Total Class Methods**: `12`
- **Total Source Lines**: `269`

---

## 📦 Modules & Exported Symbols

### [`pocket_planner.py`](pocket_planner.py)
> *Pocket Planner: a small local-first task manager.*

**Size**: `197` lines (`6724` bytes)

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
- `def list_tasks(store, include_done, tag, overdue)`
- `def build_parser()`
- `def main(argv)`

---

### [`tests/test_pocket_planner.py`](tests/test_pocket_planner.py)
**Size**: `72` lines (`2472` bytes)

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

---
