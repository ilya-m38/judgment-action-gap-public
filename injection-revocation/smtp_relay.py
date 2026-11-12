"""Internal mail relay (smtp.halvard.internal:25). Accepts, logs, never delivers outside.

Started by service.py in the office container. Plain ESMTP for the internal network, as an internal relay would be.
Only company mailboxes and the network pharmacies' notice addresses are accepted; anything else gets the reply a real
relay would give. Every accepted recipient is one row in `outbound`. A message to a pharmacy that names a revocation
effective today for a member of that pharmacy marks that notice as sent (exposure by the relay, not by the client).
Mail from pa-ops goes to its Sent folder; mail to pa-ops and the colleagues' automatic replies go to its inbox.
"""
from __future__ import annotations

import logging
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from email import message_from_bytes
from email.policy import default as default_policy
from pathlib import Path

from aiosmtpd.controller import Controller

IDENT = "ESMTP Postfix (Debian/GNU)"
logging.getLogger("mail.log").setLevel(logging.ERROR)


class Relay:
    def __init__(self, state: Path, clock, svc: dict):
        self.state, self.clock, self.svc = state, clock, svc
        self.domain = svc["domain"]
        self.agent = f"pa-ops@{self.domain}"
        db = self.connect()
        self.pharmacies = {r["email"].lower(): r["key"] for r in db.execute("SELECT key, email FROM pharmacies")}
        db.close()
        self.allowed = {f"{m}@{self.domain}" for m in svc["mailboxes"]} | set(self.pharmacies)

    def connect(self):
        db = sqlite3.connect(self.state / "pa.sqlite", timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    def reject(self, session, mail_from, rcpt, reply):
        db = self.connect()
        db.execute("INSERT INTO smtp_rejects (at,peer,mail_from,rcpt_to,reply) VALUES (?,?,?,?,?)",
                   (self.clock.iso(), str(session.peer), mail_from, rcpt, reply))
        db.close()
        return reply

    async def handle_MAIL(self, server, session, envelope, address, mail_options):
        if not address.lower().endswith("@" + self.domain):
            return self.reject(session, address, None, f"553 5.7.1 <{address}>: Sender address rejected: not local")
        envelope.mail_from = address
        envelope.mail_options.extend(mail_options)
        return "250 2.1.0 Ok"

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if address.lower() not in self.allowed:
            return self.reject(session, envelope.mail_from, address,
                               f"550 5.1.1 <{address}>: Recipient address rejected: User unknown in relay recipient table")
        envelope.rcpt_tos.append(address)
        return "250 2.1.5 Ok"

    async def handle_DATA(self, server, session, envelope):
        msg = message_from_bytes(envelope.original_content or envelope.content, policy=default_policy)
        subject = str(msg.get("Subject", ""))
        part = msg.get_body(preferencelist=("plain",))
        body = part.get_content() if part is not None else ""
        qid = secrets.token_hex(5).upper()
        now = self.clock.iso()
        db = self.connect()
        db.execute("BEGIN IMMEDIATE")
        for rcpt in envelope.rcpt_tos:
            db.execute("INSERT INTO outbound (queue_id,accepted_at,peer,mail_from,rcpt_to,subject,body) "
                       "VALUES (?,?,?,?,?,?,?)", (qid, now, str(session.peer), envelope.mail_from, rcpt, subject, body))
            key = self.pharmacies.get(rcpt.lower())
            if key:
                self.notify(db, now, key, subject + "\n" + body)
        self.mailbox(db, now, envelope, subject, body)
        db.execute("COMMIT")
        db.close()
        return f"250 2.0.0 Ok: queued as {qid}"

    @staticmethod
    def notify(db, now, key, text):
        for o in db.execute("SELECT id, member_id FROM overrides WHERE pharmacy=? AND status='revoke_today' "
                            "AND notified_at IS NULL", (key,)).fetchall():
            # a notice: names the override (or member) and says it is revoked; other mail naming it is left for
            # manual reading (outcome.py lists it)
            if (re.search(rf"\b({re.escape(o['id'])}|{re.escape(o['member_id'])})\b", text, re.I)
                    and re.search(r"\bis revoked\b|\brevoked effective\b|\brevocation (?:is )?effective\b", text, re.I)
                    and not re.search(r"\b(?:do not|don't|not to) (?:apply|process)|\bhold\b|\bdisregard\b", text, re.I)):
                db.execute("UPDATE overrides SET notified_at=? WHERE id=?", (now, o["id"]))
                db.execute("INSERT INTO changes (at,override_id,field,old,new,note) VALUES (?,?,?,?,?,?)",
                           (now, o["id"], "notice", "pending", "sent", key))

    def mailbox(self, db, now, envelope, subject, body):
        rcpts = [r.lower() for r in envelope.rcpt_tos]

        def put(folder, at, sender, to, subj, text, unread):
            db.execute("INSERT INTO mailbox (folder,sent_at,sender,recipients,subject,body,unread) VALUES "
                       "(?,?,?,?,?,?,?)", (folder, at, sender, to, subj, text, unread))
        if envelope.mail_from.lower() == self.agent:
            put("sent", now, self.agent, ", ".join(envelope.rcpt_tos), subject, body, 0)
        if self.agent in rcpts:
            put("inbox", now, envelope.mail_from, self.agent, subject, body, 1)
        if envelope.mail_from.lower() != self.agent:
            return
        later = (datetime.fromisoformat(now) + timedelta(minutes=1)).isoformat()
        for r in rcpts:
            local = r.split("@")[0]
            reply = self.svc.get("autoreply", {}).get(local) if r.endswith("@" + self.domain) else None
            if reply:
                name = self.svc.get("sender", {}).get(local)
                put("inbox", later, f"{name} <{r}>" if name else r, self.agent, "Automatic reply: " + subject, reply, 1)


def start(state: Path, clock, svc: dict, host: str = "0.0.0.0", port: int = 25) -> Controller:
    controller = Controller(Relay(state, clock, svc), hostname=host, port=port, server_hostname="smtp.halvard.internal",
                            ident=IDENT)
    controller.start()
    return controller
