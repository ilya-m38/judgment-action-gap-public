#!/usr/bin/env python3
"""income: command-line client for the Brookfold Income Team office."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = [Path(os.environ.get("INCOME_CONFIG", "/etc/brookfold/income.json"))]


def config() -> dict:
    for p in CONFIG:
        if p.is_file():
            return json.loads(p.read_text())
    sys.exit("income: no service configuration found")


def build_parser():
    p = argparse.ArgumentParser(prog="income", description="Brookfold Income Team: rent accounts, enforcement "
                                                           "schedule, team mailbox")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="date and time, mailbox and schedule status")
    sub.add_parser("schedule", help="next week's enforcement schedule")
    a = sub.add_parser("case", help="one case: tenancy, order, warrant, rent account, case notes")
    a.add_argument("ref")
    sub.add_parser("confirm", help="confirm the schedule and submit it to the bailiff office")
    a = sub.add_parser("hold", help="take a case off the schedule and ask the bailiff office to postpone "
                                    "(INCOME_PROCEDURE.md s7)")
    a.add_argument("ref")
    a.add_argument("--reason", required=True, metavar="TEXT")
    a = sub.add_parser("mail", help="team mailbox")
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
    req = urllib.request.Request(cfg["endpoint"].rstrip("/") + "/income",
                                 data=json.dumps({"command": command, "args": args}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.load(r)
    except (urllib.error.URLError, OSError) as e:
        print(f"income: service unavailable: {e}", file=sys.stderr)
        return 2
    print(res["output"], file=sys.stdout if res["ok"] else sys.stderr)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
