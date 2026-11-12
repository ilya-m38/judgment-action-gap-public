"""Theory vs action per model, in percent (read-only, no API calls).

  python3 gap.py                       # theory: runs/judgment-draft14-20261102; action: every runs/action-pilot*
  python3 gap.py --watch 15            # redraw every 15 seconds

Theory: share of normative answers labelled hold. Action: share of scored severe runs where the agent held Kerry's
case before submission (missed and infra runs are left out and shown separately). Gap = theory - action.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THEORY = ROOT / "runs" / "judgment-draft15-20261105"  # draft 15 (05.11, HQ audit); draft 14: judgment-draft14-20261102
# Per-model theory runs other than THEORY (none now: command-a, retried at medium, left the pool 02.11)
THEORY_OVERRIDE: dict[str, Path] = {}  # all 16 models in THEORY since draft 15
POOL = ["kimi", "flash", "gemini-pro", "luna", "glm", "haiku", "qwen-27b", "grok", "qwen-max", "sol", "terra",
        "mistral-large", "minimax", "nemotron", "sonnet", "astra"]  # cohere (command-a) removed 02.11 (Ilya via HQ); its data stay in runs/


def theory() -> dict:
    c = defaultdict(Counter)
    for lab in THEORY.glob("normative/*/*/label.json"):
        if lab.parent.parent.name not in THEORY_OVERRIDE:
            c[lab.parent.parent.name][json.loads(lab.read_text())["decision"]] += 1
    for m, run in THEORY_OVERRIDE.items():  # first 10 answers that finished; looped ones are only a repeated fragment
        done = [lab for lab in sorted(run.glob(f"normative/{m}/*/label.json"))
                if json.loads((lab.parent / "result.json").read_text()).get("completed")]
        for lab in done[:10]:
            c[m][json.loads(lab.read_text())["decision"]] += 1
    return c


def action(variant: str) -> dict:
    c = defaultdict(Counter)
    for res in ROOT.glob(f"runs/action-pilot*/{variant}/*/*/result.json"):
        r = json.loads(res.read_text())
        m, cls = res.parent.parent.name, r.get("classification")
        if cls in ("missed", "infra", "provider_blocked"):
            c[m][cls] += 1
            continue
        c[m]["n"] += 1
        c[m]["hold"] += r.get("primary") == "humane"
    return c


def show():
    th, ac, rt = theory(), action("severe"), action("routine")
    pct = lambda k, n: f"{round(100 * k / n)}%" if n else "-"
    head = ("модель", "теория hold", "действие hold", "разрыв", "routine hold", "missed/infra")
    rows, tot = [], Counter()
    for m in POOL:
        tn, th_h = sum(th[m].values()), th[m]["hold"]
        an, ah = ac[m]["n"], ac[m]["hold"]
        gap = f"{round(100 * th_h / tn - 100 * ah / an):+d} п.п." if tn and an else "-"
        rows.append((m, f"{pct(th_h, tn)} ({th_h}/{tn})", f"{pct(ah, an)} ({ah}/{an})", gap,
                     f"{rt[m]['hold']}/{rt[m]['n']}", f"{ac[m]['missed']}/{ac[m]['infra'] + ac[m]['provider_blocked']}"))
        tot.update({"tn": tn, "th": th_h, "an": an, "ah": ah})
    gap = (f"{round(100 * tot['th'] / tot['tn'] - 100 * tot['ah'] / tot['an']):+d} п.п."
           if tot["tn"] and tot["an"] else "-")
    rows.append(("пул", f"{pct(tot['th'], tot['tn'])}", f"{pct(tot['ah'], tot['an'])} ({tot['ah']}/{tot['an']})", gap,
                 "", ""))
    w = [max(len(r[i]) for r in rows + [head]) for i in range(len(head))]
    line = lambda r: "  ".join(x.ljust(w[i]) if i == 0 else x.rjust(w[i]) for i, x in enumerate(r))
    print("\neviction-freeze: теория (черновик 15) против действия (severe)\n")
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
