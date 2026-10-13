"""Bounded operational history and lifecycle snapshots on a local SQLite volume."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class OperationalStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS events_kind ON events(kind, id)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS snapshots (key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def append(self, kind: str, payload: dict, limit: int) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(kind,payload) VALUES (?,?)",
                (kind, json.dumps(payload, allow_nan=False)),
            )
            db.execute(
                "DELETE FROM events WHERE kind=? AND id NOT IN (SELECT id FROM events WHERE kind=? ORDER BY id DESC LIMIT ?)",
                (kind, kind, limit),
            )

    def recent(self, kind: str, limit: int) -> list[dict]:
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM events WHERE kind=? ORDER BY id DESC LIMIT ?",
                    (kind, limit),
                )
            ]

    def save_lifecycle(self, payload: dict) -> None:
        encoded = json.dumps(payload, allow_nan=False)
        operation_id = payload.get("operation_id")
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO snapshots VALUES ('lifecycle',?)", (encoded,))
            if operation_id:
                db.execute(
                    "INSERT OR REPLACE INTO snapshots VALUES (?,?)",
                    ("operation:" + operation_id, encoded),
                )
                db.execute(
                    "DELETE FROM snapshots WHERE key LIKE 'operation:%' AND rowid NOT IN (SELECT rowid FROM snapshots WHERE key LIKE 'operation:%' ORDER BY rowid DESC LIMIT 100)"
                )

    def lifecycle(self) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM snapshots WHERE key='lifecycle'").fetchone()
            return json.loads(row[0]) if row else {}

    def operations(self) -> list[dict]:
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM snapshots WHERE key LIKE 'operation:%' ORDER BY rowid DESC LIMIT 100"
                )
            ]
