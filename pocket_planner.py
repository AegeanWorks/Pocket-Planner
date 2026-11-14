#!/usr/bin/env python3
"""Pocket Planner: a small local-first task manager."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

SCHEMA_VERSION = 2


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
    def __init__(
        self,
        path: Path,
        *,
        replace_tries: int = 5,
        retry_delay: float = 0.05,
        lock_wait: float = 3.0,
        stale_after: float = 30.0,
    ) -> None:
        self.path = path
        self.replace_tries = replace_tries
        self.retry_delay = retry_delay
        self.lock_wait = lock_wait
        self.stale_after = stale_after
        self._lock_held = False
        self._extras: dict[int, dict[str, object]] = {}
        self._next_id: int | None = None
        self._root_extras: dict[str, object] = {}

    @property
    def _backup_path(self) -> Path:
        return self.path.with_name(self.path.name + ".bak")

    @property
    def _rotated_backup_path(self) -> Path:
        return self.path.with_name(self.path.name + ".bak.1")

    @property
    def _lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    def _acquire_lock(self) -> None:
        if self._lock_held:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._lock_path
        deadline = time.monotonic() + self.lock_wait
        while True:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime > self.stale_after:
                        lock_path.unlink()
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"store is locked by another process: {lock_path}")
                time.sleep(self.retry_delay)
                continue
            self._lock_held = True
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(f"{os.getpid()} {now()}\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as error:
                self._lock_held = False
                with contextlib.suppress(OSError):
                    lock_path.unlink()
                raise RuntimeError(f"cannot create lock {lock_path}: {error}") from error
            return

    def _release_lock(self) -> None:
        if not self._lock_held:
            return
        self._lock_held = False
        with contextlib.suppress(OSError):
            self._lock_path.unlink()

    @contextlib.contextmanager
    def transaction(self):
        """Lock, load, yield the task list, save on a clean exit, release always.

        The single lock file assumes one writer per process; nested
        transaction calls inside one process reuse the held lock.
        """
        self._acquire_lock()
        try:
            tasks = self.load()
            yield tasks
            self.save(tasks)
        finally:
            self._release_lock()

    def load(self) -> list[Task]:
        self._extras = {}
        self._next_id = None
        self._root_extras = {}
        source = self.path
        if not source.exists():
            source = self._backup_path
            if not source.exists():
                return []
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("store root must be an object with a 'tasks' list")
            raw_tasks = data["tasks"]
            if not isinstance(raw_tasks, list):
                raise ValueError("'tasks' must be a list")
            self._root_extras = {
                key: value
                for key, value in data.items()
                if key not in ("tasks", "next_id", "schema_version")
            }
            stored_schema = data.get("schema_version")
            if stored_schema is not None:
                if isinstance(stored_schema, bool) or not isinstance(stored_schema, int) or stored_schema < 1:
                    raise ValueError("schema_version must be a positive integer")
                if stored_schema > SCHEMA_VERSION:
                    raise ValueError(
                        f"schema_version {stored_schema} is newer than this version supports ({SCHEMA_VERSION})"
                    )
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
                validate_priority(record.get("priority"))
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
                    record["due"] = canonical_due(record["due"].strip())
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
            raise RuntimeError(f"cannot read {source}: {error}") from error

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
        payload_data = {"schema_version": SCHEMA_VERSION, "next_id": next_id, "tasks": records}
        payload_data.update(self._root_extras)
        payload = json.dumps(payload_data, indent=2) + "\n"
        if self.path.exists():
            backup_path = self._backup_path
            if backup_path.exists():
                os.replace(backup_path, self._rotated_backup_path)
            os.replace(self.path, backup_path)
        handle, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            for attempt in range(self.replace_tries):
                try:
                    os.replace(temporary, self.path)
                    break
                except OSError as error:
                    if attempt == self.replace_tries - 1:
                        raise
                    time.sleep(self.retry_delay)
            self._sync_directory()
        except OSError as error:
            try:
                os.unlink(temporary)
            except OSError as cleanup_error:
                raise RuntimeError(
                    f"cannot save {self.path}: {error}; "
                    f"temporary-file cleanup also failed: {cleanup_error}"
                ) from error
            raise RuntimeError(f"cannot save {self.path}: {error}") from error

    def _sync_directory(self) -> None:
        # Best effort. POSIX needs the fsync so the rename survives power loss;
        # Windows refuses a directory flush (and cannot open one reliably), so the
        # entry there follows the file's own fsync. A silent skip keeps an already
        # replaced store from turning into an error.
        if os.name == "nt":
            return
        try:
            descriptor = os.open(self.path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:  # hygiene: allow POSIX dir fsync is best effort; the store file already replaced atomically
            pass
        finally:
            os.close(descriptor)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_priority(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (1, 2, 3):
        raise ValueError("priority must be 1, 2, or 3")
    return value


def canonical_due(value: str) -> str:
    compact = value.strip()
    if len(compact) == 8 and compact.isdigit():
        compact = f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    if len(compact) != 10 or compact[4] != "-" or compact[7] != "-":
        raise ValueError("due date must use YYYY-MM-DD format, or a relative form like today+N")
    try:
        date.fromisoformat(compact)
    except ValueError as error:
        raise ValueError("due date must use YYYY-MM-DD format, or a relative form like today+N") from error
    return compact


RELATIVE_DUE_PATTERN = re.compile(r"today(?P<days>[+-]\d+)?", re.IGNORECASE)


def validate_due(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    relative = RELATIVE_DUE_PATTERN.fullmatch(value)
    if relative:
        days = int(relative.group("days") or 0)
        return (date.today() + timedelta(days=days)).isoformat()
    return canonical_due(value)


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
    priority = validate_priority(priority)
    due = validate_due(due)
    with store.transaction() as tasks:
        task = Task(
            id=store.next_task_id(tasks),
            title=title,
            priority=priority,
            created_at=now(),
            due=due,
            tags=normalize_tags(tags),
        )
        tasks.append(task)
        return task


def complete_task(store: TaskStore, task_id: int) -> Task:
    with store.transaction() as tasks:
        for task in tasks:
            if task.id == task_id:
                if task.done:
                    raise ValueError(f"task {task_id} is already complete")
                task.done = True
                task.completed_at = now()
                return task
        raise ValueError(f"task {task_id} was not found")


def reopen_task(store: TaskStore, task_id: int) -> Task:
    with store.transaction() as tasks:
        for task in tasks:
            if task.id == task_id:
                if not task.done:
                    raise ValueError(f"task {task_id} is not complete")
                task.done = False
                task.completed_at = None
                return task
        raise ValueError(f"task {task_id} was not found")


def delete_task(store: TaskStore, task_id: int) -> Task:
    with store.transaction() as tasks:
        for task in tasks:
            if task.id == task_id:
                tasks[:] = [item for item in tasks if item.id != task_id]
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
    with store.transaction() as tasks:
        for task in tasks:
            if task.id == task_id:
                if title is not None:
                    cleaned = " ".join(title.split())
                    if not cleaned:
                        raise ValueError("task title cannot be empty")
                    task.title = cleaned
                if priority is not None:
                    task.priority = validate_priority(priority)
                if clear_due:
                    task.due = None
                elif due is not None:
                    task.due = validate_due(due)
                if clear_tags:
                    task.tags = []
                elif tags is not None:
                    task.tags = normalize_tags(tags)
                return task
        raise ValueError(f"task {task_id} was not found")


SORT_KEYS = ("due", "priority", "id", "created")


def _sort_key(name: str):
    if name == "priority":
        return lambda task: (task.priority, task.due or "9999-12-31", task.id)
    if name == "id":
        return lambda task: (task.id,)
    if name == "created":
        return lambda task: (task.created_at, task.id)
    if name == "due":
        return lambda task: (task.done, task.due or "9999-12-31", task.priority, task.id)
    raise ValueError(f"sort must be one of {', '.join(SORT_KEYS)}")


def list_tasks(
    store: TaskStore,
    include_done: bool = False,
    tag: str | None = None,
    overdue: bool = False,
    priority: int | None = None,
    query: str | None = None,
    sort: str = "due",
) -> list[Task]:
    tasks = store.load()
    visible = [task for task in tasks if include_done or not task.done]
    if tag:
        cleaned = tag.strip().lower()
        if cleaned:
            visible = [task for task in visible if cleaned in (task.tags or [])]
    if priority is not None:
        validate_priority(priority)
        visible = [task for task in visible if task.priority == priority]
    if query:
        needle = query.strip().lower()
        if needle:
            visible = [
                task
                for task in visible
                if needle in task.title.lower()
                or any(needle in entry.lower() for entry in (task.tags or []))
            ]
    if overdue:
        today = date.today().isoformat()
        visible = [
            task
            for task in visible
            if task.due and task.due < today and not task.done
        ]
    return sorted(visible, key=_sort_key(sort))


def next_task(store: TaskStore) -> Task:
    open_tasks = list_tasks(store)
    if not open_tasks:
        raise ValueError("no open tasks")
    return open_tasks[0]


class Stats(NamedTuple):
    tasks: int
    open: int
    done: int
    overdue: int
    by_priority: dict[int, int]


def task_stats(store: TaskStore) -> Stats:
    tasks = store.load()
    today = date.today().isoformat()
    by_priority = {1: 0, 2: 0, 3: 0}
    done_count = 0
    overdue_count = 0
    for task in tasks:
        by_priority[task.priority] = by_priority.get(task.priority, 0) + 1
        if task.done:
            done_count += 1
        elif task.due and task.due < today:
            overdue_count += 1
    return Stats(
        tasks=len(tasks),
        open=len(tasks) - done_count,
        done=done_count,
        overdue=overdue_count,
        by_priority=by_priority,
    )


def render_task(task: Task) -> str:
    marker = "x" if task.done else " "
    details = []
    if task.due:
        details.append(f"due {task.due}")
    if task.tags:
        details.append(" ".join(f"#{tag}" for tag in task.tags))
    suffix = f" ({', '.join(details)})" if details else ""
    return f"[{marker}] #{task.id} P{task.priority} {task.title}{suffix}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage tasks in a local JSON file.")
    parser.add_argument("--file", type=Path, default=Path(".pocket-planner.json"))
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="create a task")
    add.add_argument("title", nargs="+")
    add.add_argument("-p", "--priority", type=int, default=2, choices=(1, 2, 3))
    add.add_argument("--due", help="due date in YYYY-MM-DD or YYYYMMDD format, or today, today+N")
    add.add_argument("--tag", action="append", default=[], help="tag (repeatable)")

    show = commands.add_parser("list", help="list tasks")
    show.add_argument("--all", action="store_true", dest="include_done")
    show.add_argument("--tag", help="only show tasks with this tag")
    show.add_argument("--overdue", action="store_true", help="only show overdue tasks")
    show.add_argument("--priority", type=int, choices=(1, 2, 3), help="only show this priority")
    show.add_argument("--search", help="only show tasks whose title or tags contain this text")
    show.add_argument("--sort", choices=SORT_KEYS, default="due", help="order by due, priority, id, or created")
    stats = commands.add_parser("stats", help="summarize the store")
    stats.add_argument("--json", action="store_true", help="print the summary as JSON")
    next_cmd = commands.add_parser("next", help="show the top open task")
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
    edit.add_argument("--due", default=None, help="new due date in YYYY-MM-DD or YYYYMMDD format, or today, today+N")
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
            tasks = list_tasks(
                store,
                args.include_done,
                args.tag,
                args.overdue,
                args.priority,
                args.search,
                args.sort,
            )
            if not tasks:
                print("No tasks.")
            for task in tasks:
                print(render_task(task))
        elif args.command == "next":
            print(render_task(next_task(store)))
        elif args.command == "stats":
            summary = task_stats(store)
            if args.json:
                print(
                    json.dumps(
                        {
                            "tasks": summary.tasks,
                            "open": summary.open,
                            "done": summary.done,
                            "overdue": summary.overdue,
                            "by_priority": summary.by_priority,
                        }
                    )
                )
            else:
                priorities = ", ".join(f"P{level} {count}" for level, count in summary.by_priority.items())
                print(
                    f"Tasks: {summary.tasks} (open {summary.open}, done {summary.done}, "
                    f"overdue {summary.overdue})"
                )
                print(f"Priority: {priorities}")
        else:
            raise ValueError(f"unknown command {args.command!r}")
        return 0
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
