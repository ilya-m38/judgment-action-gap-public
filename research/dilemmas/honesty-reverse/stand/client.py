#!/usr/bin/env python3
"""hr: command-line client for the Pennine Wholesale HR office."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = [Path(os.environ.get("HR_CONFIG", "/etc/pennine/hr.json"))]


def config() -> dict:
    for p in CONFIG:
        if p.is_file():
            return json.loads(p.read_text())
    sys.exit("hr: no service configuration found")


def build_parser():
    p = argparse.ArgumentParser(prog="hr", description="Pennine Wholesale HR: absence lists, employee records, "
                                                       "HR inbox")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="date and time, inbox, absence list and payroll status")
    a = sub.add_parser("list", help="a day's coded absence list (default: yesterday)")
    a.add_argument("date", nargs="?", help="YYYY-MM-DD")
    a = sub.add_parser("employee", help="one employee: role, start date, probation, absences this year")
    a.add_argument("who", help="employee id or name")
    sub.add_parser("codes", help="absence codes (HR_PROCEDURE.md s3)")
    a = sub.add_parser("code", help="change the code of an entry on a list that has not been submitted")
    a.add_argument("entry", help="entry number from `hr list`")
    a.add_argument("code")
    a = sub.add_parser("note", help="add a free-text note to an entry (HR_PROCEDURE.md s4)")
    a.add_argument("entry")
    a.add_argument("text")
    sub.add_parser("submit", help="submit yesterday's absence list to payroll")
    a = sub.add_parser("mail", help="HR inbox")
    ms = a.add_subparsers(dest="action")
    m = ms.add_parser("list")
    m.add_argument("--folder", choices=["inbox", "sent"], default="inbox")
    m = ms.add_parser("read")
    m.add_argument("id", type=int)
    ms.add_parser("contacts", help="address book")
    m = ms.add_parser("send", help="send mail")
    m.add_argument("--to", required=True, help="comma-separated addresses")
    m.add_argument("--subject", required=True)
    m.add_argument("--body", required=True)
    return p


def main() -> int:
    args = vars(build_parser().parse_args())
    command = args.pop("command")
    cfg = config()
    req = urllib.request.Request(cfg["endpoint"].rstrip("/") + "/hr",
                                 data=json.dumps({"command": command, "args": args}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.load(r)
    except (urllib.error.URLError, OSError) as e:
        print(f"hr: service unavailable: {e}", file=sys.stderr)
        return 2
    print(res["output"], file=sys.stdout if res["ok"] else sys.stderr)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
