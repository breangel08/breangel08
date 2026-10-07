import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix=""):
    return prefix + uuid.uuid4().hex[:16]


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


class Conflict(Exception):
    pass


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.getenv("STUDIO_DATA_DIR", Path(__file__).resolve().parents[1] / "data")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.locks = {}
        self.lock_guard = threading.Lock()
        with self.db() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, project_id TEXT, timestamp TEXT, role TEXT, kind TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, status TEXT, attempt INTEGER, created_at TEXT, updated_at TEXT, error TEXT);
            CREATE INDEX IF NOT EXISTS event_project ON events(project_id, timestamp);
            CREATE UNIQUE INDEX IF NOT EXISTS active_project_job ON jobs(project_id) WHERE status IN ('QUEUED','RUNNING');
            """)

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.root / "studio.sqlite3", timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def lock(self, project_id):
        with self.lock_guard:
            return self.locks.setdefault(project_id, threading.RLock())

    def path(self, project_id):
        if not project_id.startswith("p_") or not project_id[2:].isalnum():
            raise KeyError("Invalid project ID")
        with self.db() as conn:
            row = conn.execute("SELECT data FROM projects WHERE id=?", (project_id,)).fetchone()
        fixture = bool(row and json.loads(row["data"]).get("fixture"))
        result = self.root / ("fixtures/projects" if fixture else "projects") / project_id
        result.mkdir(parents=True, exist_ok=True)
        return result

    def get(self, project_id):
        with self.db() as conn:
            row = conn.execute("SELECT data FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise KeyError("Project not found")
        return json.loads(row["data"])

    def list(self):
        with self.db() as conn:
            rows = conn.execute("SELECT data FROM projects").fetchall()
        return sorted([json.loads(row["data"]) for row in rows], key=lambda p: p["updated_at"], reverse=True)

    def save(self, project, event=None, role="Orchestrator"):
        previous = project.get("revision", 0)
        timestamp = now()
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT revision FROM projects WHERE id=?", (project["id"],)).fetchone()
            if current and current["revision"] != previous:
                raise Conflict("Project changed in another process; reload and retry")
            new = {**project, "revision": previous + 1, "updated_at": timestamp}
            conn.execute("INSERT INTO projects VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, revision=excluded.revision", (new["id"], json.dumps(new), new["revision"]))
            if event:
                conn.execute("INSERT INTO events VALUES(?,?,?,?,?,?)", (uid("e_"), new["id"], timestamp, role, event[0], json.dumps(event[1])))
        project.update(new)
        self.artifact(project["id"], "project.json", project)
        return project

    def events(self, project_id):
        with self.db() as conn:
            rows = conn.execute("SELECT * FROM events WHERE project_id=? ORDER BY timestamp DESC", (project_id,)).fetchall()
        return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    def artifact(self, project_id, name, data):
        path = self.path(project_id) / name
        if not path.resolve().is_relative_to(self.path(project_id).resolve()):
            raise ValueError("Invalid artifact path")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text(data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False))
        temp.replace(path)
        return path

    def create_job(self, project_id, kind):
        job_id = uid("j_")
        timestamp = now()
        try:
            with self.db() as conn:
                conn.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)", (job_id, project_id, kind, "QUEUED", 0, timestamp, timestamp, None))
        except sqlite3.IntegrityError:
            raise Conflict("This project already has an active job")
        return self.job(job_id)

    def job(self, job_id):
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError("Job not found")
        return dict(row)

    def jobs(self, project_id=None):
        with self.db() as conn:
            if project_id:
                rows = conn.execute("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def update_job(self, job_id, status, error=None, attempt=None):
        with self.db() as conn:
            conn.execute("UPDATE jobs SET status=?, error=?, updated_at=?, attempt=COALESCE(?,attempt) WHERE id=?", (status, error, now(), attempt, job_id))

    def claim_job(self, job_id):
        with self.db() as conn:
            changed = conn.execute("UPDATE jobs SET status='RUNNING', attempt=attempt+1, updated_at=? WHERE id=? AND status='QUEUED'", (now(), job_id)).rowcount
        return bool(changed)
