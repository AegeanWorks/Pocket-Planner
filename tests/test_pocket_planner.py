import json
import tempfile
import unittest
from pathlib import Path

from pocket_planner import TaskStore, add_task, complete_task, list_tasks


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


if __name__ == "__main__":
    unittest.main()
