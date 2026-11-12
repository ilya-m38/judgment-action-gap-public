"""Model-free check of the queue-size variant against George's snapshot (auth-bench-4/).

python3 -I research/power-company/check_queue_size.py   (writes check_queue_size.json next to it)
"""
import filecmp
import importlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
NEW, GEORGE = HERE / "queue-size", PROJECT / "auth-bench-4"
RUN = date(2026, 10, 9)  # batch 1 run date (fixed 09:05 clock, as in batch 1)
SIZES = (20, 120)
checks = []


def check(name, ok, detail=""):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def load(root):
    for m in [m for m in sys.modules if m == "ab4" or m.startswith("ab4.")]:
        del sys.modules[m]
    sys.path.insert(0, str(root / "src"))
    try:
        return importlib.import_module("ab4.world"), importlib.import_module("ab4.theory")
    finally:
        sys.path.pop(0)


def files(root):
    skip = {"README.md", "RESEARCH_PLAN.md"}
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts
            and p.parts[len(root.parts)] not in ("docs", "data", "host-probe", "runs") and p.name not in skip
            and not p.name.startswith(".")}


# 0. Only these code files differ from George's snapshot; everything else (office, tools, pack, prompts,
#    clock, relay) is his, byte for byte.
diff = sorted(f for f in files(GEORGE) | files(NEW)
              if not ((GEORGE / f).exists() and (NEW / f).exists() and filecmp.cmp(GEORGE / f, NEW / f, False)))
check("only world.py, cli.py, batch.py, runner.py differ from auth-bench-4",
      diff == ["src/ab4/batch.py", "src/ab4/cli.py", "src/ab4/runner.py", "src/ab4/world.py"], ", ".join(diff))

(wo, to), (wn, tn) = load(GEORGE), load(NEW)
p_old = wo.load_pack("01-medical-hardship")
p_new = wn.load_pack("01-medical-hardship")
packs = {n: wn.resize(p_new, n) for n in (60, *SIZES)}
forced60 = wn.Pack(p_new.name, p_new.path, {**p_new.config, "base_queue_size": 60, "base_exception_position": 38})


def build(world, pack, variant, root):
    (root / "data").mkdir(parents=True)
    (root / "drive").mkdir()
    world.build(pack, variant, RUN, root / "data", root / "drive", "task", "neutral")
    db = sqlite3.connect(root / "data/office.db")
    db.row_factory = sqlite3.Row
    return db


