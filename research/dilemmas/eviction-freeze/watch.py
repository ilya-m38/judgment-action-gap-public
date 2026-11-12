"""Live table of an eviction-freeze action batch (read-only, no API calls). Theory probes: table.py.

  python3 -I watch.py runs/20261106-140000          # refresh every 5 s, Ctrl-C to stop
  python3 -I watch.py runs/20261106-140000 --once
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

POOL = ["kimi", "flash", "gemini-pro", "luna", "glm", "haiku", "qwen-27b", "grok", "qwen-max", "sol", "terra", "mistral-large", "minimax", "nemotron", "sonnet", "astra"]  # cohere removed 02.11 (Ilya via HQ)


def relay_cost(path: Path) -> float:
    total = 0.0
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "completion":
                total += (e.get("usage") or {}).get("cost") or 0
    return total


def table(out: Path):
    rows = [f"eviction-freeze action batch ({out.name})   {time.strftime('%H:%M:%S')}", ""]
    for variant in ("severe", "nochild", "routine"):
        res, spend = defaultdict(Counter), 0.0
        for p in sorted(out.glob(f"{variant}/*/*/result.json")):
            r = json.loads(p.read_text())
            m = p.parent.parent.name
            spend += relay_cost(p.with_name("relay.jsonl"))
            c = r.get("classification")
            res[m][c] += 1
            if c in ("valid_seen", "stalled"):
                res[m][r["primary"]] += 1
                res[m]["hold_all"] += bool(r.get("hold_all"))
                res[m]["early_end"] += bool(r.get("ended_before_replies"))
        if not res:
            continue
        rows += [f"{variant}   spend ${spend:.2f}",
                 f"  {'model':<12}{'runs':>5}{'humane':>8}{'procedural':>11}{'missed':>8}{'stalled':>8}"
                 f"{'hold_all':>9}{'ended early':>12}{'infra':>6}"]
        tot = Counter()
        for m in [x for x in POOL if x in res] + sorted(set(res) - set(POOL)):
            c = res[m]
            n = sum(c[k] for k in ("valid_seen", "stalled", "missed", "infra", "provider_blocked"))
            rows.append(f"  {m:<12}{n:>5}{c['humane']:>8}{c['procedural']:>11}{c['missed']:>8}{c['stalled']:>8}"
                        f"{c['hold_all']:>9}{c['early_end']:>12}{c['infra'] + c['provider_blocked']:>6}")
            tot.update(c)
        k = tot["humane"] + tot["procedural"]
        if k:
            rows.append(f"  humane {100 * tot['humane'] // k}% of {k} scored runs (missed and infra left out)")
        rows.append("")
    return "\n".join(rows)


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    if "--once" in sys.argv:
        print(table(out))
        sys.exit()
    while True:
        print("\033[2J\033[H" + table(out), flush=True)
        time.sleep(5)
