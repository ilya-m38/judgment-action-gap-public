"""The clinic's office host: SMTP relay (587) and platform API (8443) in one process.

One process owns the SQLite state, so there is no cross-container locking.
  python3 office_main.py --state /state
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path

import service
import smtp_server


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--smtp-port", type=int, default=587)
    ap.add_argument("--api-port", type=int, default=8443)
    a = ap.parse_args()
    relay = smtp_server.start(a.state, "0.0.0.0", a.smtp_port)
    httpd = service.serve(a.state, "0.0.0.0", a.api_port, "127.0.0.1", a.smtp_port)

    def stop(*_):
        relay.stop()
        httpd.server_close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    print(json.dumps({"smtp": a.smtp_port, "api": a.api_port}), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
