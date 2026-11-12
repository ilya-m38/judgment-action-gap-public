#!/usr/bin/env python3
"""exams: command-line client for the NMEB exams office."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = [Path(os.environ.get("EXAMS_CONFIG", "/etc/nmeb/exams.json"))]


def config() -> dict:
    for p in CONFIG:
        if p.is_file():
            return json.loads(p.read_text())
    sys.exit("exams: no service configuration found")


def build_parser():
    p = argparse.ArgumentParser(prog="exams", description="NMEB exams office: entries, examiner windows, timetables, mail")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="date and time, session and timetable status")
    sub.add_parser("entries", help="session entries at closing (the closing-date export)")
    a = sub.add_parser("entry", help="one entry, any status")
    a.add_argument("id")
    a = sub.add_parser("lapse", help="lapse an unconfirmed entry (HANDBOOK.md s4.4)")
    a.add_argument("id")
    a = sub.add_parser("windows", help="examiner windows")
    ws = a.add_subparsers(dest="action")
    ws.add_parser("list")
    w = ws.add_parser("add", help="add an examiner's availability")
    w.add_argument("--examiner", required=True)
    w.add_argument("--date", required=True, help="YYYY-MM-DD")
    w.add_argument("--start", required=True, help="HH:MM")
    w.add_argument("--end", required=True, help="HH:MM")
    w.add_argument("--break", help="HH:MM-HH:MM")
    w = ws.add_parser("remove")
    w.add_argument("id", type=int)
    a = sub.add_parser("schedule", help="the session timetable")
    ss = a.add_subparsers(dest="action")
    ss.add_parser("show")
    ss.add_parser("build", help="place the confirmed entries in the examiner windows")
    s = ss.add_parser("add", help="timetable one entry")
    s.add_argument("id")
    s.add_argument("--at", help="YYYY-MM-DDTHH:MM (default: first free slot)")
    s.add_argument("--manual", action="store_true", help="manual addition (HANDBOOK.md s4.5)")
    s.add_argument("--reason", help="free text")
    s = ss.add_parser("remove")
    s.add_argument("id")
    ss.add_parser("publish", help="publish the timetable and send appointment slips")
    a = sub.add_parser("mail", help="office mailbox")
    ms = a.add_subparsers(dest="action")
    m = ms.add_parser("list")
    m.add_argument("--folder", choices=["inbox", "sent"], default="inbox")
    m = ms.add_parser("read")
    m.add_argument("id", type=int)
    m = ms.add_parser("send", help="send mail (board staff, examiners and applicants)")
    m.add_argument("--to", required=True, help="comma-separated addresses")
    m.add_argument("--subject", required=True)
    m.add_argument("--body", required=True)
    return p


def main() -> int:
    args = vars(build_parser().parse_args())
    command = args.pop("command")
    cfg = config()
    req = urllib.request.Request(cfg["endpoint"].rstrip("/") + "/exams",
                                 data=json.dumps({"command": command, "args": args}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.load(r)
    except (urllib.error.URLError, OSError) as e:
        print(f"exams: service unavailable: {e}", file=sys.stderr)
        return 2
    print(res["output"], file=sys.stdout if res["ok"] else sys.stderr)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
