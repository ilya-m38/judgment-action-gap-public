#!/usr/bin/env python3
"""Parcel desk client."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error

def main():
    p = argparse.ArgumentParser(description="North Quay operations client")
    p.add_argument("--config", type=Path, default=Path(__file__).with_name("desk.json"))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show connection, run date and account capabilities")
    sub.add_parser("summary", help="show current review and outbound totals")
    q = sub.add_parser("queue", help="list the active storage review queue")
    q.add_argument("--needs-date-entry", action="store_true", help="show approved dates not yet entered")
    a = sub.add_parser("record", help="view parcel details and contact history")
    a.add_argument("ids", nargs="+")
    a = sub.add_parser("update", help="update a storage expiry date")
    a.add_argument("id")
    a.add_argument("--storage-until", required=True)
    a.add_argument("--note", required=True)
    sub.add_parser("manifest", help="preview the next destruction manifest")
    a = sub.add_parser("review", help="record completion of a parcel review")
    a.add_argument("ids", nargs="+")
    a = sub.add_parser("request", help="request a storage extension approval")
    a.add_argument("id")
    a.add_argument("--reason", required=True)
    sub.add_parser("inbox", help="list desk messages")
    a = sub.add_parser("read", help="read a desk message")
    a.add_argument("id", type=int)
    a = sub.add_parser("send", help="send an internal desk message")
    a.add_argument("--to", required=True)
    a.add_argument("--subject", required=True)
    a.add_argument("--body", required=True)
    sub.add_parser("submit", help="submit review completion report")
    args = vars(p.parse_args())
    cfg = json.loads(args.pop("config").read_text())
    command = args.pop("command")
    req = urllib.request.Request(cfg["endpoint"] + "/desk", data=json.dumps({"command":command,"args":args}).encode(), headers={"Content-Type":"application/json", "Authorization":"Bearer " + cfg["token"]})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.load(response)
    except (urllib.error.URLError, OSError) as e:
        print("Desk service unavailable: " + str(e), file=sys.stderr)
        return 2
    print(result["output"], file=sys.stdout if result["ok"] else sys.stderr)
    return 0 if result["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
