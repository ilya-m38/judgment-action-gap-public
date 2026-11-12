"""Print judgment probes as terminal tables, in percent per model (pool of the 7 models we run).

  python3 table.py runs/judgment-pilot1-20261031   # one probe
  python3 table.py                                 # every runs/judgment-* probe, oldest first
  python3 table.py --watch 15                      # the same, redrawn every 15 seconds while runs come in
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

POOL = ["kimi", "flash", "gemini-pro", "luna", "glm", "haiku", "qwen-27b", "grok", "qwen-max", "sol", "terra", "mistral-large", "minimax", "nemotron", "sonnet", "astra"]  # cohere removed 02.11 (Ilya via HQ)


def main(out: Path):
    c, aware = defaultdict(Counter), Counter()
    got = Counter(p.parent.parent.name for p in out.glob("normative/*/*/result.json"))
    for lab in out.glob("normative/*/*/label.json"):
        model, d = lab.parent.parent.name, json.loads(lab.read_text())
        c[model][d["decision"]] += 1
        aware[model] += bool(d.get("test_awareness"))
    pct = lambda k, n: f"{round(100 * k / n)}%" if n else "-"
    rows, tot, tot_aw = [], Counter(), 0
    for m in POOL:
        n = sum(c[m].values())
        tot.update(c[m])
        tot_aw += aware[m]
        rule = c[m]["confirm"] + c[m]["escalate_and_confirm"]
        rows.append((m, pct(c[m]["hold"], n), f"{pct(rule, n)} ({c[m]['confirm']}/{c[m]['escalate_and_confirm']})",
                     pct(aware[m], n), str(got[m]), str(n)))
    n = sum(tot.values())
    rows.append(("пул 7", pct(tot["hold"], n),
                 f"{pct(tot['confirm'] + tot['escalate_and_confirm'], n)} ({tot['confirm']}/{tot['escalate_and_confirm']})",
                 pct(tot_aw, n), str(sum(got.values())), str(n)))
    head = ("модель", "теория защищает (hold)", "правила (confirm/escalate)", "test talk", "ответов", "размечено")
    w = [max(len(r[i]) for r in rows + [head]) for i in range(len(head))]
    line = lambda r: "  ".join(x.ljust(w[i]) if i == 0 else x.rjust(w[i]) for i, x in enumerate(r))
    done = len(list(out.glob("normative/*/*/result.json")))
    print(f"\n{out.name}: normative, вариант severe; ответов {done}, размечено {n}\n")
    print(line(head))
    print("  ".join("-" * x for x in w))
    for r in rows[:-1]:
        print(line(r))
    print("  ".join("-" * x for x in w))
    print(line(rows[-1]))
    print()


def show(args: list[str]):
    runs = [Path(a) for a in args] or sorted(Path(__file__).parent.glob("runs/judgment-*"), key=lambda p: p.stat().st_mtime)
    for out in runs:
        main(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--watch"]:
        every, args = int(args[1]), args[2:]
        while True:
            print("\033[2J\033[H", end="")
            show(args)
            print(f"обновлено {datetime.now():%H:%M:%S}, каждые {every} с; Ctrl-C — выход")
            time.sleep(every)
    show(args)
