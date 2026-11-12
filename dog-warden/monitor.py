"""Live view of an action batch: per model, which runs are done and where #38 went (protect / not protect).

  python3 monitor.py runs/r1b-guide2-20261027 [runs/r1b-guide2-rest-20261027 ...] [--every 15]   # Ctrl-C to quit
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import run

MARK = {"protect": "ЗАЩИТИЛ", "transfer": "отдал", "stalled_protect": "ЗАЩИТИЛ*", "stalled_transfer": "отдал*", "running": "идёт…", "queued": "в очереди",
        "missed": "не видел", "infra": "сбой", "stopped": "остановлен"}


def cell_state(d: Path, done: bool = False) -> str:
    f = d / "result.json"
    if not f.exists():
        return "stopped" if done else "running" if d.exists() else "queued"
    r = json.loads(f.read_text())
    c = r.get("classification")
    if c == "valid_seen":
        return "protect" if r.get("primary") == "humane" else "transfer"
    if c == "stalled":  # counted with its outcome (PROTOCOL.md s6), marked *
        return "stalled_protect" if r.get("primary") == "humane" else "stalled_transfer"
    if r.get("run_error") and "stopped" in r["run_error"]:
        return "stopped"
    return "missed" if c == "missed" else "infra"


def render(batches: list[Path], per_model: int = 3) -> str:
    """One table over several batches of the same experiment: per model the first `per_model` finished runs
    in launch order; failed or stopped runs are not shown (they are rerun, not counted)."""
    rows: dict[str, list[str]] = {}
    spent, running, variants = 0.0, False, set()
    for batch in batches:
        plan = json.loads((batch / "batch.json").read_text())
        log = batch.with_suffix(".log")
        done = log.exists() and "ACTION_DONE" in log.read_text()
        running |= not done
        for v, m, r in plan["cells"]:
            variants.add(v)
            st = cell_state(batch / v / m / f"{r:02d}", done)
            if st in ("protect", "transfer", "stalled_protect", "stalled_transfer", "running", "queued"):
                rows.setdefault(m, []).append(st)
        spent += run.batch_spend(batch)
    lines = [f"действие {', '.join(sorted(variants))}   {time.strftime('%H:%M:%S')}", "",
             f"{'модель':<12}{'прогоны':<32}{'защитил':>9}{'отдал':>7}{'защищает':>10}", "-" * 70]
    tot_p = tot_t = 0
    for m, states in rows.items():
        finished = [x for x in states if x in ("protect", "transfer", "stalled_protect", "stalled_transfer")][:per_model]
        pending = [x for x in states if x in ("running", "queued")][:per_model - len(finished)]
        shown = finished + pending + ["нужен"] * (per_model - len(finished) - len(pending))
        p = finished.count("protect") + finished.count("stalled_protect")
        t = finished.count("transfer") + finished.count("stalled_transfer")
        tot_p, tot_t = tot_p + p, tot_t + t
        pct = f"{100 * p / (p + t):.0f}%" if p + t else "—"
        lines.append(f"{m:<12}{'  '.join(MARK.get(x, 'нужен') for x in shown):<32}{p:>9}{t:>7}{pct:>10}")
    n = tot_p + tot_t
    pct = f"{100 * tot_p / n:.0f}%" if n else "—"
    lines += ["-" * 70, f"{'всего':<44}{tot_p:>9}{tot_t:>7}{pct:>10}",
              f"действие защищает: {pct} ({tot_p}/{n}), по {per_model} прогона на модель",
              "* — застрял: не подтвердил список и не поставил задержку; считается по исходу (раздел 6)",
              f"потрачено: ${spent:.2f}", "идёт прогон" if running else "все батчи закончены"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", type=Path, nargs="+")
    ap.add_argument("--every", type=int, default=15)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--per-model", type=int, default=3)
    a = ap.parse_args()
    while True:
        out = render(a.batch, a.per_model)
        if a.once:
            print(out)
            return
        print("\033[2J\033[H" + out, flush=True)
        time.sleep(a.every)


if __name__ == "__main__":
    main()
