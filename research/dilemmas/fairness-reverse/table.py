"""Theory pilot by model: answers done and humane (pay_her) answers, read-only, no API calls.

  python3 table.py                                  # runs/judgment-pilot-20261105
  python3 table.py --watch 15                       # redraw every 15 seconds
  python3 table.py --out runs/<folder> [--watch N]
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POOL = ["kimi", "flash", "gemini-pro", "luna", "glm", "sonnet", "haiku", "qwen-27b", "grok", "sol", "terra",
        "mistral-large", "minimax", "nemotron", "astra"]
PLANNED = 5


def show(out: Path, framing: str = "normative"):
    c = defaultdict(Counter)
    for res in out.glob(f"{framing}/*/*/result.json"):
        m = res.parent.parent.name
        c[m]["done"] += 1
        lab = res.with_name("label.json")
        if lab.exists():
            d = json.loads(lab.read_text())["decision"]
            c[m]["n"] += 1
            c[m][d] += 1
    head = ("модель", "прогонов", "гуманно", "%", "очередь", "эскал.", "делят", "другое")
    rows = []
    for m in POOL + sorted(set(c) - set(POOL)):
        k = c[m]
        pct = f"{round(100 * k['pay_her'] / k['n'])}%" if k["n"] else "-"
        rows.append((m, f"{k['done']}/{PLANNED}", f"{k['pay_her']}/{k['n']}", pct, str(k["queue"]),
                     str(k["escalate_and_queue"]), str(k["split"]), str(k["other"])))
    tot = sum(c.values(), Counter())
    pct = f"{round(100 * tot['pay_her'] / tot['n'])}%" if tot["n"] else "-"
    total = ("пул", f"{tot['done']}/{PLANNED * len(POOL)}", f"{tot['pay_her']}/{tot['n']}", pct, str(tot["queue"]),
             str(tot["escalate_and_queue"]), str(tot["split"]), str(tot["other"]))
    w = [max(len(r[i]) for r in rows + [head, total]) for i in range(len(head))]
    line = lambda r: "  ".join(x.ljust(w[i]) if i == 0 else x.rjust(w[i]) for i, x in enumerate(r))
    print(f"\nСправедливость против гуманности, вариант A: теория {framing}\nгуманно = агент платит Hollie\n")
    print(line(head))
    print("  ".join("-" * x for x in w))
    for r in rows:
        print(line(r))
    print("  ".join("-" * x for x in w))
    print(line(total))
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "runs/judgment-pilot-20261105")
    p.add_argument("--watch", type=int)
    a = p.parse_args()
    while True:
        if a.watch:
            print("\033[2J\033[H", end="")
        show(a.out)
        if not a.watch:
            break
        print(f"обновлено {datetime.now():%H:%M:%S}, каждые {a.watch} с; Ctrl-C — выход")
        time.sleep(a.watch)
