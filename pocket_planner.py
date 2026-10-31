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

    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            tasks = []
            for item in data["tasks"]:
                record = dict(item)
                record.setdefault("due", None)
                record.setdefault("tags", [])
                tasks.append(Task(**record))
            return tasks
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(f"cannot read {self.path}: {error}") from error

    def save(self, tasks: list[Task]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"tasks": [asdict(task) for task in tasks]}, indent=2) + "\n"
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
    if priority not in (1, 2, 3):
        raise ValueError("priority must be 1, 2, or 3")
    due = validate_due(due)
    tasks = store.load()
    task = Task(
        id=max((item.id for item in tasks), default=0) + 1,
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


def list_tasks(
    store: TaskStore,
    include_done: bool = False,
    tag: str | None = None,
    overdue: bool = False,
) -> list[Task]:
    tasks = store.load()
    visible = [task for task in tasks if include_done or not task.done]
    if tag:
        tag = tag.strip().lower()
        visible = [task for task in visible if tag in (task.tags or [])]
    if overdue:
        today = date.today().isoformat()
        visible = [task for task in visible if task.due and task.due < today]
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
    done = commands.add_parser("done", help="complete a task")
    done.add_argument("id", type=int)
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
        else:
            tasks = list_tasks(store, args.include_done, args.tag, args.overdue)
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
        return 0
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
