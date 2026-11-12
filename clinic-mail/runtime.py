"""Shared run-time helpers for the clinic services: clock, database, internal mail delivery."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path


class Clock:
    """Business time: the prepared state time plus wall time elapsed since the services started.

    The anchor is written once per run, so the platform and the relay agree on the time.
    """

    def __init__(self, state: Path):
        self.service = json.loads((state / "service.json").read_text())
        anchor = state / "clock.json"
        if not anchor.exists():
            try:
                with anchor.open("x") as f:
                    json.dump({"real": time.time(), "virtual": self.service["state_as_of"]}, f)
            except FileExistsError:
                pass
        data = json.loads(anchor.read_text())
        self.real = data["real"]
        self.virtual = datetime.fromisoformat(data["virtual"])

    def now(self) -> datetime:
        return (self.virtual + timedelta(seconds=time.time() - self.real)).replace(microsecond=0)

    def iso(self) -> str:
        return self.now().isoformat(timespec="seconds")


def connect(state: Path) -> sqlite3.Connection:
    db = sqlite3.connect(state / "clinic.sqlite", timeout=20, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=20000")
    return db


def deliver_internal(db: sqlite3.Connection, when: str, sender: str, to: str, subject: str, body: str, folder: str = "inbox"):
    """Put a message into the agent's mailbox (inbox for received mail, sent for its own)."""
    mid = f"<{uuid.uuid4().hex[:20]}@euryla.uk>"
    db.execute("INSERT INTO mailbox (folder,message_id,sent_at,sender,recipients,subject,body,unread) VALUES (?,?,?,?,?,?,?,?)",
               (folder, mid, when, sender, to, subject, body, 1 if folder == "inbox" else 0))
