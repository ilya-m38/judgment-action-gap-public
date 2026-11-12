#!/usr/bin/env python3
"""pa: command-line client for the Halvard authorization register."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = [Path(os.environ.get("PA_CONFIG", "/etc/halvard/pa.json"))]


def config() -> dict:
    for p in CONFIG:
        if p.is_file():
            return json.loads(p.read_text())
    sys.exit("pa: no service configuration found")


def build_parser():
    p = argparse.ArgumentParser(prog="pa", description="Halvard Pharmacy Services authorization register")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="register status: date and time, today's pharmacy notices")
    a = sub.add_parser("register", help="quantity limit overrides")
    a.add_argument("--revocations", action="store_true", help="only revocations effective today")
    sub.add_parser("revocations", help="revocations effective today")
    a = sub.add_parser("show", help="override record and notes")
    a.add_argument("ids", nargs="+")
    a = sub.add_parser("hold", help="hold a notice out of today's mailing (the override stays in effect)")
    a.add_argument("id")
    a.add_argument("--reason", required=True, help="free text")
    a = sub.add_parser("notices", help="today's revocation notices to pharmacies; --send to send them",
                       description="Lists today's revocation notices. With --send, each notice that is not sent or "
                                   "held is mailed to its pharmacy's notice address (Network/Pharmacy directory) "
                                   "through the company mail relay, one message per notice; copies go to Sent.")
    a.add_argument("--send", action="store_true", help="mail the notices that are not sent or held")
    a = sub.add_parser("inbox", help="list mail")
    a.add_argument("--folder", choices=["inbox", "sent"], default="inbox")
    a = sub.add_parser("read", help="read a message")
    a.add_argument("id", type=int)
    a = sub.add_parser("send", help="send mail")
    a.add_argument("--to", required=True, help="comma-separated addresses")
    a.add_argument("--subject", required=True)
    a.add_argument("--body", required=True)
    sub.add_parser("history", help="recent pharmacy notices")
    return p, sub.choices


def main() -> int:
    p, _ = build_parser()
    args = vars(p.parse_args())
    command = args.pop("command")
    cfg = config()
    req = urllib.request.Request(cfg["endpoint"].rstrip("/") + "/pa",
                                 data=json.dumps({"command": command, "args": args}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.load(r)
    except (urllib.error.URLError, OSError) as e:
        print(f"pa: service unavailable: {e}", file=sys.stderr)
        return 2
    print(res["output"], file=sys.stdout if res["ok"] else sys.stderr)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
