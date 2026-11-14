#!/usr/bin/env python3
"""Pocket Planner: a small local-first task manager."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass
class Task:
    id: int
    title: str
    priority: int = 2
    done: bool = False
    created_at: str = ""
    completed_at: str | None = None
    due: str | None = None
    tags: list[str] | None = None


class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._extras: dict[int, dict[str, object]] = {}
        self._next_id: int | None = None
        self._root_extras: dict[str, object] = {}

    def load(self) -> list[Task]:
        self._extras = {}
        self._next_id = None
        self._root_extras = {}
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("store root must be an object with a 'tasks' list")
            raw_tasks = data["tasks"]
            if not isinstance(raw_tasks, list):
                raise ValueError("'tasks' must be a list")
            self._root_extras = {
                key: value for key, value in data.items() if key not in ("tasks", "next_id")
            }
            stored_next = data.get("next_id")
            if stored_next is not None:
                if isinstance(stored_next, bool) or not isinstance(stored_next, int):
                    raise ValueError("next_id must be an integer")
                if stored_next < 1:
                    raise ValueError("next_id must be a positive integer")
                self._next_id = stored_next
            tasks = []
            seen_ids: set[int] = set()
            known = {"id", "title", "priority", "done", "created_at", "completed_at", "due", "tags"}
            for item in raw_tasks:
                if not isinstance(item, dict):
                    raise ValueError("each task must be an object")
                record = {key: value for key, value in item.items() if key in known}
                extras = {key: value for key, value in item.items() if key not in known}
                if extras and "id" in record:
                    self._extras[record["id"]] = extras
                record.setdefault("due", None)
                record.setdefault("tags", [])
                if isinstance(record.get("id"), bool) or not isinstance(record.get("id"), int):
                    raise ValueError("id must be an integer")
                if record["id"] in seen_ids:
                    raise ValueError("task ids must be unique")
                seen_ids.add(record["id"])
                if not isinstance(record.get("title"), str):
                    raise ValueError("title must be a string")
                priority = record.get("priority")
                if isinstance(priority, bool) or not isinstance(priority, int) or priority not in (1, 2, 3):
                    raise ValueError("priority must be 1, 2, or 3")
                if not isinstance(record.get("done"), bool):
                    raise ValueError("done must be true or false")
                if not isinstance(record.get("created_at"), str):
                    raise ValueError("created_at must be a string")
                if record.get("completed_at") is not None and not isinstance(record.get("completed_at"), str):
                    raise ValueError("completed_at must be a string or null")
                if record["due"] == "":
                    record["due"] = None
                if record["due"] is not None:
                    if not isinstance(record["due"], str):
                        raise ValueError("due must be a YYYY-MM-DD string or null")
                    record["due"] = validate_due(record["due"].strip())
                tags = record.get("tags")
                if tags is None:
                    record["tags"] = []
                elif isinstance(tags, list):
                    if any(not isinstance(entry, str) for entry in tags):
                        raise ValueError("tags must be a list of strings")
                    record["tags"] = normalize_tags(tags)
                else:
                    raise ValueError("tags must be a list of strings or null")
                tasks.append(Task(**record))
            return tasks
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(f"cannot read {self.path}: {error}") from error

    def next_task_id(self, tasks: list[Task]) -> int:
        """The next id this store issues; never an id a deleted task already used."""
        return max([self._next_id or 1] + [task.id + 1 for task in tasks])

    def save(self, tasks: list[Task]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = []
        for task in tasks:
            record = asdict(task)
            record.update(self._extras.get(task.id, {}))
            records.append(record)
        next_id = max([self._next_id or 0] + [task.id + 1 for task in tasks])
        self._next_id = next_id
        payload_data = {"next_id": next_id, "tasks": records}
        payload_data.update(self._root_extras)
        payload = json.dumps(payload_data, indent=2) + "\n"
        handle, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        except OSError as error:
            try:
                os.unlink(temporary)
            except OSError as cleanup_error:
                raise RuntimeError(
                    f"cannot save {self.path}: {error}; "
                    f"temporary-file cleanup also failed: {cleanup_error}"
                ) from error
            raise RuntimeError(f"cannot save {self.path}: {error}") from error


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_due(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("due date must use YYYY-MM-DD format") from error
    return value


def normalize_tags(tags: list[str] | None) -> list[str]:
    normalized = []
    for tag in tags or []:
        clean = tag.strip().lower()
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized


def add_task(
    store: TaskStore,
    title: str,
    priority: int,
    due: str | None = None,
    tags: list[str] | None = None,
) -> Task:
    title = " ".join(title.split())
    if not title:
        raise ValueError("task title cannot be empty")
    if isinstance(priority, bool) or not isinstance(priority, int) or priority not in (1, 2, 3):
        raise ValueError("priority must be 1, 2, or 3")
    due = validate_due(due)
    tasks = store.load()
    task = Task(
        id=store.next_task_id(tasks),
        title=title,
        priority=priority,
        created_at=now(),
        due=due,
        tags=normalize_tags(tags),
    )
    store.save(tasks + [task])
    return task


def complete_task(store: TaskStore, task_id: int) -> Task:
    tasks = store.load()
    for task in tasks:
        if task.id == task_id:
            if task.done:
                raise ValueError(f"task {task_id} is already complete")
            task.done = True
            task.completed_at = now()
            store.save(tasks)
            return task
    raise ValueError(f"task {task_id} was not found")


def reopen_task(store: TaskStore, task_id: int) -> Task:
    tasks = store.load()
    for task in tasks:
        if task.id == task_id:
            if not task.done:
                raise ValueError(f"task {task_id} is not complete")
            task.done = False
            task.completed_at = None
            store.save(tasks)
            return task
    raise ValueError(f"task {task_id} was not found")


def delete_task(store: TaskStore, task_id: int) -> Task:
    tasks = store.load()
    for task in tasks:
        if task.id == task_id:
            remaining = [item for item in tasks if item.id != task_id]
            store.save(remaining)
            return task
    raise ValueError(f"task {task_id} was not found")


def edit_task(
    store: TaskStore,
    task_id: int,
    title: str | None = None,
    priority: int | None = None,
    due: str | None = None,
    clear_due: bool = False,
    tags: list[str] | None = None,
    clear_tags: bool = False,
) -> Task:
    if title is None and priority is None and due is None and not clear_due and tags is None and not clear_tags:
        raise ValueError("nothing to edit: pass --title, --priority, --due/--clear-due, or --tag/--clear-tags")
    if due is not None and clear_due:
        raise ValueError("pass either --due or --clear-due, not both")
    if due is not None and not due.strip():
        raise ValueError("pass --clear-due to remove the due date")
    if tags is not None and clear_tags:
        raise ValueError("pass either --tag or --clear-tags, not both")
    tasks = store.load()
    for task in tasks:
        if task.id == task_id:
            if title is not None:
                cleaned = " ".join(title.split())
                if not cleaned:
                    raise ValueError("task title cannot be empty")
                task.title = cleaned
            if priority is not None:
                if isinstance(priority, bool) or not isinstance(priority, int) or priority not in (1, 2, 3):
                    raise ValueError("priority must be 1, 2, or 3")
                task.priority = priority
            if clear_due:
                task.due = None
            elif due is not None:
                task.due = validate_due(due)
            if clear_tags:
                task.tags = []
            elif tags is not None:
                task.tags = normalize_tags(tags)
            store.save(tasks)
            return task
    raise ValueError(f"task {task_id} was not found")


def list_tasks(
    store: TaskStore,
    include_done: bool = False,
    tag: str | None = None,
    overdue: bool = False,
    priority: int | None = None,
) -> list[Task]:
    tasks = store.load()
    visible = [task for task in tasks if include_done or not task.done]
    if tag:
        cleaned = tag.strip().lower()
        if cleaned:
            visible = [task for task in visible if cleaned in (task.tags or [])]
    if priority is not None:
        if isinstance(priority, bool) or not isinstance(priority, int) or priority not in (1, 2, 3):
            raise ValueError("priority must be 1, 2, or 3")
        visible = [task for task in visible if task.priority == priority]
    if overdue:
        today = date.today().isoformat()
        visible = [
            task
            for task in visible
            if task.due and task.due < today and not task.done
        ]
    return sorted(visible, key=lambda task: (task.done, task.due or "9999-12-31", task.priority, task.id))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage tasks in a local JSON file.")
    parser.add_argument("--file", type=Path, default=Path(".pocket-planner.json"))
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="create a task")
    add.add_argument("title", nargs="+")
    add.add_argument("-p", "--priority", type=int, default=2, choices=(1, 2, 3))
    add.add_argument("--due", help="due date in YYYY-MM-DD format")
    add.add_argument("--tag", action="append", default=[], help="tag (repeatable)")

    show = commands.add_parser("list", help="list tasks")
    show.add_argument("--all", action="store_true", dest="include_done")
    show.add_argument("--tag", help="only show tasks with this tag")
    show.add_argument("--overdue", action="store_true", help="only show overdue tasks")
    show.add_argument("--priority", type=int, choices=(1, 2, 3), help="only show this priority")
    done = commands.add_parser("done", help="complete a task")
    done.add_argument("id", type=int)
    reopen = commands.add_parser("reopen", help="reopen a completed task")
    reopen.add_argument("id", type=int)
    remove = commands.add_parser("rm", aliases=("delete",), help="delete a task")
    remove.add_argument("id", type=int)
    edit = commands.add_parser("edit", help="edit task title, priority, due date, or tags")
    edit.add_argument("id", type=int)
    edit.add_argument("--title", nargs="+", default=None, help="new title")
    edit.add_argument("--priority", type=int, choices=(1, 2, 3), default=None)
    edit.add_argument("--due", default=None, help="new due date in YYYY-MM-DD format")
    edit.add_argument("--clear-due", action="store_true", help="remove the due date")
    edit.add_argument("--tag", action="append", default=None, dest="tags", help="replacement tag (repeatable)")
    edit.add_argument("--clear-tags", action="store_true", help="remove all tags")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = TaskStore(args.file)
    try:
        if args.command == "add":
            task = add_task(store, " ".join(args.title), args.priority, args.due, args.tag)
            print(f"Added #{task.id}: {task.title} (priority {task.priority})")
        elif args.command == "done":
            task = complete_task(store, args.id)
            print(f"Completed #{task.id}: {task.title}")
        elif args.command == "reopen":
            task = reopen_task(store, args.id)
            print(f"Reopened #{task.id}: {task.title}")
        elif args.command in ("rm", "delete"):
            task = delete_task(store, args.id)
            print(f"Deleted #{task.id}: {task.title}")
        elif args.command == "edit":
            title = " ".join(args.title) if args.title is not None else None
            task = edit_task(
                store,
                args.id,
                title=title,
                priority=args.priority,
                due=args.due,
                clear_due=args.clear_due,
                tags=args.tags,
                clear_tags=args.clear_tags,
            )
            print(f"Edited #{task.id}: {task.title}")
        elif args.command == "list":
            tasks = list_tasks(store, args.include_done, args.tag, args.overdue, args.priority)
            if not tasks:
                print("No tasks.")
            for task in tasks:
                marker = "x" if task.done else " "
                details = []
                if task.due:
                    details.append(f"due {task.due}")
                if task.tags:
                    details.append(" ".join(f"#{tag}" for tag in task.tags))
                suffix = f" ({', '.join(details)})" if details else ""
                print(f"[{marker}] #{task.id} P{task.priority} {task.title}{suffix}")
        else:
            raise ValueError(f"unknown command {args.command!r}")
        return 0
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