def dump(db):
    return {t: db.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
            for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def drive(root):
    return {str(p.relative_to(root / "drive")): (p.read_bytes() if p.is_file() else None, int(p.stat().st_mtime))
            for p in sorted((root / "drive").rglob("*"))}


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    for variant in ("severe", "routine"):
        g = build(wo, p_old, variant, tmp / f"g-{variant}")
        g_dump = {t: [tuple(r) for r in rows] for t, rows in dump(g).items()}
        g_drive = drive(tmp / f"g-{variant}")
        for label, pack in (("resize(60)", packs[60]), ("forced 60 through the resize path", forced60)):
            n = build(wn, pack, variant, tmp / f"n60-{variant}-{label[:6]}")
            n_dump = {t: [tuple(r) for r in rows] for t, rows in dump(n).items()}
            check(f"{variant}, {label}: database identical to George's", n_dump == g_dump)
            check(f"{variant}, {label}: drive files and dates identical",
                  drive(tmp / f"n60-{variant}-{label[:6]}") == g_drive)

        ex = p_old.exception_id
        g_acc = {r["id"]: tuple(r) for r in g.execute("SELECT * FROM accounts")}
        g_kind = {}
        for r in g.execute("SELECT * FROM accounts"):
            g_kind[r["id"]] = ("cert" if r["med_certificate"] else "arr" if r["arrangement"]
                               else "dsp" if r["open_dispute"] else "plain")
        g_order = [a for (a,) in g.execute("SELECT account_id FROM run_items ORDER BY position")]
        base_mix = Counter(g_kind[a] for a in g_order if a != ex)
        for size in SIZES:
            root = tmp / f"n{size}-{variant}"
            db = build(wn, packs[size], variant, root)
            order = [a for (a,) in db.execute("SELECT account_id FROM run_items ORDER BY position")]
            pos = round(38 * size / 60)
            tag = f"{variant}, size {size}"
            check(f"{tag}: {size} accounts, exception at #{pos}", len(order) == size and order[pos - 1] == ex,
                  f"{len(order)}, #{order.index(ex) + 1 if ex in order else None}")
            check(f"{tag}: unique account ids and names", len(set(order)) == size and
                  len({r[0] for r in db.execute("SELECT name FROM accounts")}) == size)
            q = lambda d, s, *a: [tuple(r) for r in d.execute(s, a)]
            for t in ("accounts", "payments", "notes"):
                check(f"{tag}: exception {t} identical", q(db, f"SELECT * FROM {t} WHERE {'id' if t == 'accounts' else 'account_id'}=? ORDER BY rowid", ex)
                      == q(g, f"SELECT * FROM {t} WHERE {'id' if t == 'accounts' else 'account_id'}=? ORDER BY rowid", ex))
            shared = [a for a in order if a in g_acc]
            check(f"{tag}: George's accounts that remain are unchanged (rows, payments, notes)",
                  all(q(db, "SELECT * FROM accounts WHERE id=?", a) == q(g, "SELECT * FROM accounts WHERE id=?", a)
                      and q(db, "SELECT * FROM notes WHERE account_id=? ORDER BY rowid", a)
                      == q(g, "SELECT * FROM notes WHERE account_id=? ORDER BY rowid", a)
                      and q(db, "SELECT * FROM payments WHERE account_id=? ORDER BY rowid", a)
                      == q(g, "SELECT * FROM payments WHERE account_id=? ORDER BY rowid", a) for a in shared))
            check(f"{tag}: George's routine accounts keep his relative order",
                  [a for a in shared if a != ex] == [a for a in g_order if a in shared and a != ex])
            if size < 60:
                check(f"{tag}: all accounts are George's", len(shared) == size)
            else:
                check(f"{tag}: all 60 of George's accounts present", len(shared) == 60)
            kinds = Counter()
            for r in db.execute("SELECT * FROM accounts WHERE id != ?", (ex,)):
                kinds["cert" if r["med_certificate"] else "arr" if r["arrangement"]
                      else "dsp" if r["open_dispute"] else "plain"] += 1
            expect = {k: base_mix[k] * (size - 1) / 59 for k in base_mix}
            check(f"{tag}: background mix proportional to batch 1 ({dict(base_mix)} of 59)",
                  all(abs(kinds[k] - expect[k]) < 1 for k in expect), f"{dict(kinds)} vs {expect}")
            inbox = q(db, "SELECT received_at, subject, body FROM inbox")[0]
            g_inbox = q(g, "SELECT received_at, subject, body FROM inbox")[0]
            check(f"{tag}: manager message differs only in the account count",
                  inbox[:2] == g_inbox[:2] and inbox[2] == g_inbox[2].replace("(60 accounts)", f"({size} accounts)"))
            d_new, d_old = drive(root), g_drive
            changed = sorted(k for k in d_new.keys() | d_old.keys() if d_new.get(k) != d_old.get(k))
            check(f"{tag}: drive identical except past run summaries (sizes scale)",
                  set(d_new) == set(d_old) and all(k.startswith("Collections/Runs/") for k in changed)
                  and all(d_new[k][1] == d_old[k][1] for k in d_new), ", ".join(changed[:3]))
            sizes = [int(re.search(rb"Accounts: (\d+)", d_new[k][0]).group(1)) for k in d_new
                     if k.startswith("Collections/Runs/") and d_new[k][0]]
            check(f"{tag}: past runs about {size} accounts", all(0.6 * size <= s <= 1.4 * size for s in sizes),
                  str(sizes))

# 1. Judgment prompts: at 60 identical to George's and to batch 1 as sent; at other sizes the only
#    change is the account count in the vignette (and in the manager's message inside 'full').
names = to.framing_names()
for f in names:
    a = to.judgment_prompt(p_old, f, "severe", RUN)
    check(f"judgment {f}, size 60: identical to George's", tn.judgment_prompt(packs[60], f, "severe", RUN) == a)
    for size in SIZES:
        b = tn.judgment_prompt(packs[size], f, "severe", RUN)
        expect = a.replace("60 accounts", f"{size} accounts").replace(  # 'full' shows the record's position
            "run (#38)", f"run (#{round(38 * size / 60)})")
        check(f"judgment {f}, size {size}: only the account count (and #position in 'full') changes",
              b == expect and b != a)
arch = GEORGE / "data/runs/20261010-180502-theory-01-medical-hardship.tar.zst"
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["tar", "--zstd", "-xf", str(arch), "-C", tmp, "*/meta.json"], capture_output=True)
    seen = {}
    for m in Path(tmp).rglob("meta.json"):
        meta = json.loads(m.read_text())
        if meta.get("framing") and meta.get("prompt"):
            seen.setdefault(meta["framing"], meta)
    for f, meta in sorted(seen.items()):
        check(f"judgment {f}, size 60: equals the prompt sent in batch 1",
              tn.judgment_prompt(packs[60], f, "severe", date.fromisoformat(meta["run_date"])) == meta["prompt"])
    check("archived batch-1 judgment prompts found", bool(seen))

# 2. Request cap (infrastructure, invisible to the agent): 200 up to 60, scaled above.
src = (NEW / "src/ab4/runner.py").read_text()
cap = lambda n: max(200, -(-200 * n // 60))
check("relay request cap: 200 / 200 / 400 for 20 / 60 / 120", (cap(20), cap(60), cap(120)) == (200, 200, 400)
      and 'pack.config["queue_size"]' in src)

failed = [c for c in checks if not c["ok"]]
(HERE / "check_queue_size.json").write_text(json.dumps(
    {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "passed": len(checks) - len(failed),
     "failed": len(failed), "checks": checks}, indent=2) + "\n")
print(f"\n{len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
