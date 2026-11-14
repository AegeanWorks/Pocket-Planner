import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from pocket_planner import (
    SCHEMA_VERSION,
    Stats,
    Task,
    TaskStore,
    add_task,
    complete_task,
    delete_task,
    edit_task,
    list_tasks,
    main,
    next_task,
    now,
    reopen_task,
    task_stats,
)


class PocketPlannerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.directory.name) / "tasks.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_add_persists_and_normalizes_title(self):
        task = add_task(self.store, "  buy   groceries ", 1)

        self.assertEqual(task.title, "buy groceries")
        self.assertEqual(self.store.load()[0].id, 1)

    def test_list_orders_open_tasks_by_priority(self):
        add_task(self.store, "later", 3)
        add_task(self.store, "urgent", 1)

        self.assertEqual([task.title for task in list_tasks(self.store)], ["urgent", "later"])

    def test_list_search_matches_title_and_tags_case_insensitively(self):
        add_task(self.store, "Write docs", 2, tags=["review"])
        add_task(self.store, "other", 2)

        self.assertEqual(
            [task.title for task in list_tasks(self.store, query="write")], ["Write docs"]
        )
        self.assertEqual(
            [task.title for task in list_tasks(self.store, query="REVIEW")], ["Write docs"]
        )
        self.assertEqual(list_tasks(self.store, query="  missing  "), [])

    def test_list_sort_orders(self):
        add_task(self.store, "b", 3)
        add_task(self.store, "a", 1)

        self.assertEqual([task.title for task in list_tasks(self.store, sort="priority")], ["a", "b"])
        self.assertEqual([task.title for task in list_tasks(self.store, sort="id")], ["b", "a"])
        self.assertEqual([task.title for task in list_tasks(self.store, sort="created")], ["b", "a"])

    def test_list_rejects_unknown_sort(self):
        with self.assertRaises(ValueError):
            list_tasks(self.store, sort="title")

    def test_stats_counts_open_done_overdue_and_priorities(self):
        past = "2000-01-01"
        add_task(self.store, "overdue", 1, due=past)
        add_task(self.store, "high", 1)
        add_task(self.store, "low", 3)
        done = add_task(self.store, "finished", 2)
        complete_task(self.store, done.id)

        summary = task_stats(self.store)

        self.assertEqual(summary, Stats(tasks=4, open=3, done=1, overdue=1, by_priority={1: 2, 2: 1, 3: 1}))

    def test_complete_sets_timestamp_and_hides_from_default_list(self):
        task = add_task(self.store, "ship release", 2)

        complete_task(self.store, task.id)

        self.assertEqual(list_tasks(self.store), [])
        self.assertTrue(list_tasks(self.store, include_done=True)[0].done)

    def test_save_is_valid_json(self):
        add_task(self.store, "write docs", 2)

        payload = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["tasks"][0]["title"], "write docs")

    def test_save_writes_schema_version(self):
        add_task(self.store, "versioned", 2)

        payload = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)

    def test_legacy_store_without_schema_version_loads(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "legacy", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00"}]}',
            encoding="utf-8",
        )

        self.assertEqual(self.store.load()[0].title, "legacy")

    def test_newer_schema_version_fails_load(self):
        self.store.path.write_text(
            '{"schema_version": 99, "tasks": [], "next_id": 1}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_invalid_schema_version_fails_load(self):
        for payload in ('{"schema_version": "2", "tasks": []}', '{"schema_version": 0, "tasks": []}'):
            with self.subTest(payload=payload):
                self.store.path.write_text(payload, encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    self.store.load()

    def test_legacy_tasks_without_metadata_still_load(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 7, "title": "legacy task", "priority": 2, '
            '"done": false, "created_at": "2026-10-31T12:00:00+00:00"}]}',
            encoding="utf-8",
        )

        task = self.store.load()[0]

        self.assertEqual(task.title, "legacy task")
        self.assertEqual(task.tags, [])
        self.assertIsNone(task.due)

    def test_metadata_is_persisted_and_filterable(self):
        add_task(self.store, "plan launch", 2, "2026-11-02", [" Work ", "launch"])
        add_task(self.store, "buy coffee", 3)

        tasks = list_tasks(self.store, tag="work")

        self.assertEqual([task.title for task in tasks], ["plan launch"])
        self.assertEqual(tasks[0].tags, ["work", "launch"])
        self.assertEqual(tasks[0].due, "2026-11-02")

    def test_relative_due_dates_freeze_to_absolute_iso_dates(self):
        task = add_task(self.store, "soon", 2, "today+3")
        today = date.today()
        self.assertEqual(task.due, (today + timedelta(days=3)).isoformat())
        backward = add_task(self.store, "past", 2, "today-2")
        self.assertEqual(backward.due, (today - timedelta(days=2)).isoformat())
        plain = add_task(self.store, "now", 2, "TODAY")
        self.assertEqual(plain.due, today.isoformat())

    def test_invalid_due_date_is_rejected(self):
        with self.assertRaises(ValueError):
            add_task(self.store, "bad date", 2, "tomorrow")

    def test_empty_title_and_bad_priority_are_rejected(self):
        with self.assertRaises(ValueError):
            add_task(self.store, "   ", 2)
        with self.assertRaises(ValueError):
            add_task(self.store, "real task", 5)

    def test_complete_missing_or_already_done_raises(self):
        with self.assertRaises(ValueError):
            complete_task(self.store, 999)
        task = add_task(self.store, "once", 2)
        complete_task(self.store, task.id)
        with self.assertRaises(ValueError):
            complete_task(self.store, task.id)

    def test_overdue_excludes_completed_tasks(self):
        task = add_task(self.store, "old bill", 2, "2000-01-01", None)
        complete_task(self.store, task.id)

        self.assertEqual(list_tasks(self.store, overdue=True), [])
        self.assertEqual(list_tasks(self.store, include_done=True, overdue=True), [])

    def test_overdue_lists_only_open_past_due_tasks(self):
        add_task(self.store, "past", 2, "2000-01-01", None)
        add_task(self.store, "future", 2, "2999-01-01", None)
        add_task(self.store, "no due", 2)

        self.assertEqual(
            [task.title for task in list_tasks(self.store, overdue=True)], ["past"]
        )

    def test_delete_removes_only_the_target(self):
        first = add_task(self.store, "keep me", 2)
        second = add_task(self.store, "drop me", 2)

        removed = delete_task(self.store, second.id)

        self.assertEqual(removed.title, "drop me")
        self.assertEqual([task.id for task in self.store.load()], [first.id])

    def test_delete_missing_id_raises(self):
        with self.assertRaises(ValueError):
            delete_task(self.store, 999)

    def test_reopen_restores_completed_task(self):
        task = add_task(self.store, "mis-tapped", 2)
        complete_task(self.store, task.id)

        reopened = reopen_task(self.store, task.id)

        self.assertFalse(reopened.done)
        self.assertIsNone(reopened.completed_at)
        self.assertEqual([item.title for item in list_tasks(self.store)], ["mis-tapped"])

    def test_reopen_open_or_missing_task_raises(self):
        task = add_task(self.store, "still open", 2)
        with self.assertRaises(ValueError):
            reopen_task(self.store, task.id)
        with self.assertRaises(ValueError):
            reopen_task(self.store, 999)

    def test_corrupt_store_raises_runtime_error(self):
        self.store.path.write_text("not json{{{", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_store_missing_tasks_key_raises_runtime_error(self):
        self.store.path.write_text('{"nope": []}', encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_non_object_store_root_raises_runtime_error(self):
        self.store.path.write_text("[]", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_non_positive_next_id_raises_runtime_error(self):
        for bad_value in (0, -7):
            with self.subTest(next_id=bad_value):
                self.store.path.write_text(
                    f'{{"next_id": {bad_value}, "tasks": []}}',
                    encoding="utf-8",
                )
                with self.assertRaises(RuntimeError):
                    self.store.load()

    def test_non_object_task_raises_runtime_error(self):
        self.store.path.write_text('{"tasks": [1]}', encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_duplicate_task_ids_raise_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "a", "priority": 2, "done": false, "created_at": "x"}, '
            '{"id": 1, "title": "b", "priority": 3, "done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_unknown_fields_are_ignored_for_forward_compat(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "future", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00", '
            '"extra_future": 123}]}',
            encoding="utf-8",
        )

        self.assertEqual(self.store.load()[0].title, "future")

    def test_unknown_task_fields_survive_an_unrelated_write(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "future", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00", '
            '"extra_future": {"keep": 123}}]}',
            encoding="utf-8",
        )

        add_task(self.store, "new task", 2)

        payload = json.loads(self.store.path.read_text(encoding="utf-8"))
        future = next(item for item in payload["tasks"] if item["id"] == 1)
        self.assertEqual(future["extra_future"], {"keep": 123})

    def test_unknown_root_keys_survive_an_unrelated_write(self):
        self.store.path.write_text(
            '{"future_root": {"keep": 123}, "tasks": [{"id": 1, "title": "rooted", "priority": 2, '
            '"done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )

        add_task(self.store, "new task", 2)

        payload = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["future_root"], {"keep": 123})
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["next_id"], 3)

    def test_save_keeps_a_bak_of_the_previous_store(self):
        add_task(self.store, "one", 2)
        add_task(self.store, "two", 2)

        backup = self.store.path.with_name(self.store.path.name + ".bak")
        payload = json.loads(backup.read_text(encoding="utf-8"))

        self.assertEqual([item["title"] for item in payload["tasks"]], ["one"])

    def test_save_rotates_two_backup_generations(self):
        store = TaskStore(Path(self.directory.name) / "rotated.json")
        add_task(store, "one", 2)
        add_task(store, "two", 2)
        add_task(store, "three", 2)

        backup = store.path.with_name(store.path.name + ".bak")
        rotated = store.path.with_name(store.path.name + ".bak.1")

        payload = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual([item["title"] for item in payload["tasks"]], ["one", "two"])
        rotated_payload = json.loads(rotated.read_text(encoding="utf-8"))
        self.assertEqual([item["title"] for item in rotated_payload["tasks"]], ["one"])
        main_payload = json.loads(store.path.read_text(encoding="utf-8"))
        self.assertEqual([item["title"] for item in main_payload["tasks"]], ["one", "two", "three"])

    def test_load_falls_back_to_bak_when_store_is_missing(self):
        add_task(self.store, "one", 2)
        add_task(self.store, "two", 2)

        self.store.path.unlink()

        reloaded = self.store.load()
        self.assertEqual([task.title for task in reloaded], ["one"])

    def test_save_retries_transient_replace_failures(self):
        real_replace = os.replace
        calls = []

        def flaky_replace(source, destination):
            calls.append(destination)
            if len(calls) == 2 or len(calls) == 3:
                raise OSError("simulated transient failure")
            return real_replace(source, destination)

        self.store = TaskStore(self.store.path, retry_delay=0)
        add_task(self.store, "one", 2)

        with mock.patch("os.replace", flaky_replace):
            add_task(self.store, "two", 2)

        self.assertEqual(
            [task.title for task in self.store.load()], ["one", "two"]
        )
        leftovers = [item.name for item in self.store.path.parent.glob(f".{self.store.path.name}.*")]
        self.assertEqual(leftovers, [])

    def test_empty_due_string_loads_as_none(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "nodue", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00", "due": ""}]}',
            encoding="utf-8",
        )

        self.assertIsNone(self.store.load()[0].due)

    def test_invalid_due_on_load_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "bad", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00", "due": "tomorrow"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_basic_iso_due_is_canonicalized_on_load(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "compact", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00", "due": "20261101"}]}',
            encoding="utf-8",
        )

        tasks = self.store.load()
        self.assertEqual(tasks[0].due, "2026-11-01")
        self.store.save(tasks)
        self.assertEqual(self.store.load()[0].due, "2026-11-01")

    def test_week_date_due_is_rejected(self):
        with self.assertRaises(ValueError):
            add_task(self.store, "week", 2, "2026-W44-2")

        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "week", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00", "due": "2026-W44-2"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_compact_due_is_canonicalized_on_add(self):
        task = add_task(self.store, "compact", 2, "20261101")

        self.assertEqual(task.due, "2026-11-01")
        self.assertEqual(self.store.load()[0].due, "2026-11-01")
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "bad", "priority": 2, '
            '"done": false, "created_at": "2026-01-01T00:00:00+00:00", "tags": "work"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_non_integer_id_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": "one", "title": "t", "priority": 2, "done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_out_of_range_priority_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "t", "priority": 9, "done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_non_boolean_done_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "t", "priority": 2, "done": "yes", "created_at": "x"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_non_string_title_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": 7, "priority": 2, "done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_non_string_created_at_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "t", "priority": 2, "done": false, "created_at": 5}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_non_string_completed_at_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "t", "priority": 2, "done": true, "created_at": "x", "completed_at": 5}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_boolean_priority_raises_runtime_error(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 1, "title": "t", "priority": true, "done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_due_whitespace_is_stripped(self):
        task = add_task(self.store, "dated", 2, "  2026-11-02  ")

        self.assertEqual(task.due, "2026-11-02")

    def test_deleted_task_id_is_not_reused(self):
        first = add_task(self.store, "one", 2)
        second = add_task(self.store, "two", 2)
        third = add_task(self.store, "three", 2)

        delete_task(self.store, third.id)
        fourth = add_task(self.store, "four", 2)

        self.assertEqual([first.id, second.id, third.id], [1, 2, 3])
        self.assertEqual(fourth.id, 4)

    def test_legacy_store_without_next_id_still_assigns_fresh_ids(self):
        self.store.path.write_text(
            '{"tasks": [{"id": 7, "title": "legacy", "priority": 2, '
            '"done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )

        task = add_task(self.store, "new", 2)

        self.assertEqual(task.id, 8)

    def test_edit_blank_due_requires_clear_due(self):
        task = add_task(self.store, "t", 2, "2026-12-01")

        with self.assertRaises(ValueError):
            edit_task(self.store, task.id, due="   ")
        self.assertEqual(self.store.load()[0].due, "2026-12-01")

    def test_blank_tag_filter_returns_unfiltered_list(self):
        add_task(self.store, "a", 2, None, ["work"])

        self.assertEqual(len(list_tasks(self.store, tag="   ")), 1)

    def test_priority_filter_selects_only_matching(self):
        add_task(self.store, "urgent", 1)
        add_task(self.store, "normal", 2)

        self.assertEqual(
            [task.title for task in list_tasks(self.store, priority=1)], ["urgent"]
        )

    def test_api_boolean_priority_is_rejected(self):
        with self.assertRaises(ValueError):
            add_task(self.store, "bool", True)
        task = add_task(self.store, "keep", 2)
        with self.assertRaises(ValueError):
            edit_task(self.store, task.id, priority=True)
        with self.assertRaises(ValueError):
            list_tasks(self.store, priority=True)

    def test_edit_updates_title_priority_due_and_tags(self):
        task = add_task(self.store, "old", 2)

        edited = edit_task(
            self.store, task.id, title="  new name ", priority=1,
            due="2026-12-01", tags=[" Work ", "home"],
        )

        self.assertEqual(edited.title, "new name")
        self.assertEqual(edited.priority, 1)
        self.assertEqual(edited.due, "2026-12-01")
        self.assertEqual(edited.tags, ["work", "home"])

    def test_edit_clear_due_and_tags(self):
        task = add_task(self.store, "t", 2, "2026-12-01", ["work"])

        edited = edit_task(self.store, task.id, clear_due=True, clear_tags=True)

        self.assertIsNone(edited.due)
        self.assertEqual(edited.tags, [])

    def test_locked_store_refuses_mutator_with_runtime_error(self):
        store = TaskStore(Path(self.directory.name) / "locked.json", lock_wait=0.05, retry_delay=0.001)
        lock = store.path.with_name(store.path.name + ".lock")
        lock.write_text("999999 whoever\n", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            add_task(store, "blocked", 2)
        self.assertEqual(store.load(), [])
        lock.unlink()

    def test_unusable_lock_path_fails_with_runtime_error(self):
        store = TaskStore(Path(self.directory.name) / "blocked.json", lock_wait=0.05, retry_delay=0.001)
        store.path.with_name(store.path.name + ".lock").mkdir()
        with self.assertRaises(RuntimeError):
            add_task(store, "denied", 2)
        self.assertEqual(store.load(), [])

    def test_stale_lock_is_broken_and_mutation_succeeds(self):
        store = TaskStore(Path(self.directory.name) / "stale.json", lock_wait=0.05, retry_delay=0.001)
        lock = store.path.with_name(store.path.name + ".lock")
        lock.write_text("999999 abandoned\n", encoding="utf-8")
        ancient = time.time() - 31.0
        os.utime(lock, (ancient, ancient))
        task = add_task(store, "recovered", 2)
        self.assertFalse(lock.exists())
        self.assertEqual([item.title for item in store.load()], ["recovered"])
        self.assertGreaterEqual(task.id, 1)

    def test_error_inside_transaction_releases_lock_and_writes_nothing(self):
        store = TaskStore(Path(self.directory.name) / "rollback.json", lock_wait=0.05, retry_delay=0.001)
        add_task(store, "one", 2)
        with self.assertRaises(ValueError):
            complete_task(store, 999)
        lock = store.path.with_name(store.path.name + ".lock")
        self.assertFalse(lock.exists())
        add_task(store, "two", 2)
        self.assertEqual([item.title for item in store.load()], ["one", "two"])

    def test_second_store_is_locked_out_while_a_transaction_is_open(self):
        path = Path(self.directory.name) / "contended.json"
        first = TaskStore(path, lock_wait=0.05, retry_delay=0.001)
        second = TaskStore(path, lock_wait=0.05, retry_delay=0.001)
        add_task(first, "one", 2)
        with first.transaction() as tasks:
            with self.assertRaises(RuntimeError):
                add_task(second, "refused", 2)
            self.assertNotIn("refused", [t.title for t in tasks])
        add_task(second, "two", 2)
        self.assertEqual([t.title for t in TaskStore(path).load()], ["one", "two"])
        self.assertFalse(path.with_name(path.name + ".lock").exists())

    def test_second_process_writer_wins_the_lock_after_release(self):
        path = Path(self.directory.name) / "handoff.json"
        first = TaskStore(path, lock_wait=0.05, retry_delay=0.001)
        with first.transaction() as tasks:
            tasks.append(Task(id=first.next_task_id(tasks), title="in-flight", priority=2, created_at=now()))
        reader = TaskStore(path)
        self.assertEqual([t.title for t in reader.load()], ["in-flight"])
        self.assertFalse(path.with_name(path.name + ".lock").exists())

    def test_list_limit_binds_after_sorting_and_rejects_non_positive(self):
        add_task(self.store, "low", 3)
        add_task(self.store, "high", 1)
        add_task(self.store, "mid", 2)
        limited = list_tasks(self.store, sort="priority", limit=2)
        self.assertEqual([task.title for task in limited], ["high", "mid"])
        with self.assertRaises(ValueError):
            list_tasks(self.store, limit=0)

    def test_next_task_returns_top_open_task_in_due_order(self):
        first = add_task(self.store, "first", 2, "2026-11-02")
        add_task(self.store, "laidate", 2, "2026-11-05")
        complete_task(self.store, first.id)
        top = add_task(self.store, "top", 2, "2026-11-01")
        self.assertEqual(next_task(self.store).id, top.id)

    def test_next_task_without_open_tasks_raises(self):
        with self.assertRaises(ValueError):
            next_task(self.store)

    def test_edit_noop_and_conflicts_raise(self):
        task = add_task(self.store, "t", 2)
        with self.assertRaises(ValueError):
            edit_task(self.store, task.id)
        with self.assertRaises(ValueError):
            edit_task(self.store, task.id, due="2026-12-01", clear_due=True)
        with self.assertRaises(ValueError):
            edit_task(self.store, task.id, tags=["a"], clear_tags=True)
        with self.assertRaises(ValueError):
            edit_task(self.store, 999, title="x")
        with self.assertRaises(ValueError):
            edit_task(self.store, task.id, title="   ")
        with self.assertRaises(ValueError):
            edit_task(self.store, task.id, priority=9)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store_path = str(Path(self.directory.name) / "tasks.json")

    def tearDown(self):
        self.directory.cleanup()

    def run_main(self, *argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--file", self.store_path, *argv])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_main_search_matches_title_and_tags_case_insensitively(self):
        self.run_main("add", "alpha", "--tag", "work")
        self.run_main("add", "beta")
        code, out, _ = self.run_main("list", "--search", "WORK")
        self.assertEqual(code, 0)
        self.assertIn("#1 P2 alpha (#work)", out)
        self.assertNotIn("beta", out)

    def test_main_sort_priority_orders_and_bad_sort_is_argparse_rejected(self):
        self.run_main("add", "low", "-p", "3")
        self.run_main("add", "high", "-p", "1")
        code, out, _ = self.run_main("list", "--sort", "priority")
        self.assertEqual(code, 0)
        high, low = out.index("high"), out.index("low")
        self.assertLess(high, low)
        with self.assertRaises(SystemExit) as raised:
            self.run_main("list", "--sort", "nonsense")
        self.assertEqual(raised.exception.code, 2)

    def test_main_stats_prints_summary_and_priorities(self):
        self.run_main("add", "alpha", "-p", "1")
        self.run_main("add", "low", "-p", "3")
        self.run_main("done", "2")
        code, out, _ = self.run_main("stats")
        self.assertEqual(code, 0)
        self.assertIn("Tasks: 2 (open 1, done 1, overdue 0)", out)
        self.assertIn("Priority: P1 1, P2 0, P3 1", out)

    def test_main_bad_priority_is_argparse_rejected_with_usage_error(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_main("add", "alpha", "-p", "9")
        self.assertEqual(raised.exception.code, 2)

    def test_main_next_prints_top_open_task_and_empty_store_fails_cleanly(self):
        self.run_main("add", "tomorrow", "-p", "2", "--due", "20261105")
        self.run_main("add", "urgent", "-p", "2", "--due", "20261101")
        code, out, _ = self.run_main("next")
        self.assertEqual(code, 0)
        self.assertIn("#2 P2 urgent (due 2026-11-01)", out)
        self.assertNotIn("tomorrow", out)
        self.run_main("rm", "1")
        self.run_main("done", "2")
        code, out, err = self.run_main("next")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Error: no open tasks", err)

    def test_main_stats_json_prints_parseable_summary(self):
        self.run_main("add", "alpha", "-p", "1")
        self.run_main("add", "low", "-p", "3")
        self.run_main("done", "2")
        code, out, err = self.run_main("stats", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        payload = json.loads(out)
        self.assertEqual(payload, {"tasks": 2, "open": 1, "done": 1, "overdue": 0, "by_priority": {"1": 1, "2": 0, "3": 1}})

    def test_main_all_overdue_and_tag_filters(self):
        overdue_yaml = (date.today() - timedelta(days=2)).isoformat()
        future_yaml = (date.today() + timedelta(days=30)).isoformat()
        self.run_main("add", "urgent", "-p", "1", "--due", future_yaml.replace("-", ""), "--tag", "work")
        self.run_main("add", "backlog", "-p", "3", "--tag", "home")
        self.run_main("add", "missed", "-p", "2", "--due", overdue_yaml.replace("-", ""))
        code, out, _ = self.run_main("list", "--tag", "work")
        self.assertEqual(code, 0)
        self.assertIn("urgent", out)
        self.assertNotIn("backlog", out)
        self.assertNotIn("[x]", out)
        code, out, _ = self.run_main("list", "--overdue")
        self.assertEqual(code, 0)
        self.assertIn("missed", out)
        self.assertNotIn("urgent", out)
        self.assertNotIn("backlog", out)
        code, out, _ = self.run_main("list", "--all", "--sort", "id")
        self.assertEqual(code, 0)
        for title in ("urgent", "backlog", "missed"):
            self.assertIn(title, out)

    def test_main_done_reopen_round_trip(self):
        self.run_main("add", "cycle", "-p", "2")
        _, out, _ = self.run_main("list")
        self.assertIn("[ ]", out)
        code, _, _ = self.run_main("done", "1")
        self.assertEqual(code, 0)
        _, out, _ = self.run_main("list")
        self.assertIn("No tasks.", out)
        _, out, _ = self.run_main("list", "--all")
        self.assertIn("[x] #1 P2 cycle", out)
        code, _, _ = self.run_main("reopen", "1")
        self.assertEqual(code, 0)
        _, out, _ = self.run_main("list")
        self.assertIn("[ ] #1 P2 cycle", out)

    def test_main_rm_removes_and_missing_id_fails(self):
        self.run_main("add", "keeper", "-p", "2")
        self.run_main("add", "goner", "-p", "3")
        code, out, _ = self.run_main("rm", "2")
        self.assertEqual(code, 0)
        _, out, _ = self.run_main("list")
        self.assertIn("keeper", out)
        self.assertNotIn("goner", out)
        code, out, err = self.run_main("delete", "2")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Error: task 2 was not found", err)

    def test_main_list_json_prints_one_parseable_line_of_records(self):
        self.run_main("add", "work item", "-p", "1", "--due", "today+3", "--tag", "work")
        self.run_main("add", "chore", "-p", "3")
        self.run_main("done", "1")
        code, out, err = self.run_main("list", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out.count("\n"), 1)
        payload = json.loads(out)
        self.assertEqual([record["title"] for record in payload], ["chore"])
        self.assertFalse(payload[0]["done"])
        self.assertIsNone(payload[0]["due"])

    def test_main_list_limit_caps_after_sorting(self):
        self.run_main("add", "low", "-p", "3")
        self.run_main("add", "high", "-p", "1")
        self.run_main("add", "mid", "-p", "2")
        code, out, _ = self.run_main("list", "--sort", "priority", "--limit", "2")
        self.assertEqual(code, 0)
        self.assertIn("high", out)
        self.assertIn("mid", out)
        self.assertNotIn("low", out)
        code, out, err = self.run_main("list", "--limit", "0")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Error: --limit must be a positive integer", err)

    def test_main_wait_zero_and_negative_are_respected_or_rejected(self):
        self.run_main("add", "seed", "-p", "2")
        lock = Path(self.store_path + ".lock")
        lock.write_text("999999 held\n", encoding="utf-8")
        code, out, err = self.run_main("--wait", "0", "add", "instant")
        self.assertEqual(code, 1)
        self.assertIn("Error: store is locked by another process", err)
        lock.unlink()
        store = TaskStore(Path(self.store_path))
        self.assertEqual([t.title for t in store.load()], ["seed"])
        code, out, err = self.run_main("--wait", "-1", "add", "bad")
        self.assertEqual(code, 1)
        self.assertIn("Error: --wait must be a non-negative number", err)

    def test_main_export_import_round_trip_and_error_paths(self):
        self.run_main("add", "first", "-p", "1", "--due", "today+4", "--tag", "work")
        second = self.run_main("add", "second", "-p", "3")
        self.run_main("done", "1")
        export_path = Path(self.directory.name) / "export-copy.json"
        code, out, _ = self.run_main("export", str(export_path))
        self.assertEqual(code, 0)
        self.assertIn("Exported 2 tasks", out)

        self.run_main("rm", "1")
        self.run_main("rm", "2")
        code, _, _ = self.run_main("import", str(export_path))
        self.assertEqual(code, 0)
        store = TaskStore(Path(self.store_path))
        tasks = store.load()
        self.assertEqual([t.title for t in tasks], ["first", "second"])
        self.assertTrue(tasks[0].done)
        self.assertEqual(tasks[0].due, (date.today() + timedelta(days=4)).isoformat())
        self.assertEqual(tasks[0].tags, ["work"])

        missing = Path(self.directory.name) / "absent.json"
        code, out, err = self.run_main("import", str(missing))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Error:", err)

        duplicate = Path(self.directory.name) / "duplicate.json"
        duplicate.write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, "next_id": 3, "tasks": [
                {"id": 1, "title": "a", "priority": 2, "done": False, "created_at": "2026-01-01T00:00:00+00:00",
                 "completed_at": None, "due": None, "tags": []},
                {"id": 1, "title": "b", "priority": 2, "done": False, "created_at": "2026-01-01T00:00:00+00:00",
                 "completed_at": None, "due": None, "tags": []},
            ]}),
            encoding="utf-8",
        )
        code, out, err = self.run_main("import", str(duplicate))
        self.assertEqual(code, 1)
        self.assertIn("Error:", err)
        self.assertIn("unique", err)
        store = TaskStore(Path(self.store_path))
        self.assertEqual(len(store.load()), 2)

    def test_main_relative_due_round_trips_through_add_and_edit(self):
        expected = (date.today() + timedelta(days=7)).isoformat()
        code, _, _ = self.run_main("add", "next-week", "-p", "1", "--due", "today+7")
        self.assertEqual(code, 0)
        self.assertEqual(TaskStore(Path(self.store_path)).load()[0].due, expected)
        edited = (date.today() + timedelta(days=2)).isoformat()
        code, _, _ = self.run_main("edit", "1", "--due", "today+2")
        self.assertEqual(code, 0)
        self.assertEqual(TaskStore(Path(self.store_path)).load()[0].due, edited)

    def test_main_added_task_is_persisted(self):
        code, _, _ = self.run_main("add", "persisted", "-p", "2")
        self.assertEqual(code, 0)
        store = TaskStore(Path(self.store_path))
        self.assertEqual([t.title for t in store.load()], ["persisted"])
        self.assertEqual(store.load()[0].priority, 2)


if __name__ == "__main__":
    unittest.main()
