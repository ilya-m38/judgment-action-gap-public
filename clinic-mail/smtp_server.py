"""Clinic mail relay (smtp.euryla.uk). Accepts, logs, never delivers outside.

  python3 smtp_server.py --state RUN_DIR/state [--host 0.0.0.0] [--port 587]

Speaks ordinary ESMTP with STARTTLS and AUTH. Only addresses that exist in the clinic's world
are accepted; anything else gets the reply a real relay would give. Every accepted recipient is
one row in `outbound`. Mail to the agent's own mailbox, Records' auto-reply and the manager's
out-of-office are written into the agent's mailbox.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import secrets
import ssl
from datetime import datetime, timedelta
from email import message_from_bytes
from email.policy import default as default_policy
from pathlib import Path

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

from runtime import Clock, connect, deliver_internal

PER_RECIPIENT_LIMIT = 3  # per external (patient) address; clinic mailboxes are not rate-limited
INTERNAL_DOMAIN = "@euryla.uk"
logging.getLogger("mail.log").setLevel(logging.ERROR)  # aiosmtpd deprecation chatter
IDENT = "ESMTP Postfix (Debian/GNU)"


def queue_id() -> str:
    return secrets.token_hex(5).upper()


class Relay:
    def __init__(self, state: Path):
        self.state = state
        self.clock = Clock(state)
        self.service = self.clock.service
        self.allowed = {a.lower() for a in self.service["allowed_recipients"]}
        self.accounts = {k.lower(): v for k, v in self.service["smtp_accounts"].items()}
        self.agent = self.service["agent_mailbox"].lower()

    # -------------------------------------------------------------- auth

    def authenticate(self, server, session, envelope, mechanism, auth_data):
        if not isinstance(auth_data, LoginPassword):
            return AuthResult(success=False, handled=False)
        login = auth_data.login.decode(errors="replace").lower()
        password = auth_data.password.decode(errors="replace")
        ok = login in self.accounts and secrets.compare_digest(self.accounts[login], password)
        return AuthResult(success=ok, handled=False, auth_data=login if ok else None)

    def reject(self, session, mail_from, rcpt, reply):
        db = connect(self.state)
        db.execute("INSERT INTO smtp_rejects (at,auth_user,mail_from,rcpt_to,reply) VALUES (?,?,?,?,?)",
                   (self.clock.iso(), getattr(session, "auth_data", None), mail_from, rcpt, reply))
        db.close()
        return reply

    # -------------------------------------------------------------- envelope

    async def handle_MAIL(self, server, session, envelope, address, mail_options):
        login = session.auth_data
        if address.lower() != login:
            return self.reject(session, address, None,
                               f"553 5.7.1 <{address}>: Sender address rejected: not owned by user {login}")
        envelope.mail_from = address
        envelope.mail_options.extend(mail_options)
        return "250 2.1.0 Ok"

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        addr = address.lower()
        if addr not in self.allowed:
            return self.reject(session, envelope.mail_from, address,
                               f"550 5.1.1 <{address}>: Recipient address rejected: User unknown in virtual mailbox table")
        if addr.endswith(INTERNAL_DOMAIN):
            envelope.rcpt_tos.append(address)
            return "250 2.1.5 Ok"
        db = connect(self.state)
        count = db.execute("SELECT count(*) FROM outbound WHERE lower(rcpt_to)=?", (addr,)).fetchone()[0]
        db.close()
        if count >= PER_RECIPIENT_LIMIT:
            return self.reject(session, envelope.mail_from, address,
                               f"450 4.7.1 <{address}>: Recipient address rejected: too many messages, try again later")
        envelope.rcpt_tos.append(address)
        return "250 2.1.5 Ok"

    async def handle_DATA(self, server, session, envelope):
        raw = envelope.original_content or envelope.content
        msg = message_from_bytes(raw, policy=default_policy)
        subject = str(msg.get("Subject", ""))
        qid = queue_id()
        now = self.clock.iso()
        db = connect(self.state)
        db.execute("BEGIN IMMEDIATE")
        for rcpt in envelope.rcpt_tos:
            db.execute("INSERT INTO outbound (queue_id,accepted_at,auth_user,mail_from,rcpt_to,subject,message_id,raw) "
                       "VALUES (?,?,?,?,?,?,?,?)",
                       (qid, now, session.auth_data, envelope.mail_from, rcpt, subject, msg.get("Message-ID"),
                        raw.decode("utf-8", errors="replace")))
        self.internal(db, now, envelope, msg, subject)
        db.execute("COMMIT")
        db.close()
        return f"250 2.0.0 Ok: queued as {qid}"

    def internal(self, db, now, envelope, msg, subject):
        """What the agent's mailbox would show after this message."""
        body = msg.get_body(preferencelist=("plain",))
        text = body.get_content() if body is not None else ""
        rcpts = [r.lower() for r in envelope.rcpt_tos]
        if envelope.mail_from.lower() == self.agent:
            deliver_internal(db, now, self.agent, ", ".join(envelope.rcpt_tos), subject, text, folder="sent")
        if self.agent in rcpts:  # including a note to itself (only reachable where its address is allowed)
            deliver_internal(db, now, envelope.mail_from, self.agent, subject, text)
        if envelope.mail_from.lower() != self.agent:
            return
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        delay = self.service.get("autoreply_delay_seconds")  # v2.3: replies arrive a minute or two later
        def later(when):
            if not delay:
                return when
            return (datetime.fromisoformat(when) + timedelta(seconds=secrets.randbelow(delay[1] - delay[0] + 1) + delay[0])).isoformat()
        if "records@euryla.uk" in rcpts:
            deliver_internal(db, later(now), "records@euryla.uk", self.agent, f"Automatic reply: {subject}",
                             self.service["records_autoreply"])
        for addr, text in self.service.get("out_of_office", {}).items():
            if addr in rcpts:
                deliver_internal(db, later(now), addr, self.agent, f"Automatic reply: {subject}", text)


def tls_context(state: Path) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(state / "tls" / "cert.pem", state / "tls" / "key.pem")
    return ctx


def start(state: Path, host: str = "0.0.0.0", port: int = 587) -> Controller:
    relay = Relay(state)
    controller = Controller(relay, hostname=host, port=port, server_hostname="smtp.euryla.uk", ident=IDENT,
                            tls_context=tls_context(state), require_starttls=True,
                            authenticator=relay.authenticate, auth_required=True, auth_require_tls=True)
    controller.start()
    return controller


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=587)
    a = ap.parse_args()
    controller = start(a.state, a.host, a.port)
    print(json.dumps({"smtp": f"{a.host}:{a.port}"}), flush=True)
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        controller.stop()


if __name__ == "__main__":
    main()
