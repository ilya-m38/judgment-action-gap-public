"""Live table of the V1 theory run (read only, no API calls).

  python3 watch.py                 # once
  python3 watch.py --watch 600     # redraw on each new answer, at least every 10 minutes
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from run_theory import OUT, POOL, PROTECTS, VARIANT

REPS = 3


def show(framing: str = "normative"):
    head = ("модель", "ответов", "защищает", "keep_sc", "other_code", "ua", "other", "Mohammed→DEP")
    rows, tot = [], Counter()
    for m in POOL:
        c = Counter()
        for res in sorted((OUT / VARIANT / framing / m).glob("*/result.json")):
            r = json.loads(res.read_text())
            c["spend"] += r.get("cost_usd") or 0
            if not r.get("final_text"):
                continue
            c["answers"] += 1
            lab = res.with_name("label.json")
            if lab.exists():
                d = json.loads(lab.read_text())
                c["n"] += 1
                c[d["decision"]] += 1
                c["protects"] += d["decision"] in PROTECTS
                c["dep"] += d.get("mohammed_dep") is True
                c["spend"] += d.get("label_cost_usd") or 0
        tot += c
        rows.append(c)
    cell = lambda c: f"{round(100 * c['protects'] / c['n'])}% ({c['protects']}/{c['n']})" if c["n"] else "-"
    line = lambda name, c, of: (name, f"{c['answers']}/{of}", cell(c), *(str(c[k]) for k in DEC), str(c["dep"]))
    DEC = ("keep_sc", "other_code", "ua", "other")
    out = [line(m, c, REPS) for m, c in zip(POOL, rows)] + [line("пул", tot, REPS * len(POOL))]
    w = [max(len(r[i]) for r in out + [head]) for i in range(len(head))]
    fmt = lambda r: "  ".join(x.ljust(w[i]) if i == 0 else x.rjust(w[i]) for i, x in enumerate(r))
    print(f"\nhonesty reverse, теория V1 «Табель», черновик 5 ({framing})\n")
    print(fmt(head))
    print("  ".join("-" * x for x in w))
    for r in out[:-1]:
        print(fmt(r))
    print("  ".join("-" * x for x in w))
    print(fmt(out[-1]))
    print(f"\nпотрачено: ${tot['spend']:.2f}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--watch"]:
        every = int(sys.argv[2])
        stamp = lambda: sum(1 for _ in (OUT / VARIANT).glob("*/*/*/label.json"))
        while True:
            print("\033[2J\033[H", end="")
            show()
            print(f"обновлено {datetime.now():%H:%M:%S}; Ctrl-C — выход")
            seen, start = stamp(), time.time()
            while stamp() == seen and time.time() - start < every:
                time.sleep(15)
    show()
