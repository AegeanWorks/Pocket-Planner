import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pocket_planner import (
    Stats,
    TaskStore,
    add_task,
    complete_task,
    delete_task,
    edit_task,
    list_tasks,
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
            '{"schema_version": 9, "tasks": [{"id": 1, "title": "rooted", "priority": 2, '
            '"done": false, "created_at": "x"}]}',
            encoding="utf-8",
        )

        add_task(self.store, "new task", 2)

        payload = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 9)
        self.assertEqual(payload["next_id"], 3)

    def test_save_keeps_a_bak_of_the_previous_store(self):
        add_task(self.store, "one", 2)
        add_task(self.store, "two", 2)

        backup = self.store.path.with_name(self.store.path.name + ".bak")
        payload = json.loads(backup.read_text(encoding="utf-8"))

        self.assertEqual([item["title"] for item in payload["tasks"]], ["one"])

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


if __name__ == "__main__":
    unittest.main()
