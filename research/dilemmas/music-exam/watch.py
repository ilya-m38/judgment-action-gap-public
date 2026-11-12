"""Live table of a music-exam theory pilot (read-only, no API calls).

  python3 -I watch.py runs/judgment-pilot7-20261031          # refresh every 5 s, Ctrl-C to stop
  python3 -I watch.py runs/judgment-pilot7-20261031 --once
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

POOL = ["kimi", "flash", "gemini-pro", "luna", "glm", "haiku", "qwen-27b"]  # sonnet is not shown
REPS = 5


def table(out: Path):
    lab, done, errors, aware, spend = defaultdict(Counter), Counter(), Counter(), Counter(), 0.0
    for p in sorted(out.glob("normative/*/*/result.json")):
        r = json.loads(p.read_text())
        m = r["model"]
        spend += r.get("cost_usd") or 0
        if not r.get("completed"):
            errors[m] += 1
            continue
        done[m] += 1
        t = p.with_name("label.json")
        if t.exists():
            d = json.loads(t.read_text())
            lab[m][d["decision"]] += 1
            aware[m] += bool(d.get("test_awareness"))
            spend += d.get("label_cost_usd") or 0
    rows = [f"music exam theory pilot ({out.name})   {time.strftime('%H:%M:%S')}   spend ${spend:.2f}", "",
            f"{'model':<19}{'answers':>8}{'labelled':>9}   {'protects (add)':<16}{'rules (without / +mail)':<25}"
            f"{'other':>5}{'err':>5}{'test talk':>10}"]
    tot, tot_aware = Counter(), 0
    for m in POOL:
        c = lab[m]
        n = sum(c.values())
        rules = c["publish_without"] + c["escalate_and_publish_without"]
        pct = lambda k: f"{100 * k // n:>3}% ({k}/{n})" if n else "-"
        rows.append(f"{m:<19}{done[m]:>4}/{REPS:<3}{n:>9}   {pct(c['add']):<16}"
                    f"{(pct(rules) + f' {c['publish_without']}/{c['escalate_and_publish_without']}') if n else '-':<25}"
                    f"{c['other']:>5}{errors[m]:>5}{(f'{aware[m]}/{n}' if n else '-'):>10}")
        tot.update(c)
        tot_aware += aware[m]
    n = sum(tot.values())
    if n:
        rows += ["", f"pool of 7: protects {100 * tot['add'] // n}% ({tot['add']}/{n}), rules "
                 f"{100 * (tot['publish_without'] + tot['escalate_and_publish_without']) // n}%, "
                 f"test talk {tot_aware}/{n}"]
    elif sum(done.values()):
        rows += ["", "Haiku labels each answer within ~20 s of its arrival"]
    return "\n".join(rows)


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    if "--once" in sys.argv:
        print(table(out))
        sys.exit()
    while True:
        print("\033[2J\033[H" + table(out), flush=True)
        time.sleep(5)
