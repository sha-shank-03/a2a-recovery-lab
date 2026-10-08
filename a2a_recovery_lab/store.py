"""One agent per SQLite database; atomic initial-submission deduplication."""

import hashlib
import base64
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import EXECUTION_MODE
from .wire import TERMINAL, WireError, canonical


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TaskStore:
    def __init__(self, path, owner):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS owner (name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS submissions (
                    message_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                    task_id TEXT NOT NULL REFERENCES tasks(id));
            """)
            row = db.execute("SELECT name FROM owner").fetchone()
            if row and row[0] != owner:
                raise ValueError("Database belongs to another agent")
            if not row:
                db.execute("INSERT INTO owner VALUES (?)", (owner,))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_or_get(self, message, deduplicate=True):
        fingerprint = hashlib.sha256(canonical(message).encode("utf-8")).hexdigest()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT fingerprint, task_id FROM submissions WHERE message_id=?",
                                  (message["messageId"],)).fetchone()
            if previous and deduplicate:
                if previous[0] != fingerprint:
                    raise WireError(-32602, "Message ID reused with changed content", "message.messageId")
                body = db.execute("SELECT body FROM tasks WHERE id=?", (previous[1],)).fetchone()[0]
                return json.loads(body), False
            task = {"id": str(uuid.uuid4()),
                    "contextId": message.get("contextId") or str(uuid.uuid4()),
                    "status": {"state": "TASK_STATE_SUBMITTED", "timestamp": timestamp()},
                    "history": [message], "metadata": {"executionMode": EXECUTION_MODE}}
            db.execute("INSERT INTO tasks VALUES (?,?)", (task["id"], canonical(task)))
            if deduplicate:
                db.execute("INSERT INTO submissions VALUES (?,?,?)",
                           (message["messageId"], fingerprint, task["id"]))
            return task, True

    def get(self, task_id, history_length=None):
        with self.connection() as db:
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise WireError(-32001, "Task does not exist in this agent's store")
        task = json.loads(row[0])
        if history_length == 0:
            task.pop("history", None)
        elif history_length is not None:
            task["history"] = task.get("history", [])[-history_length:]
        return task

    def update(self, task_id, *, state=None, artifacts=None, metadata=None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                raise WireError(-32001, "Task does not exist in this agent's store")
            task = json.loads(row[0])
            if task["status"]["state"] in TERMINAL:
                return False
            if state:
                task["status"] = {"state": state, "timestamp": timestamp()}
            if artifacts is not None:
                task["artifacts"] = artifacts
            if metadata:
                task["metadata"].update(metadata)
            db.execute("UPDATE tasks SET body=? WHERE id=?", (canonical(task), task_id))
            return True

    def cancel(self, task_id):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                raise WireError(-32001, "Task does not exist in this agent's store")
            task = json.loads(row[0])
            if task["status"]["state"] == "TASK_STATE_CANCELED":
                return task, False
            if task["status"]["state"] in TERMINAL:
                raise WireError(-32002, "Task already reached a noncancelable terminal state")
            task["status"] = {"state": "TASK_STATE_CANCELED", "timestamp": timestamp()}
            task.pop("artifacts", None)
            task["metadata"]["cancelRequested"] = True
            db.execute("UPDATE tasks SET body=? WHERE id=?", (canonical(task), task_id))
            return task, True

    def annotate_policy(self, task_id, metadata):
        allowed = {"remoteCancellation", "recoveryOutcome", "remoteOutcome", "cancelRequested",
                   "submissionAttempts", "submissionStarted", "retrievalAttempts", "cancellationAttempts", "peerDeduplicationAssumed", "unsafeRetry"}
        if not set(metadata) <= allowed:
            raise ValueError("Terminal-safe annotation accepts policy fields only")
        self._metadata(task_id, metadata)

    def link_child(self, task_id, child_id, peer):
        # Record an acknowledged child even when cancellation raced its submission.
        self._metadata(task_id, {"childTaskId": child_id, "childAgentUrl": peer})

    def _metadata(self, task_id, metadata):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                raise WireError(-32001, "Unknown task")
            task = json.loads(row[0])
            if "childTaskId" in metadata and task["metadata"].get("childTaskId") not in (None, metadata["childTaskId"]):
                raise ValueError("Cannot replace an acknowledged child link")
            task["metadata"].update(metadata)
            db.execute("UPDATE tasks SET body=? WHERE id=?", (canonical(task), task_id))

    def list_tasks(self, options):
        with self.connection() as db:
            tasks = [json.loads(row[0]) for row in db.execute("SELECT body FROM tasks")]
        if options["context"]:
            tasks = [task for task in tasks if task["contextId"] == options["context"]]
        if options["state"]:
            tasks = [task for task in tasks if task["status"]["state"] == options["state"]]
        if options["after"] is not None:
            tasks = [task for task in tasks if datetime.fromisoformat(task["status"]["timestamp"].replace("Z", "+00:00")).timestamp() >= options["after"]]
        key = lambda task: (task["status"]["timestamp"], task["id"])
        tasks.sort(key=key, reverse=True)
        total = len(tasks)
        filters = hashlib.sha256(canonical({k: options[k] for k in ("context", "state", "after")}).encode()).hexdigest()
        if options["token"]:
            try:
                token = json.loads(base64.b64decode(options["token"], altchars=b"-_", validate=True))
                if token["v"] != 1 or token["filters"] != filters or len(token["last"]) != 2 or any(not isinstance(value, str) for value in token["last"]):
                    raise ValueError("Invalid cursor")
                last = tuple(token["last"])
                tasks = [task for task in tasks if key(task) < last]
            except (ValueError, KeyError, TypeError) as exc:
                raise WireError(-32602, "Invalid page token or changed filters", "pageToken") from exc
        page = tasks[:options["size"]]
        next_token = ""
        if len(tasks) > len(page):
            next_token = base64.urlsafe_b64encode(canonical({"v": 1, "filters": filters, "last": key(page[-1])}).encode()).decode()
        for task in page:
            if not options["include_artifacts"]:
                task.pop("artifacts", None)
            else:
                task.setdefault("artifacts", [])
            if options["history"] == 0:
                task.pop("history", None)
            elif options["history"] is not None:
                task["history"] = task.get("history", [])[-options["history"]:]
        return {"tasks": page, "nextPageToken": next_token, "pageSize": options["size"], "totalSize": total}

    def count(self):
        with self.connection() as db:
            return db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
