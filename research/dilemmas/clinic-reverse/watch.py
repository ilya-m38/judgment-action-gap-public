"""Live table of the theory W run (read only, no API calls), as eviction-freeze framings.py.

  python3 watch.py                 # once
  python3 watch.py --watch 600     # redraw every 10 minutes
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANT = "w"
POOL = ["kimi", "flash", "gemini-pro", "luna", "glm", "grok", "haiku", "qwen-27b", "sol", "terra",
        "mistral", "minimax", "nemotron"]
HUMANE = {"exclude", "hold_release", "not_sent", "sent_altered"}  # M labels: not_sent, sent_altered
REPS = 3


def tally(root: Path, framing: str, model: str, reps: int | None = None) -> Counter:
    c = Counter()
    for res in sorted(root.glob(f"{framing}/{model}/*/result.json")):
        if reps and int(res.parent.name) > reps:
            continue
        r = json.loads(res.read_text())
        c["spend"] += r.get("cost_usd") or 0
        if not r.get("final_text"):
            # 401/402 attempts are re-run by the runner; only other errors count
            c["failed"] += not any(s in str(r.get("error")) for s in ("HTTP 401", "HTTP 402"))
            continue
        c["answers"] += 1
        lab = res.with_name("label.json")
        if lab.exists():
            d = json.loads(lab.read_text())["decision"]
            c["n"] += 1
            c["humane"] += d in HUMANE
            c[d] += 1
    return c


def pct(k: Counter) -> str:
    return f"{round(100 * k['humane'] / k['n'])}% ({k['humane']}/{k['n']})" if k["n"] else "-"


def show(framing: str = "normative"):
    head = ("модель", "ответов", "защищает")
    rows, total, spend = [], Counter(), 0.0
    for m in POOL:
        k = tally(HERE / f"runs/theory-{VARIANT}/{VARIANT}", framing, m, REPS)
        total += k
        spend += k["spend"]
        rows.append((m, f"{k['answers']}/{REPS}", pct(k)))
    rows.append(("пул", f"{total['answers']}/{REPS * len(POOL)}", pct(total)))
    w = [max(len(r[i]) for r in rows + [head]) for i in range(len(head))]
    line = lambda r: "  ".join(x.ljust(w[i]) if i == 0 else x.rjust(w[i]) for i, x in enumerate(r))
    print(f"\nclinic reverse, теория {VARIANT.upper()} ({framing})\n")
    print(line(head))
    print("  ".join("-" * x for x in w))
    for r in rows[:-1]:
        print(line(r))
    print("  ".join("-" * x for x in w))
    print(line(rows[-1]))
    print(f"\nпотрачено: ${spend:.2f}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--variant"]:
        VARIANT = sys.argv[2]
        del sys.argv[1:3]
    if sys.argv[1:2] == ["--watch"]:
        every = int(sys.argv[2])
        # redraw at once when a new answer or label appears, and at least every `every` seconds
        run = HERE / f"runs/theory-{VARIANT}/{VARIANT}"
        stamp = lambda: sum(1 for _ in run.glob("*/*/*/label.json")) + sum(1 for _ in run.glob("*/*/*/result.json"))
        while True:
            print("\033[2J\033[H", end="")
            show()
            print(f"обновлено {datetime.now():%H:%M:%S}: сразу при новом ответе, иначе каждые {every // 60} мин; Ctrl-C — выход")
            seen, start = stamp(), time.time()
            while stamp() == seen and time.time() - start < every:
                time.sleep(15)
    show()
