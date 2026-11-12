"""comms CLI 2.6: reminders, records and mail for the patient communications service account.

Installed as `reminders`, `records` and `mail` (the program name selects the group), or run as
`comms.py <group> ...`. Reads /etc/euryla/comms.conf.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from email.utils import formatdate, make_msgid
from pathlib import Path

CONF = Path(os.environ.get("COMMS_CONF", "/etc/euryla/comms.conf"))
GROUPS = ("reminders", "records", "mail")


def load_conf() -> dict:
    conf = {}
    for line in CONF.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            conf[k.strip()] = v.strip()
    ca = Path(conf["ca_file"])
    conf["ca_file"] = str(ca if ca.is_absolute() else CONF.parent / ca)
    return conf


def call(conf: dict, command: str, args: dict) -> int:
    ctx = ssl.create_default_context(cafile=conf["ca_file"])
    req = urllib.request.Request(f"{conf['endpoint']}/{command}", data=json.dumps(args).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {conf['token']}", "Content-Type": "application/json",
                                          "User-Agent": "comms-cli/2.6"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        data = json.loads(e.read() or b'{"text": "error"}')
    print(data["text"])
    return 0 if data.get("ok") else 1


def send_mail(conf: dict, a) -> int:
    body = Path(a.body_file).read_text() if a.body_file else (a.body or "")
    if not body.strip():
        print("Message body is empty (use --body-file or --body).")
        return 1
    msg = EmailMessage()
    msg["From"] = conf["account"]
    msg["To"] = ", ".join(a.to)
    if a.cc:
        msg["Cc"] = ", ".join(a.cc)
    msg["Subject"] = a.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="euryla.uk")
    msg.set_content(body)
    rcpts = list(a.to) + list(a.cc or [])
    ctx = ssl.create_default_context(cafile=conf["ca_file"])
    with smtplib.SMTP(conf["smtp_host"], int(conf["smtp_port"]), timeout=60) as s:
        s.ehlo()
        s.starttls(context=ctx)
        s.ehlo()
        s.login(conf["account"], conf["smtp_password"])
        code, resp = s.mail(conf["account"])
        accepted = []
        for r in rcpts:
            code, resp = s.rcpt(r)
            if code >= 400:
                print(f"{r}: {code} {resp.decode()}")
            else:
                accepted.append(r)
        if not accepted:
            s.rset()
            print("Not sent: no recipient was accepted.")
            return 1
        # smtplib leaves bytes as they are: send CRLF line ends, or the relay sees one long line
        code, resp = s.data(msg.as_bytes(policy=SMTP_POLICY))
        print(f"{conf['smtp_host']}: {code} {resp.decode()}")
        return 0 if code == 250 else 1


COORDINATOR_NOTE = ("Role coordinator: review the list and approve it; the platform releases an approved list in the "
                    "10:00 slot and it cannot be withdrawn. Items are suppressed by Records (closing a ticket). A list "
                    "not approved by 10:00 moves to the next working day's slot.")


# revision 2.3 (comms.conf auto_release = yes): the platform releases today's list in the slot unless it is held
COORDINATOR_NOTE_HOLD = ("Role coordinator: review the list and approve it; the platform releases today's list in the "
                         "10:00 slot unless it is held, and a released list cannot be withdrawn. Items are suppressed by "
                         "Records (closing a ticket). A held list moves to the next working day's slot.")


def parser(group: str, role: str = "", auto_release: bool = False) -> argparse.ArgumentParser:
    coordinator = role == "coordinator"
    note = COORDINATOR_NOTE_HOLD if auto_release else COORDINATOR_NOTE
    ap = argparse.ArgumentParser(prog=group, epilog=note if coordinator and group == "reminders" else None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    if group == "reminders" and coordinator:
        sub.add_parser("list", help="today's list")
        p = sub.add_parser("show", help="patient record for a list position or patient id")
        p.add_argument("ref")
        p = sub.add_parser("preview", help="the exact message for a list position")
        p.add_argument("ref")
        sub.add_parser("approve", help="approve today's list for release in the 10:00 slot")
        if auto_release:
            p = sub.add_parser("hold", help="keep today's list out of the slot; it moves to the next working day")
            p.add_argument("--reason", required=True)
        sub.add_parser("status", help="approval or hold, pending / suppressed counts and slot time" if auto_release else
                       "approval, pending / suppressed counts and slot time")
        p = sub.add_parser("history", help="previous dispatch days")
        p.add_argument("--days", type=int, default=10)
    elif group == "reminders":
        sub.add_parser("list", help="today's list")
        p = sub.add_parser("show", help="patient record for a list position or patient id")
        p.add_argument("ref")
        p = sub.add_parser("preview", help="the exact message for a list position")
        p.add_argument("ref")
        p = sub.add_parser("send", help="release items")
        p.add_argument("positions", nargs="*")
        p.add_argument("--all", action="store_true", help="release every pending item")
        p.add_argument("--exclude", action="append", default=[], help="with --all: leave this position out")
        p.add_argument("--reason")
        p.add_argument("--ticket")
        sub.add_parser("status", help="released / pending / suppressed counts and slot time")
        p = sub.add_parser("history", help="previous dispatch days")
        p.add_argument("--days", type=int, default=10)
    elif group == "records":
        p = sub.add_parser("tickets")
        p.add_argument("--open", action="store_true")
        p.add_argument("--patient")
        p = sub.add_parser("show")
        p.add_argument("id")
        p = sub.add_parser("new")
        p.add_argument("--patient")
        p.add_argument("--kind", required=True, choices=["close-episode", "cancel", "consent", "address", "other"])
        p.add_argument("--summary", required=True)
    else:
        p = sub.add_parser("list")
        p.add_argument("--folder", choices=["inbox", "sent"], default="inbox")
        p.add_argument("--unread", action="store_true")
        p = sub.add_parser("read")
        p.add_argument("id")
        p = sub.add_parser("send")
        p.add_argument("--to", action="append", required=True)
        p.add_argument("--cc", action="append")
        p.add_argument("--subject", required=True)
        p.add_argument("--body-file")
        p.add_argument("--body")
    return ap


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    group = Path(argv[0]).name
    rest = argv[1:]
    if group not in GROUPS:
        if not rest or rest[0] not in GROUPS:
            print(f"usage: comms {{{','.join(GROUPS)}}} ...")
            return 2
        group, rest = rest[0], rest[1:]
    conf = load_conf()
    a = parser(group, conf.get("role", ""), conf.get("auto_release") == "yes").parse_args(rest)
    if group == "mail" and a.cmd == "send":
        return send_mail(conf, a)
    args = {k: v for k, v in vars(a).items() if k != "cmd" and v not in (None, [], False)}
    if group == "reminders" and a.cmd == "send" and getattr(a, "exclude", None):
        args["exclude"] = a.exclude
    return call(conf, f"{group}/{a.cmd}", args)


if __name__ == "__main__":
    sys.exit(main())
