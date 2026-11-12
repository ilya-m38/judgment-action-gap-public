"""Live table of the injection revocation (former C1) theory probe (read-only, no API calls).

  python3 -I watch.py            # refresh every 10 s, Ctrl-C to stop
  python3 -I watch.py --once
  python3 -I watch.py --runs runs-v13-retold --reps kimi=3 gemini-pro=2   # another folder; answers expected per model
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARGS = sys.argv[1:]
RUNS = HERE / (ARGS[ARGS.index("--runs") + 1] if "--runs" in ARGS else "runs")
EXPECT = {k: int(v) for k, v in (x.split("=") for x in ARGS if "=" in x)}  # answers expected per model
ORDER = ["kimi", "flash", "gemini-pro", "luna", "glm", "grok", "qwen-max", "haiku", "qwen-27b", "sol", "terra",
         "mistral", "minimax", "nemotron", "sonnet"]
REPS = int(ARGS[ARGS.index("--n") + 1]) if "--n" in ARGS else 5  # answers expected per model by default


def table():
    lab, done, errors, blocked, spend = defaultdict(Counter), Counter(), Counter(), Counter(), 0.0
    for p in sorted(RUNS.glob("*/*/result.json")):
        r = json.loads(p.read_text())
        m = r["model"]
        spend += r.get("cost_usd") or 0
        if r.get("error"):
            errors[m] += 1  # HTTP error (e.g. 402); the cell is retried on the next run
            continue
        if not r.get("final_text") or r.get("finish_reason") == "content_filter":
            blocked[m] += 1
            continue
        done[m] += 1
        t = p.with_name("label.json")
        if t.exists():
            lab[m][json.loads(t.read_text())["decision"]] += 1
    v = RUNS / "vignette.txt"
    rows = [f"injection revocation theory probe   {time.strftime('%H:%M:%S')}   spend ${spend:.2f}",
            f"question: {v.read_text().strip() if v.exists() else '?'}", "",
            f"{'model':<11}{'answers':>8}{'labelled':>9}   {'hold (protects)':<20}{'rules (send / +esc)':<22}"
            f"{'other':>5}{'filter':>7}{'http err':>9}"]
    tot = Counter()
    present = {p.parent.parent.name for p in RUNS.glob("*/*/result.json")}
    models = [m for m in ORDER if m in present] + sorted(present - set(ORDER))
    for m in models:
        c = lab[m]
        n = sum(c.values())
        rules = c["route"] + c["route_and_escalate"]
        pct = lambda k: f"{k}/{n} {100 * k // n:>3}%" if n else "-"
        rows.append(f"{m:<11}{done[m]:>4}/{EXPECT.get(m, REPS):<3}{n:>9}   {pct(c['approve']):<20}"
                    f"{pct(rules) + f' ({c['route']}/{c['route_and_escalate']})' if n else '-':<22}"
                    f"{c['other']:>5}{blocked[m]:>7}{errors[m]:>9}")
        tot.update(c)
    n = sum(tot.values())
    if n:
        rows += ["", f"all models: hold {100 * tot['approve'] // n}%, rules "
                 f"{100 * (tot['route'] + tot['route_and_escalate']) // n}%  (n={n})"]
    elif sum(done.values()):
        rows += ["", "labels come after all answers are in (Haiku labels the whole run at the end)"]
    return "\n".join(rows)


if __name__ == "__main__":
    if "--once" in sys.argv:
        print(table())
        sys.exit()
    while True:
        print("\033[2J\033[H" + table(), flush=True)
        time.sleep(10)
