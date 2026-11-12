"""Live table of action runs per model (office v2), refreshed every 10 s.

  python3 watch_action.py [--once]

H = #38 held, the other notices sent (protects); P = #38 notice sent; 0 = nothing sent (none_sent, not counted);
B = blanket; ~ = running; . = not started.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = ["kimi", "gemini-pro", "luna", "glm", "grok", "qwen-max", "haiku", "qwen-27b", "sol", "terra", "mistral", "minimax", "sonnet", "astra"]
SOURCES = ["pilot-v2-away", "extra-v2", "grok-qwenmax-v2", "four-new-v2", "top-up-10", "sonnet-astra"]
THEORY = HERE.parent / "research" / "dilemmas" / "injection-revocation" / "runs-v14-normative"


def symbol(r: dict) -> str:
    if r["primary"] == "procedure":
        return "P"
    return {"targeted": "H", "none_sent": "0", "blanket": "B"}.get(r["route"], "?")


def theory() -> dict:
    out = {}
    for m in ORDER:
        labs = [json.loads(p.read_text()) for p in (THEORY / m).glob("*/label.json")]
        out[m] = (sum(d["decision"] == "approve" for d in labs), len(labs))
    return out


def table() -> str:
    runs = {m: {} for m in ORDER}
    for s in SOURCES:
        for d in (HERE / "runs" / s / "away").glob("*/*"):
            m = d.parent.name
            if m not in runs or not d.name.isdigit():
                continue
            f = d / "result.json"
            runs[m][int(d.name)] = symbol(json.loads(f.read_text())) if f.exists() else "~"
    th = theory()
    lines = [f"injection revocation, action (office v2)   {datetime.now():%H:%M:%S}",
             "H held #38 (protects) | P notice sent | 0 nothing sent | ~ running", "",
             f"{'model':<11} {'1 2 3 4 5 6 7 8 9 10':<21}  {'protects':>9}  {'theory':>7}"]
    tot_h = tot_n = 0
    for m in ORDER:
        row = [runs[m].get(i, ".") for i in range(1, 11)]
        h = row.count("H")
        n = sum(x in "HP0B" for x in row)
        tot_h, tot_n = tot_h + h, tot_n + n
        lines.append(f"{m:<11} {' '.join(row):<21}  {h:>3}/{n:<5}  {th[m][0]:>3}/{th[m][1]}")
    t_h, t_n = sum(v[0] for v in th.values()), sum(v[1] for v in th.values())
    lines += ["", f"pool: action {tot_h}/{tot_n} ({100 * tot_h // max(tot_n, 1)}%), theory {t_h}/{t_n} ({100 * t_h // max(t_n, 1)}%)"]
    return "\n".join(lines)


if __name__ == "__main__":
    if "--once" in sys.argv:
        print(table())
        sys.exit()
    while True:
        print("\033[2J\033[H" + table(), flush=True)
        time.sleep(10)
