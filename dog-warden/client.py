#!/usr/bin/env python3
"""kennel: command-line client for the Meadowbank kennel register."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = [Path(os.environ.get("KENNEL_CONFIG", "/etc/meadowbank/kennel.json"))]


def config() -> dict:
    for p in CONFIG:
        if p.is_file():
            return json.loads(p.read_text())
    sys.exit("kennel: no service configuration found")


def build_parser():
    """The CLI's parser and its subcommand parsers (the judgment texts print the same help)."""
    p = argparse.ArgumentParser(prog="kennel", description="Meadowbank Animal Services kennel register")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="register status: date and time, day-8 list")
    a = sub.add_parser("register", help="dogs in care")
    a.add_argument("--day8", action="store_true", help="only dogs on today's day-8 list")
    a = sub.add_parser("dog", help="dog record and owner contact log")
    a.add_argument("ids", nargs="+")
    a = sub.add_parser("hold", help="enter a hold (dog stays in kennels and leaves the day-8 list)")
    a.add_argument("id")
    a.add_argument("--until", required=True, help="YYYY-MM-DD")
    a.add_argument("--reason", required=True, help="free text")
    a = sub.add_parser("transfers", help="show the day-8 list; --confirm to confirm it")
    a.add_argument("--confirm", action="store_true")
    a = sub.add_parser("inbox", help="list mail")
    a.add_argument("--folder", choices=["inbox", "sent"], default="inbox")
    a = sub.add_parser("read", help="read a message")
    a.add_argument("id", type=int)
    a = sub.add_parser("send", help="send mail (company and rehoming partner addresses)")
    a.add_argument("--to", required=True, help="comma-separated addresses")
    a.add_argument("--subject", required=True)
    a.add_argument("--body", required=True)
    sub.add_parser("history", help="recent days")
    return p, sub.choices


def main() -> int:
    p, _ = build_parser()
    args = vars(p.parse_args())
    command = args.pop("command")
    cfg = config()
    req = urllib.request.Request(cfg["endpoint"].rstrip("/") + "/kennel",
                                 data=json.dumps({"command": command, "args": args}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.load(r)
    except (urllib.error.URLError, OSError) as e:
        print(f"kennel: service unavailable: {e}", file=sys.stderr)
        return 2
    print(res["output"], file=sys.stdout if res["ok"] else sys.stderr)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
