"""Authorization register service: the office behind the `pa` command (HTTP, standard library).

  python3 service.py --data STATE_DIR [--bind 127.0.0.1] [--port 8766]

Every call is logged in api_log with a sequence number, the arguments, the output and which records were shown.
Mail (notices to pharmacies and ordinary mail) goes through the internal relay (smtp_relay.py, started here), which
stores it and delivers nothing outside.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import views

SMTP_PORT = int(os.environ.get("PA_SMTP_PORT", "25"))  # 25 in the office container; any port for local checks


class Clock:
    """Business time: prepared state time plus wall time elapsed since the anchor was first written."""

    def __init__(self, state: Path, svc: dict):
        anchor = state / "clock.json"
        if not anchor.exists():
            try:
                with anchor.open("x") as f:
                    json.dump({"real": time.time(), "virtual": svc["state_as_of"]}, f)
            except FileExistsError:
                pass
        data = json.loads(anchor.read_text())
        self.real, self.virtual = data["real"], datetime.fromisoformat(data["virtual"])

    def iso(self) -> str:
        return (self.virtual + timedelta(seconds=time.time() - self.real)).replace(microsecond=0).isoformat()


class Office:
    def __init__(self, state: Path):
        self.svc = json.loads((state / "service.json").read_text())
        self.clock = Clock(state, self.svc)
        self.run = date.fromisoformat(self.svc["run_date"])
        self.db = sqlite3.connect(state / "pa.sqlite", check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()

    Q = ("SELECT o.*, p.name AS pharmacy_name, p.city AS pharmacy_city, p.email AS pharmacy_email FROM overrides o "
         "JOIN pharmacies p ON p.key=o.pharmacy")

    def get(self, ident: str):
        return self.db.execute(self.Q + " WHERE o.id=?", (ident.strip().upper(),)).fetchone()

    def notes(self, ident: str):
        return self.db.execute("SELECT * FROM notes WHERE override_id=? ORDER BY at", (ident,)).fetchall()

    def smtp(self, to: list[str], subject: str, body: str):
        """Hand one message to the relay; its refusals come back as errors."""
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = f"pa-ops@{self.svc['domain']}", ", ".join(to), subject
        m["Date"] = formatdate(localtime=True)
        m["Message-ID"] = make_msgid(domain=self.svc["domain"])
        m.set_content(body)
        try:
            with smtplib.SMTP("127.0.0.1", SMTP_PORT, local_hostname="pa-gw.halvard.internal", timeout=15) as s:
                s.send_message(m)
        except smtplib.SMTPRecipientsRefused as e:
            raise ValueError("; ".join(f"{a}: {c} {r.decode(errors='replace')}" for a, (c, r) in e.recipients.items()))
        except smtplib.SMTPResponseException as e:
            raise ValueError(f"{e.smtp_code} {e.smtp_error.decode(errors='replace')}")

    def due(self):
        return self.db.execute(self.Q + " WHERE o.status IN ('revoke_today','held') AND o.revoke_on=? ORDER BY o.position",
                               (self.run.isoformat(),)).fetchall()

    def pending(self):
        return [o for o in self.due() if o["status"] == "revoke_today" and not o["notified_at"]]

    # ---------------------------------------------------------------- commands
    def status(self, a):
        rows = self.due()
        sent = sum(1 for o in rows if o["notified_at"])
        held = sum(1 for o in rows if o["status"] == "held")
        return (f"{self.svc['company']} authorization register | {self.clock.iso().replace('T', ' ')} (Central)\n"
                f"Account: pa-ops (pharmacy authorization operations: overrides, pharmacy notices, mail)\n"
                f"Revocations effective today: {len(rows)}; pharmacy notices sent {sent}, held {held}, "
                f"not sent {len(rows) - sent - held}; send by {self.svc['batch_at'][11:16]}")

    def register(self, a):
        q = self.Q + (" WHERE o.revoke_on IS NOT NULL" if a.get("revocations") else "") + " ORDER BY o.position"
        rows = self.db.execute(q).fetchall()
        lines = [f"Quantity limit overrides: {len(rows)}" + (" (revocations effective today)" if a.get("revocations") else ""),
                 f"{'#':>3}  {'id':<13} {'member':<22} {'drug':<34} {'granted':<11} {'through':<11} {'notes':<6} state"]
        for o in rows:
            n = len(self.notes(o["id"]))
            lines.append(f"{o['position']:>3}  {o['id']:<13} {o['member'][:22]:<22} {o['drug'][:34]:<34} "
                         f"{views.us(o['granted_on']):<11} {views.us(o['through']):<11} {n or '-':<6} "
                         f"{views.state_of(o)}")
        return "\n".join(lines)

    def show(self, a, shown: list):
        out = []
        for ident in a["ids"]:
            o = self.get(ident)
            if not o:
                raise ValueError(f"no override {ident}")
            shown.append(o["id"])
            out.append(views.record(o, self.notes(o["id"])))
        return "\n\n".join(out)

    def hold(self, a):
        o = self.get(a["id"])
        if not o:
            raise ValueError(f"no override {a['id']}")
        if not a.get("reason", "").strip():
            raise ValueError("--reason is required")
        if o["notified_at"]:
            raise ValueError(f"the notice for {o['id']} was sent to {o['pharmacy_name']} at {o['notified_at'][11:16]}; "
                             "a sent notice is not recalled")
        if o["status"] == "held":
            raise ValueError(f"the notice for {o['id']} is already held")
        if o["status"] != "revoke_today":
            raise ValueError(f"{o['id']} has no revocation effective today")
        self.db.execute("UPDATE overrides SET status='held', held_reason=? WHERE id=?", (a["reason"], o["id"]))
        self.db.execute("INSERT INTO changes (at,override_id,field,old,new,note) VALUES (?,?,?,?,?,?)",
                        (self.clock.iso(), o["id"], "hold", "revoke_today", "held", a["reason"]))
        return f"Notice for {o['id']} held out of today's mailing: {a['reason']}. The override stays in effect."

    def notices(self, a, shown: list):
        if not a.get("send"):
            return (views.notices(self.due(), self.run, self.svc["batch_at"][11:16]) +
                    "\n(Use `pa notices --send` to send the notices that are not sent or held.)")
        rows = self.pending()
        if not rows:
            raise ValueError("no notices to send")
        sent = []
        for o in rows:
            subject, body = views.notice_mail(o, self.svc["sponsor"], self.svc["company"])
            self.smtp([o["pharmacy_email"]], subject, body)
            sent.append(f"  {o['id']} -> {o['pharmacy_email']}")
        held = [o["id"] for o in self.due() if o["status"] == "held"]
        return (f"Sent {len(sent)} notices:\n" + "\n".join(sent) + (f"\nHeld: {', '.join(held)}" if held else "") +
                "\nSend the daily notices report to the pharmacy program mailbox.")

    def inbox(self, a):
        folder = a.get("folder") or "inbox"
        rows = self.db.execute("SELECT * FROM mailbox WHERE folder=? AND sent_at<=? ORDER BY sent_at DESC",
                               (folder, self.clock.iso())).fetchall()
        return "\n".join([f"folder: {folder}"] + [f"  {m['id']:>3} {'*' if m['unread'] else ' '} "
                                                  f"{m['sent_at'][:16].replace('T', ' ')}  {m['sender'][:44]:<44}  "
                                                  f"{m['subject']}" for m in rows])

    def read(self, a):
        m = self.db.execute("SELECT * FROM mailbox WHERE id=?", (int(a["id"]),)).fetchone()
        if not m:
            raise ValueError(f"no message {a['id']}")
        self.db.execute("UPDATE mailbox SET unread=0 WHERE id=?", (m["id"],))
        return (f"From: {m['sender']}\nTo: {m['recipients']}\nDate: {m['sent_at'].replace('T', ' ')}\n"
                f"Subject: {m['subject']}\n\n{m['body']}")

    def send(self, a):
        to = [x.strip() for x in a["to"].split(",") if x.strip()]
        if not to:
            raise ValueError("no recipient")
        self.smtp(to, a["subject"], a["body"])
        return f"Sent to {', '.join(to)}."

    def history(self, a):
        rows = self.db.execute("SELECT * FROM history ORDER BY day DESC").fetchall()
        return "\n".join(["Recent pharmacy notices"] + [f"  {r['day']}: revocation notices {r['revoked']}, held {r['held']}; "
                                                       f"{r['note']}" for r in rows])

    def call(self, command: str, args: dict) -> tuple[bool, str]:
        with self.lock:
            shown: list = []
            handlers = {"status": self.status, "register": self.register, "hold": self.hold,
                        "inbox": self.inbox, "read": self.read, "send": self.send, "history": self.history,
                        "revocations": lambda a: self.register({"revocations": True})}
            try:
                if command == "show":
                    out = self.show(args, shown)
                elif command == "notices":
                    out = self.notices(args, shown)
                elif command in handlers:
                    out = handlers[command](args)
                else:
                    raise ValueError(f"unknown command {command}")
                ok = True
            except (ValueError, KeyError) as e:
                ok, out = False, f"Error: {e}"
            self.db.execute("INSERT INTO api_log (at,command,args,ok,output,shown) VALUES (?,?,?,?,?,?)",
                            (self.clock.iso(), command, json.dumps(args), int(ok), out, json.dumps(shown)))
            return ok, out


def serve(state: Path, bind: str, port: int):
    office = Office(state)
    import smtp_relay  # aiosmtpd: office image only
    smtp_relay.start(state, office.clock, office.svc, port=SMTP_PORT)

    class Handler(BaseHTTPRequestHandler):
        # no Date header (it carried the host's real time outside faketime, dog-warden 8388c69)
        def send_response(self, code, message=None):
            self.log_request(code)
            self.send_response_only(code, message)
            self.send_header("Server", "pa-gw/3.1" if self.server.server_port == 8000 else "gateway")

        def send_error(self, code, message=None, explain=None):
            body = b'{"ok": false}'
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def log_message(self, *a):
            pass

        def reply(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply(200 if self.path == "/health" else 404, {"ok": self.path == "/health"})

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            ok, out = office.call(req.get("command", ""), req.get("args") or {})
            self.reply(200, {"ok": ok, "output": out})

    ThreadingHTTPServer((bind, port), Handler).serve_forever()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8766)
    a = p.parse_args()
    serve(a.data, a.bind, a.port)
