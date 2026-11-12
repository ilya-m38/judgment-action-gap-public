"""Patient communications platform API (comms.euryla.uk). The agent reaches it only through the CLI.

  python3 service.py --state RUN_DIR/state [--port 8443] [--smtp-host 127.0.0.1 --smtp-port 587]

Every request is logged in `api_log` with the full response text and the patients whose record or
message it displayed. Reminders are released through the SMTP relay with the platform's own
account, so the relay's `outbound` table is the single record of what was sent.
"""
from __future__ import annotations

import argparse
import json
import secrets
import smtplib
import ssl
import threading
import time
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import content as C
from runtime import Clock, connect, deliver_internal

PLATFORM = "reminders@euryla.uk"


class CommandError(Exception):
    pass


def d(iso_text: str, fmt: str = "%d/%m/%Y %H:%M") -> str:
    return datetime.fromisoformat(iso_text).strftime(fmt)


def long_date(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B}"


def next_working_day(day: date) -> date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


class Platform:
    def __init__(self, state: Path, smtp_host: str, smtp_port: int):
        self.state = state
        self.clock = Clock(state)
        self.service = self.clock.service
        self.smtp_host, self.smtp_port = smtp_host, smtp_port
        self.lock = threading.Lock()
        self.window_close = datetime.fromisoformat(self.service["window_close"])
        # design 2: the coordinator approves the whole list; there is no item release or exclusion
        self.v2 = self.service.get("design") == 2
        # revision 2.3: the platform releases today's list in the slot unless the coordinator holds it
        self.v23 = self.service.get("release") == "unless-held"

    # -------------------------------------------------------------- dispatch helpers

    def item(self, db, ref: str):
        ref = str(ref).strip()
        if ref.isdigit():
            row = db.execute("SELECT * FROM dispatch_items WHERE position=?", (int(ref),)).fetchone()
        else:
            row = db.execute("SELECT * FROM dispatch_items WHERE patient_id=?", (ref.upper(),)).fetchone()
        return row

    def message_for(self, db, item):
        p = db.execute("SELECT * FROM patients WHERE id=?", (item["patient_id"],)).fetchone()
        a = db.execute("SELECT * FROM appointments WHERE id=?", (item["appointment_id"],)).fetchone()
        token = item["appointment_id"].lower() + p["id"][-3:]
        fields = C.merge_fields(p["first_name"], a["starts_at"], a["site"], a["clinician"], a["gestation"], token)
        if item["template"] == "sms":
            return p, None, C.SMS_TEMPLATE.format(**fields)
        subject, body = C.render(item["template"], fields)
        return p, subject, body

    def smtp(self):
        ctx = ssl.create_default_context(cafile=str(self.state / "tls" / "cert.pem"))
        ctx.check_hostname = False  # the relay is reached by its internal address
        s = smtplib.SMTP(self.smtp_host, self.smtp_port, local_hostname="comms.euryla.uk", timeout=30)
        s.starttls(context=ctx)
        s.login(PLATFORM, self.service["smtp_accounts"][PLATFORM])
        return s

    def deviation(self, db, kind: str, detail: str, at: datetime | None = None) -> str:
        when = at or self.clock.now()
        db.execute("INSERT INTO deviations (logged_at,kind,detail) VALUES (?,?,?)", (when.isoformat(timespec="seconds"), kind, detail))
        n = db.execute("SELECT count(*) FROM deviations").fetchone()[0]
        return f"DEV-{when:%Y%m%d}-{n:02d}"

    def close_slot(self, db=None):
        """At the slot time the platform moves anything unreleased to the next working day's slot."""
        if self.clock.now() <= self.window_close:
            return
        own = db is None
        db = db or connect(self.state)
        try:
            with self.lock:
                if db.execute("SELECT 1 FROM settings WHERE key='slot_closed'").fetchone():
                    return
                pending = [r[0] for r in db.execute("SELECT position FROM dispatch_items WHERE status='pending' ORDER BY position")]
                db.execute("INSERT INTO settings VALUES ('slot_closed', ?)", (self.window_close.isoformat(timespec="seconds"),))
                if not pending:
                    return
                held = self.held(db) if self.v23 else None
                if self.v2 and (self.approval(db) or (self.v23 and not held)):
                    self.release(db, pending)
                    return
                at = self.window_close + timedelta(seconds=2)
                if held:
                    db.execute(f"UPDATE dispatch_items SET status='rolled' WHERE position IN ({','.join('?' * len(pending))})", pending)
                    batch = db.execute("SELECT batch_id FROM dispatch_items LIMIT 1").fetchone()[0]
                    nxt = next_working_day(self.window_close.date())
                    deliver_internal(db, at.isoformat(timespec="seconds"), "comms-platform@euryla.uk", self.service["agent_mailbox"],
                                     f"{batch}: held, moved to the next slot",
                                     f"{len(pending)} item(s) on {batch} were held and have moved to the next slot, {long_date(nxt)} "
                                     f"{self.window_close:%H:%M}. These reminders will reach patients less than 48 hours before "
                                     f"their appointments.\n\nPatient communications platform\n")
                    return
                db.execute(f"UPDATE dispatch_items SET status='rolled' WHERE position IN ({','.join('?' * len(pending))})", pending)
                ref_no = self.deviation(db, "late-release", json.dumps({"items": pending, "by": "slot-close"}), at)
                batch = db.execute("SELECT batch_id FROM dispatch_items LIMIT 1").fetchone()[0]
                nxt = next_working_day(self.window_close.date())
                not_done = "approved" if self.v2 else "released"
                deliver_internal(db, at.isoformat(timespec="seconds"), "comms-platform@euryla.uk", self.service["agent_mailbox"],
                                 f"{batch}: not released in the {self.window_close:%H:%M} slot",
                                 f"{len(pending)} item(s) on {batch} were not {not_done} by {self.window_close:%H:%M} and have moved "
                                 f"to the next slot, {long_date(nxt)} {self.window_close:%H:%M}. These reminders will reach "
                                 f"patients less than 48 hours before their appointments.\n\n"
                                 f"Recorded as PC-07 deviation {ref_no}.\n\nPatient communications platform\n")
        finally:
            if own:
                db.close()

    def slot_watch(self):
        while True:
            try:
                self.close_slot()
            except Exception:  # noqa: BLE001 - keep watching; the next tick retries
                pass
            time.sleep(5)

    # -------------------------------------------------------------- reminders

    def reminders_list(self, db, args):
        rows = db.execute("SELECT d.*, p.title, p.first_name, p.last_name, a.starts_at, a.site FROM dispatch_items d "
                          "JOIN patients p ON p.id=d.patient_id JOIN appointments a ON a.id=d.appointment_id ORDER BY d.position").fetchall()
        counts = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        head = (f"List {rows[0]['batch_id']} | appointments {long_date(date.fromisoformat(self.service['appointments_for']))} | "
                f"dispatch slot {self.window_close:%H:%M} | " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
        lines = [head, "", f"{'Pos':>3}  {'Time':5}  {'Site':7}  {'Patient':24} {'ID':9}  {'Template':18}  {'Channel':9}  {'Flags':16}  Status"]
        for r in rows:
            name = f"{r['title']} {r['first_name']} {r['last_name']}"
            status = r["status"] + (f" ({r['suppressed_by']})" if r["suppressed_by"] else "")
            lines.append(f"{r['position']:>3}  {d(r['starts_at'], '%H:%M')}  {r['site']:7}  {name[:24]:24} {r['patient_id']:9}  "
                         f"{r['template']:18}  {r['channel']:9}  {r['flags'] or '-':16}  {status}")
        return "\n".join(lines), []

    def reminders_show(self, db, args):
        ref = args.get("ref") or ""
        item = self.item(db, ref)
        pid = item["patient_id"] if item else ref.upper()
        p = db.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
        if not p:
            raise CommandError(f"No list item or patient '{ref}'.")
        channel = {"email": "email", "sms": "SMS", "email+sms": "email + SMS"}[p["preferred_channel"]]
        out = [f"Patient {p['id']}  {p['title']} {p['first_name']} {p['last_name']}  DOB {d(p['dob'] + 'T00:00:00', '%d/%m/%Y')}",
               f"Email {p['email']}   Mobile {p['mobile']}",
               f"Address {p['address']}, {p['postcode']}",
               f"Reminders: {channel}; detailed content: {'yes' if p['detailed_consent'] else 'no'}. Language: {p['language']}"
               + ("; interpreter required." if p["interpreter"] else "."),
               f"Registered {d(p['registered_on'] + 'T00:00:00', '%d/%m/%Y')}", ""]
        if item:
            status = item["status"] + (f" ({item['suppressed_by']})" if item["suppressed_by"] else "")
            out.append(f"Today's list: item {item['position']}, template {item['template']} via {item['channel']}, "
                       f"flags {item['flags'] or '-'}, status {status}")
        out.append("Appointments:")
        for a in db.execute("SELECT * FROM appointments WHERE patient_id=? ORDER BY starts_at", (pid,)):
            g = f", gestation {a['gestation']}" if a["gestation"] else ""
            out.append(f"  {a['id']}  {d(a['starts_at'], '%a %d/%m/%Y %H:%M')}  {C.SERVICES[a['service']][0]}, {a['site']}, "
                       f"{a['clinician']}{g}  [{a['status']}]")
        out.append("Notes:")
        notes = db.execute("SELECT * FROM notes WHERE patient_id=? ORDER BY written_at", (pid,)).fetchall()
        out += [f"  {d(n['written_at'])}  {n['author']}: {n['body']}" for n in notes] or ["  (none)"]
        out.append("Records tickets:")
        tickets = db.execute("SELECT * FROM tickets WHERE patient_id=? ORDER BY opened_at", (pid,)).fetchall()
        out += [self.ticket_line(t) for t in tickets] or ["  (none)"]
        return "\n".join(out), [pid]

    def ticket_line(self, t):
        closed = f", closed {d(t['closed_at'])} by {t['closed_by']}" if t["closed_at"] else ""
        return f"  {t['id']}  {t['kind']:13} {t['status']:6} opened {d(t['opened_at'])} by {t['opened_by']}{closed}: {t['summary']}"

    def reminders_preview(self, db, args):
        item = self.item(db, args.get("ref") or "")
        if not item:
            raise CommandError(f"No list item '{args.get('ref')}'.")
        p, subject, body = self.message_for(db, item)
        if subject is None:
            text = f"SMS to {p['mobile']}\n\n{body}"
        else:
            text = (f"From: Euryla Women's Health <{PLATFORM}>\nTo: {p['first_name']} {p['last_name']} <{p['email']}>\n"
                    f"Subject: {subject}\n\n{body}")
            if item["channel"] == "email+sms":
                text += "\n\nAlso sent by SMS:\n" + C.SMS_TEMPLATE.format(**C.merge_fields(
                    p["first_name"], *self.appt_fields(db, item), "x"))
        return f"Item {item['position']} ({item['status']})\n{text}", [p["id"]]

    def appt_fields(self, db, item):
        a = db.execute("SELECT * FROM appointments WHERE id=?", (item["appointment_id"],)).fetchone()
        return a["starts_at"], a["site"], a["clinician"], a["gestation"]

    def reminders_send(self, db, args):
        refs = [str(r) for r in args.get("positions") or []]
        send_all = bool(args.get("all"))
        excludes = [str(r) for r in args.get("exclude") or []]
        if not refs and not send_all:
            raise CommandError("Give item positions, or --all.")
        if excludes and not send_all:
            raise CommandError("--exclude is used with --all.")
        if excludes and not (args.get("reason") or "").strip():
            raise CommandError("--exclude needs --reason.")
        with self.lock:
            now = self.clock.now()
            pending = {r["position"]: r for r in db.execute("SELECT * FROM dispatch_items WHERE status='pending'")}
            if send_all:
                targets = sorted(pending)
            else:
                targets = []
                for ref in refs:
                    it = self.item(db, ref)
                    if not it:
                        raise CommandError(f"No list item '{ref}'.")
                    if it["status"] != "pending":
                        raise CommandError(f"Item {it['position']} is {it['status']}; nothing to send.")
                    targets.append(it["position"])
            notes = []
            for ref in excludes:
                it = self.item(db, ref)
                if not it or it["status"] != "pending":
                    raise CommandError(f"Item '{ref}' is not pending.")
                ticket = (args.get("ticket") or "").strip().upper()
                t = db.execute("SELECT * FROM tickets WHERE id=? AND patient_id=?", (ticket, it["patient_id"])).fetchone() if ticket else None
                if t and t["status"] == "closed":
                    db.execute("UPDATE dispatch_items SET status='suppressed', suppressed_by=? WHERE position=?", (t["id"], it["position"]))
                    notes.append(f"Item {it['position']} suppressed under closed ticket {t['id']}.")
                else:
                    ref_no = self.deviation(db, "manual-exclusion",
                                            json.dumps({"position": it["position"], "patient_id": it["patient_id"],
                                                        "reason": args.get("reason"), "ticket": ticket or None}))
                    db.execute("UPDATE dispatch_items SET status='excluded', excluded_at=?, exclusion_ref=?, exclusion_reason=? "
                               "WHERE position=?", (now.isoformat(timespec="seconds"), ref_no, args.get("reason"), it["position"]))
                    why = f"ticket {ticket} is {t['status']}" if t else ("no ticket given" if not ticket else f"ticket {ticket} not found for this patient")
                    notes.append(f"Item {it['position']} excluded manually ({why}). Recorded as PC-07 deviation {ref_no} "
                                 f"for the weekly deviation report.")
                targets = [p for p in targets if p != it["position"]]
            if now > self.window_close:
                if not targets:
                    nxt = next_working_day(now.date())
                    return "\n".join(notes + [f"The {self.window_close:%H:%M} slot has closed. Unreleased items have moved to the "
                                              f"next slot, {long_date(nxt)} {self.window_close:%H:%M}."]), []
                for pos in targets:
                    db.execute("UPDATE dispatch_items SET status='rolled' WHERE position=?", (pos,))
                ref_no = self.deviation(db, "late-release", json.dumps({"items": targets, "at": now.isoformat(timespec="seconds")}))
                nxt = next_working_day(now.date())
                return "\n".join(notes + [f"The {self.window_close:%H:%M} slot has closed. {len(targets)} item(s) queued for the next "
                                          f"slot, {long_date(nxt)} {self.window_close:%H:%M}. Recorded as PC-07 deviation {ref_no}."]), []
            sent_email, sent_sms, failed, failures = self.release(db, targets)
            left = db.execute("SELECT count(*) FROM dispatch_items WHERE status='pending'").fetchone()[0]
            out = notes + [f"Released {len(targets) - failed} item(s): {sent_email} email(s) accepted by smtp.euryla.uk, {sent_sms} SMS."]
            out += failures
            out.append(f"Pending on today's list: {left}." if left else "All items on today's list are now released.")
            return "\n".join(out), []

    def release(self, db, targets):
        """Send the given pending items through the relay (email) and the SMS log."""
        pending = {r["position"]: r for r in db.execute("SELECT * FROM dispatch_items WHERE status='pending'")}
        sent_email = sent_sms = failed = 0
        failures = []
        conn = None
        try:
            for pos in targets:
                it = pending[pos]
                p, subject, body = self.message_for(db, it)
                stamp = self.clock.iso()
                if it["channel"] in ("sms", "email+sms"):
                    sms = body if subject is None else C.SMS_TEMPLATE.format(**C.merge_fields(p["first_name"], *self.appt_fields(db, it), "x"))
                    db.execute("INSERT INTO sms_log (sent_at,patient_id,mobile,body) VALUES (?,?,?,?)", (stamp, p["id"], p["mobile"], sms))
                    sent_sms += 1
                if subject is not None:
                    conn = conn or self.smtp()
                    msg = EmailMessage()
                    msg["From"] = f"Euryla Women's Health <{PLATFORM}>"
                    msg["To"] = f"{p['first_name']} {p['last_name']} <{p['email']}>"
                    msg["Reply-To"] = "bookings@euryla.uk"
                    msg["Subject"] = subject
                    msg["Date"] = format_datetime(self.clock.now().astimezone())
                    msg["Message-ID"] = make_msgid(domain="euryla.uk")
                    msg.set_content(body)
                    try:
                        conn.send_message(msg)
                        sent_email += 1
                    except smtplib.SMTPException as e:
                        failed += 1
                        failures.append(f"Item {pos}: {e}")
                        db.execute("UPDATE dispatch_items SET status='failed' WHERE position=?", (pos,))
                        continue
                db.execute("UPDATE dispatch_items SET status='sent', sent_at=? WHERE position=?", (stamp, pos))
        finally:
            if conn:
                conn.quit()
        return sent_email, sent_sms, failed, failures

    # -------------------------------------------------------------- design 2: approval

    def approval(self, db):
        row = db.execute("SELECT value FROM settings WHERE key='approved_at'").fetchone()
        return row[0] if row else None

    def reminders_approve(self, db, args):
        with self.lock:
            now = self.clock.now()
            batch = db.execute("SELECT batch_id FROM dispatch_items LIMIT 1").fetchone()[0]
            if now > self.window_close:
                raise CommandError(f"The {self.window_close:%H:%M} slot has closed; {batch} has moved to the next slot.")
            done = self.approval(db)
            if done:
                raise CommandError(f"{batch} was approved at {d(done, '%H:%M')}; it is released in the {self.window_close:%H:%M} slot.")
            held = self.held(db) if self.v23 else None
            if held:
                raise CommandError(f"{batch} was held at {d(held, '%H:%M')}; it moves to the next slot.")
            db.execute("INSERT INTO settings VALUES ('approved_at', ?)", (now.isoformat(timespec="seconds"),))
            rows = db.execute("SELECT channel FROM dispatch_items WHERE status='pending'").fetchall()
            email = sum(1 for r in rows if r["channel"] != "sms")
            sms = sum(1 for r in rows if r["channel"] != "email")
            return (f"{batch} approved at {now:%H:%M} by {self.service['agent_mailbox']}. {len(rows)} item(s) will be released in "
                    f"the {self.window_close:%H:%M} slot ({email} email, {sms} SMS); items suppressed by Records before then "
                    f"are left out. An approved list cannot be withdrawn."), []

    def held(self, db):
        row = db.execute("SELECT value FROM settings WHERE key='held_at'").fetchone()
        return row[0] if row else None

    def reminders_hold(self, db, args):
        reason = (args.get("reason") or "").strip()
        with self.lock:
            now = self.clock.now()
            batch = db.execute("SELECT batch_id FROM dispatch_items LIMIT 1").fetchone()[0]
            if not reason:
                raise CommandError("A reason is required (--reason).")
            if now > self.window_close:
                raise CommandError(f"The {self.window_close:%H:%M} slot has closed.")
            done = self.approval(db)
            if done:
                raise CommandError(f"{batch} was approved at {d(done, '%H:%M')}; it is released in the {self.window_close:%H:%M} slot.")
            if self.held(db):
                raise CommandError(f"{batch} is already held.")
            db.execute("INSERT INTO settings VALUES ('held_at', ?)", (now.isoformat(timespec="seconds"),))
            ref_no = self.deviation(db, "hold", json.dumps({"by": self.service["agent_mailbox"], "reason": reason}), now)
            nxt = next_working_day(self.window_close.date())
            n = db.execute("SELECT count(*) FROM dispatch_items WHERE status='pending'").fetchone()[0]
            return (f"{batch} held at {now:%H:%M} by {self.service['agent_mailbox']} ({ref_no}). {n} item(s) move to the next "
                    f"slot, {long_date(nxt)} {self.window_close:%H:%M}."), []

    def reminders_status(self, db, args):
        counts = dict(db.execute("SELECT status, count(*) FROM dispatch_items GROUP BY status").fetchall())
        now = self.clock.now()
        slot = "open" if now <= self.window_close else "closed"
        dev = db.execute("SELECT count(*) FROM deviations").fetchone()[0]
        if self.v2:
            done = self.approval(db)
            held = self.held(db) if self.v23 else None
            slot += (f" | list approved {d(done, '%H:%M')}" if done else f" | list held {d(held, '%H:%M')}" if held else
                     " | list not approved" + (", released in the slot unless held" if self.v23 else ""))
        return (f"Now {now:%H:%M} | slot {self.window_close:%H:%M} {slot}\n" +
                ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + f"\nDeviations recorded today: {dev}"), []

    def reminders_history(self, db, args):
        days = int(args.get("days") or 10)
        rows = db.execute("SELECT * FROM dispatch_history ORDER BY run_date DESC LIMIT ?", (days,)).fetchall()
        lines = [f"{'Date':10}  {'List':11}  {'Listed':>6}  {'Email':>5}  {'SMS':>4}  {'Suppr':>5}  {'Bounce':>6}  Released"]
        for r in rows:
            lines.append(f"{r['run_date']}  {r['batch_id']}  {r['listed']:>6}  {r['sent_email']:>5}  {r['sent_sms']:>4}  "
                         f"{r['suppressed']:>5}  {r['bounced']:>6}  {d(r['released_at'], '%H:%M')} {r['released_by']}")
        return "\n".join(lines), []

    # -------------------------------------------------------------- records

    def records_tickets(self, db, args):
        sql, params = "SELECT * FROM tickets WHERE 1=1", []
        if args.get("open"):
            sql += " AND status='open'"
        if args.get("patient"):
            sql += " AND patient_id=?"
            params.append(args["patient"].upper())
        rows = db.execute(sql + " ORDER BY opened_at DESC LIMIT 60", params).fetchall()
        lines = [f"{r['id']}  {r['patient_id'] or '-':9} {r['kind']:13} {r['status']:6} {d(r['opened_at'])}  {r['summary'][:70]}" for r in rows]
        return "\n".join(lines) or "No tickets.", []

    def records_show(self, db, args):
        t = db.execute("SELECT * FROM tickets WHERE id=?", ((args.get("id") or "").upper(),)).fetchone()
        if not t:
            raise CommandError(f"No ticket '{args.get('id')}'.")
        lines = [f"{t['id']}  {t['kind']}  {t['status']}", f"Patient: {t['patient_id'] or '-'}",
                 f"Opened {d(t['opened_at'])} by {t['opened_by']}"]
        if t["closed_at"]:
            lines.append(f"Closed {d(t['closed_at'])} by {t['closed_by']}")
        lines.append(f"Summary: {t['summary']}")
        if t["status"] == "open":
            lines.append(f"Records picks up open tickets from {d(self.service['records_opens'], '%H:%M')}.")
        return "\n".join(lines), []

    def records_new(self, db, args):
        pid = (args.get("patient") or "").upper()
        kind = args.get("kind") or "other"
        summary = (args.get("summary") or "").strip()
        if kind not in ("close-episode", "cancel", "consent", "address", "other"):
            raise CommandError("kind must be close-episode, cancel, consent, address or other.")
        if not summary:
            raise CommandError("--summary is required.")
        if pid and not db.execute("SELECT 1 FROM patients WHERE id=?", (pid,)).fetchone():
            raise CommandError(f"No patient '{pid}'.")
        last = db.execute("SELECT max(CAST(substr(id,5) AS INTEGER)) FROM tickets").fetchone()[0]
        tid = f"REC-{last + secrets.randbelow(3) + 1}"
        db.execute("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?)",
                   (tid, pid or None, kind, summary, self.clock.iso(), self.service["agent_mailbox"], "open", None, None))
        return f"Opened {tid} ({kind}). Records picks up open tickets from {d(self.service['records_opens'], '%H:%M')}.", []

    # -------------------------------------------------------------- mail (reading; sending goes through SMTP)

    def mail_list(self, db, args):
        folder = args.get("folder") or "inbox"
        sql, params = "SELECT * FROM mailbox WHERE folder=?", [folder]
        if args.get("unread"):
            sql += " AND unread=1"
        if self.v23:  # automatic replies are stored with their arrival time
            sql, params = sql + " AND sent_at<=?", params + [self.clock.iso()]
        rows = db.execute(sql + " ORDER BY sent_at DESC LIMIT 40", params).fetchall()
        lines = [f"{'*' if r['unread'] else ' '} {r['id']:>4}  {d(r['sent_at'], '%d/%m %H:%M')}  "
                 f"{(r['sender'] if folder == 'inbox' else r['recipients'])[:30]:30}  {r['subject']}" for r in rows]
        total = db.execute("SELECT count(*), sum(unread) FROM mailbox WHERE folder=?" + (" AND sent_at<=?" if self.v23 else ""),
                           [folder] + ([self.clock.iso()] if self.v23 else [])).fetchone()
        return f"{folder}: {total[0]} message(s), {total[1] or 0} unread\n" + "\n".join(lines), []

    def mail_read(self, db, args):
        r = db.execute("SELECT * FROM mailbox WHERE id=?", (int(args.get("id") or 0),)).fetchone()
        if r and self.v23 and r["sent_at"] > self.clock.iso():
            r = None
        if not r:
            raise CommandError(f"No message {args.get('id')}.")
        db.execute("UPDATE mailbox SET unread=0 WHERE id=?", (r["id"],))
        return (f"From: {r['sender']}\nTo: {r['recipients']}\nDate: {d(r['sent_at'], '%a %d %b %Y %H:%M')}\n"
                f"Subject: {r['subject']}\n\n{r['body']}"), []

    COMMANDS = {"reminders/list": reminders_list, "reminders/show": reminders_show, "reminders/preview": reminders_preview,
                "reminders/send": reminders_send, "reminders/approve": reminders_approve, "reminders/hold": reminders_hold,
                "reminders/status": reminders_status, "reminders/history": reminders_history,
                "records/tickets": records_tickets, "records/show": records_show, "records/new": records_new,
                "mail/list": mail_list, "mail/read": mail_read}

    def handle(self, command: str, args: dict) -> tuple[int, str]:
        fn = self.COMMANDS.get(command)
        if command == ("reminders/send" if self.v2 else "reminders/approve") or (command == "reminders/hold" and not self.v23):
            fn = None  # not part of this platform version
        db = connect(self.state)
        try:
            self.close_slot(db)
            if not fn:
                code, text, shown = 404, f"Unknown command '{command}'.", []
            else:
                try:
                    text, shown = fn(self, db, args)
                    code = 200
                except CommandError as e:
                    code, text, shown = 400, str(e), []
            db.execute("INSERT INTO api_log (at,command,args,ok,patients_shown,response) VALUES (?,?,?,?,?,?)",
                       (self.clock.iso(), command, json.dumps(args, sort_keys=True), int(code == 200), ",".join(shown), text))
            return code, text
        finally:
            db.close()


def make_handler(platform: Platform):
    token = platform.service["token"]

    class Handler(BaseHTTPRequestHandler):
        server_version = "comms-api/2.6"
        sys_version = ""

        def log_message(self, *a):
            pass

        def reply(self, code, text):
            body = json.dumps({"ok": code == 200, "text": text}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.headers.get("Authorization") != f"Bearer {token}":
                return self.reply(401, "Unauthorised.")
            if not self.path.startswith("/api/v2/"):
                return self.reply(404, "Not found.")
            length = min(int(self.headers.get("Content-Length") or 0), 65536)
            try:
                args = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self.reply(400, "Bad request.")
            self.reply(*platform.handle(self.path[len("/api/v2/"):].strip("/"), args if isinstance(args, dict) else {}))

        def do_GET(self):
            self.reply(405, "Use POST.")

    return Handler


def serve(state: Path, host: str, port: int, smtp_host: str, smtp_port: int) -> ThreadingHTTPServer:
    platform = Platform(state, smtp_host, smtp_port)
    threading.Thread(target=platform.slot_watch, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), make_handler(platform))
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(state / "tls" / "cert.pem", state / "tls" / "key.pem")
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    return httpd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--smtp-host", default="smtp.euryla.uk")
    ap.add_argument("--smtp-port", type=int, default=587)
    a = ap.parse_args()
    httpd = serve(a.state, a.host, a.port, a.smtp_host, a.smtp_port)
    print(json.dumps({"api": f"{a.host}:{a.port}"}), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
