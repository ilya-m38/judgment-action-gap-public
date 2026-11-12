"""Scripted stand-in for model_relay.py: no network, no key, no model. It drives pi through a fixed list of
bash tool calls and then a final message, so the agent's real command environment can be inspected.
Every request body is logged to the relay log, like the real relay."""
import json, os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONFIG = json.loads(Path(os.environ["RELAY_CONFIG"]).read_text())
LOG = Path(CONFIG["log_path"])
SCRIPT = ["desk inbox", "desk read 1", "desk overview | sed -n '/\\[requests\\]/,/\\[queue\\]/p'", "desk queue | awk '$NF==\"yes\" {print $2}' | xargs desk record | head -c 1500"]
STATE = {"n": 0}


def chunk(delta, finish=None):
    return "data: " + json.dumps({"id": "mock", "object": "chat.completion.chunk", "created": 0, "model": "mock",
                                  "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}) + "\n\n"


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        n = STATE["n"]; STATE["n"] += 1
        with LOG.open("a") as f:
            f.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "event": "mock_request", "n": n,
                                "messages": body.get("messages", [])[-1:]}) + "\n")
        if n < len(SCRIPT):
            call = {"index": 0, "id": f"call_{n}", "type": "function",
                    "function": {"name": "bash", "arguments": json.dumps({"command": SCRIPT[n]})}}
            out = chunk({"role": "assistant", "tool_calls": [call]}) + chunk({}, "tool_calls")
        else:
            out = chunk({"role": "assistant", "content": "Preflight finished."}) + chunk({}, "stop")
        out += "data: [DONE]\n\n"
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(out.encode())

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
