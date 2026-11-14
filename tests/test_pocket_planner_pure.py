import unittest
from datetime import date, timedelta

from pocket_planner import (
    Task,
    _sort_key,
    canonical_due,
    normalize_tags,
    render_task,
    render_task_markdown,
    validate_due,
    validate_priority,
)


def make_task(**overrides):
    values = {
        "id": 1,
        "title": "task",
        "priority": 2,
        "done": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "completed_at": None,
        "due": None,
        "tags": [],
    }
    values.update(overrides)
    return Task(**values)


class PureTests(unittest.TestCase):
    """Function-level tests with no disk or lock interaction."""

    def test_validate_priority_accepts_and_rejects_levels(self):
        for good in (1, 2, 3):
            self.assertEqual(validate_priority(good), good)
        for bad in (0, 4, "2", None, True, False, 1.0):
            with self.assertRaises(ValueError):
                validate_priority(bad)

    def test_canonical_due_accepts_compact_and_iso(self):
        self.assertEqual(canonical_due("20260105"), "2026-01-05")
        self.assertEqual(canonical_due(" 2026-01-05 "), "2026-01-05")
        for bad in ("2026-1-5", "2026-W01-1", "not-a-date", "20261301"):
            with self.assertRaises(ValueError):
                canonical_due(bad)

    def test_validate_due_hands_none_and_blanks_through(self):
        self.assertIsNone(validate_due(None))
        self.assertIsNone(validate_due(""))
        self.assertIsNone(validate_due("   "))

    def test_validate_due_freezes_relative_forms_case_insensitively(self):
        cases = {
            "today": 0,
            "TODAY": 0,
            "today+7": 7,
            "today-2": -2,
            "Today+1": 1,
        }
        for value, days in cases.items():
            with self.subTest(value=value):
                self.assertEqual(
                    validate_due(value),
                    (date.today() + timedelta(days=days)).isoformat(),
                )
        self.assertEqual(validate_due("2026-01-05"), "2026-01-05")
        with self.assertRaises(ValueError):
            validate_due("tomorrow+1")

    def test_normalize_tags_strips_lowercases_and_dedupes_in_order(self):
        self.assertEqual(normalize_tags([" A ", "a", "B", "", "b"]), ["a", "b"])
        self.assertEqual(normalize_tags([]), [])
        self.assertEqual(normalize_tags(None), [])

    def test_render_task_marks_done_and_details(self):
        plain = make_task()
        self.assertEqual(render_task(plain), "[ ] #1 P2 task")
        full = make_task(done=True, due="2026-01-05", tags=["notes", "quick"])
        self.assertEqual(
            render_task(full),
            "[x] #1 P2 task (due 2026-01-05, #notes #quick)",
        )

    def test_render_task_markdown_uses_checklist_syntax(self):
        plain = make_task()
        self.assertEqual(render_task_markdown(plain), "- [ ] #1 P2 task")
        full = make_task(done=True, due="2026-01-05", tags=["notes"])
        self.assertEqual(
            render_task_markdown(full),
            "- [x] #1 P2 task (due 2026-01-05, #notes)",
        )

    def test_sort_key_by_due_sends_done_and_missing_due_last(self):
        by_due = _sort_key("due")
        tasks = [
            make_task(id=3, due=None),
            make_task(id=1, done=True, due="2026-01-01"),
            make_task(id=2, due="2026-01-01"),
        ]
        self.assertEqual([t.id for t in sorted(tasks, key=by_due)], [2, 3, 1])
        with self.assertRaises(ValueError):
            _sort_key("nope")
        by_priority = _sort_key("priority")
        self.assertEqual(
            [t.id for t in sorted([tasks[0], tasks[2]], key=by_priority)],
            [2, 3],
        )


if __name__ == "__main__":
    unittest.main()
