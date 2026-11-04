import json
import tempfile
import unittest
from pathlib import Path

from pocket_planner import (
    TaskStore,
    add_task,
    complete_task,
    delete_task,
    list_tasks,
    reopen_task,
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


if __name__ == "__main__":
    unittest.main()
