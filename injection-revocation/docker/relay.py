"""Model relay: holds the OpenRouter key, enforces the model allowlist, logs usage. Stdlib only.

Adapted from the Euryla relay (judgment-action-gap-environment). The spend cap
lives on the OpenRouter key itself, so this relay keeps only a per-run request cap.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

UPSTREAM = "https://openrouter.ai/api/v1/chat/completions"
CONFIG = json.loads(Path(os.environ["RELAY_CONFIG"]).read_text(encoding="utf-8"))
MODELS: dict[str, dict] = CONFIG["models"]
MAX_REQUESTS = int(CONFIG["max_requests"])
MAX_OUTPUT_TOKENS = int(CONFIG.get("max_output_tokens", 8192))
RETRIES = int(CONFIG.get("retries", 8))
LOG = Path(CONFIG["log_path"])
KEY_FILE = Path(os.environ.get("OPENROUTER_SECRET_FILE", "/run/secrets/openrouter_api_key"))
LOCK = Lock()
STATE = {"requests": 0}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(NoRedirect())


def log(**record: object) -> None:
    with LOCK, LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                                 **record}, sort_keys=True) + "\n")


def usage_from_stream(raw: bytes) -> dict:
    usage, meta, model = {}, {}, None
    for line in raw.splitlines():
        if not line.startswith(b"data: ") or line[6:] == b"[DONE]":
            continue
        try:
            event = json.loads(line[6:])
        except ValueError:
            continue
        if isinstance(event, dict):
            model = event.get("model") or model
            if isinstance(event.get("usage"), dict):
                usage = event["usage"]
            if isinstance(event.get("openrouter_metadata"), dict):
                meta = event["openrouter_metadata"]
    selected = [e for e in meta.get("endpoints", {}).get("available", [])
                if isinstance(e, dict) and e.get("selected")]
    return {"resolved_model": model, "usage": usage,
            "provider": selected[0].get("provider") if selected else None}


def forward(raw: bytes) -> tuple[int, str, bytes]:
    body = json.loads(raw)
    model = body.get("model")
    params = {k: v for k, v in body.items() if k not in ("messages", "tools")}
    if model not in MODELS:
        log(event="denied", reason="model not allowed", model=model)
        return 403, "application/json", b'{"error":"model not allowed"}'
    with LOCK:
        if STATE["requests"] >= MAX_REQUESTS:
            denied = True
        else:
            STATE["requests"] += 1
            denied = False
    if denied:
        log(event="denied", reason="request cap reached", model=model)
        return 429, "application/json", b'{"error":"request limit reached"}'
    for field in ("models", "route", "plugins"):
        body.pop(field, None)
    body["max_tokens"] = min(int(body.pop("max_completion_tokens", 0) or body.get("max_tokens")
                                 or MAX_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS)
    if body.get("stream"):
        body["stream_options"] = {**(body.get("stream_options") or {}), "include_usage": True}
    body["provider"] = {"only": [MODELS[model]["provider"]], "allow_fallbacks": False}
    payload = json.dumps(body, ensure_ascii=False).encode()
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    request = Request(UPSTREAM, data=payload, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "X-OpenRouter-Metadata": "enabled"})
    started = time.monotonic()
    # Retry rate limits and provider errors with backoff; each failure is logged.
    for attempt in range(RETRIES + 1):
        try:
            with OPENER.open(request, timeout=300) as response:
                data = response.read()
                status, ctype = response.status, response.headers.get("Content-Type", "application/json")
            break
        except HTTPError as exc:
            detail = exc.read()[:2000].decode("utf-8", "replace")
            log(event="upstream_error", model=model, http_status=exc.code, detail=detail, attempt=attempt,
                elapsed_ms=int((time.monotonic() - started) * 1000))
            if exc.code != 429 and exc.code < 500 or attempt == RETRIES:
                return 502, "application/json", b'{"error":"upstream error"}'
        except Exception as exc:  # noqa: BLE001
            log(event="upstream_error", model=model, error=type(exc).__name__, attempt=attempt,
                elapsed_ms=int((time.monotonic() - started) * 1000))
            if attempt == RETRIES:
                return 502, "application/json", b'{"error":"upstream unavailable"}'
        time.sleep(min(120, 5 * 2 ** attempt))
    info = usage_from_stream(data) if body.get("stream") else {
        "usage": json.loads(data).get("usage"), "resolved_model": json.loads(data).get("model"),
        "provider": json.loads(data).get("provider")}
    log(event="completion", model=model, request_no=STATE["requests"], http_status=status, params=params,
        n_messages=len(body.get("messages") or []), n_tools=len(body.get("tools") or []),
        elapsed_ms=int((time.monotonic() - started) * 1000), request_bytes=len(raw),
        response_bytes=len(data), **info)
    return status, ctype, data


class Handler(BaseHTTPRequestHandler):
    # no Server and Date headers: Date carried the host's real time outside faketime (8388c69)
    def send_response(self, code, message=None):
        self.log_request(code)
        self.send_response_only(code, message)
        self.send_header("Server", "pa-gw/3.1" if self.server.server_port == 8000 else "gateway")

    def send_error(self, code, message=None, explain=None):  # no http.server error page
        body = b'{"ok": false}'
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._reply(200 if self.path == "/health" else 404, "application/json", b'{"status":"ok"}')

    def do_POST(self):  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._reply(404, "application/json", b'{"error":"not found"}')
            return
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self._reply(*forward(raw))
        except Exception as exc:  # noqa: BLE001
            log(event="handler_error", error=type(exc).__name__)
            self._reply(400, "application/json", b'{"error":"invalid request"}')

    def _reply(self, status: int, ctype: str, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.daemon_threads = True
    server.serve_forever(poll_interval=0.25)


if __name__ == "__main__":
    main()
