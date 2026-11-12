"""Theory on draft 15 by question: share of hold per model for all four framings (read-only, no API calls).

  python3 framings.py                  # runs/judgment-draft15-20261105 (all 16 models)
  python3 framings.py --watch 15       # redraw every 15 seconds
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from gap import POOL, THEORY, THEORY_OVERRIDE

FRAMINGS = ("normative", "self", "typical_ai", "typical_employee")


def counts() -> dict:
    c = defaultdict(Counter)
    for m in POOL:
        run = THEORY_OVERRIDE.get(m, THEORY)
        for f in FRAMINGS:
            c[m, f]["answers"] = len(list(run.glob(f"{f}/{m}/*/result.json")))
            for lab in run.glob(f"{f}/{m}/*/label.json"):
                c[m, f]["n"] += 1
                c[m, f]["hold"] += json.loads(lab.read_text())["decision"] == "hold"
    return c


def show():
    c = counts()
    head = ("модель",) + FRAMINGS
    cell = lambda k: f"{round(100 * k['hold'] / k['n'])}% ({k['hold']}/{k['n']})" if k["n"] else f"- ({k['answers']})"
    rows = [(m,) + tuple(cell(c[m, f]) for f in FRAMINGS) for m in POOL]
    tot = [sum((c[m, f] for m in POOL), Counter()) for f in FRAMINGS]
    rows.append(("пул",) + tuple(cell(t) for t in tot))
    w = [max(len(r[i]) for r in rows + [head]) for i in range(len(head))]
    line = lambda r: "  ".join(x.ljust(w[i]) if i == 0 else x.rjust(w[i]) for i, x in enumerate(r))
    print("\neviction-freeze: теория, черновик 15, hold по вопросам\n")
    print(line(head))
    print("  ".join("-" * x for x in w))
    for r in rows[:-1]:
        print(line(r))
    print("  ".join("-" * x for x in w))
    print(line(rows[-1]))
    print()


if __name__ == "__main__":
    if sys.argv[1:2] == ["--watch"]:
        every = int(sys.argv[2])
        while True:
            print("\033[2J\033[H", end="")
            show()
            print(f"обновлено {datetime.now():%H:%M:%S}, каждые {every} с; Ctrl-C — выход")
            time.sleep(every)
    show()
