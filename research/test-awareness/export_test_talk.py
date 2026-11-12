# Export blind test-talk codes to research/dataset/export/test_talk.jsonl (SCHEMA.md, test_talk.jsonl)
import json, glob, os, re, collections, sys
R = "/Users/user/Projects/Move38/Measuring the Judgment-Action Gap in Large Language Models"
S = os.environ.get("TT_SCRATCH", os.path.dirname(os.path.abspath(__file__)))  # recode pool and batch-1 unpack
os.chdir(R)
rows = []
MODEL_ALIAS = {"mistral-large": "mistral", "minimax-flash": "minimax"}
CASE_DIRS = ("severe", "action", "away", "guide3", "runs")


def rel(p):
    p = p.rstrip("/")
    if p.startswith(R + "/"):
        return p[len(R) + 1:]
    m = re.search(r"/b1/(\d{8}-\d{6}-agent-01-medical-hardship)/(.*)$", p)
    if m:  # George's batch 1, read from the archive
        return f"auth-bench-4/data/runs/{m.group(1)}/{m.group(2)}"
    return p


def model_of(path):
    parts = path.rstrip("/").split("/")
    return MODEL_ALIAS.get(parts[-2], parts[-2])


def arm_of(path):
    return "routine" if re.search(r"/(routine|control)/", path) else "case"


def add(dil, path, code, clock=False, quote="", method="blind", batch=""):
    path = rel(path)
    m = model_of(path)
    if m in ("cohere", "command-a-plus"):
        return
    rows.append(dict(dilemma_id=dil, model=m, kind="action", arm=arm_of(path), run_path=path, code=code,
                     about_clock=bool(clock), quote=quote or "", method=method, batch=batch))


def norm(v):
    """codes.json entry -> S/W/T/N."""
    if not v:
        return "N"
    if v.get("code") in ("S", "W", "T", "N"):
        return v["code"]
    if v.get("code") in ("strong", "weak", "none"):
        return {"strong": "S", "weak": "W", "none": "N"}[v["code"]]
    tt = v.get("test_talk")
    if tt in (True, "yes", "strong", "weak"):
        st = v.get("strength") or (tt if tt in ("strong", "weak") else None)
        return "S" if st == "strong" else "W"
    if v.get("trap"):
        return "T"
    return "N"


def clock_of(v):
    trig = str(v.get("trigger", "")) + str(v.get("time_triggered", ""))
    return "TIME" in trig.upper() or v.get("time_triggered") is True


def from_pool(dil, pool, base="", batch=None):
    key = json.load(open(pool + "-KEY.json"))
    codes = json.load(open(pool + "/codes.json"))
    for c, p in key.items():
        p = p if p.startswith("/") else os.path.join(R, base, p)
        v = codes.get(c) or {}
        add(dil, p, norm(v), clock_of(v), v.get("quote", ""), batch=batch or os.path.basename(pool))


# 1. re-coded pool (14 pools whose per-run codes were not saved on 02.11, plus George's batch 1)
rc_key = json.load(open(f"{S}/rc-KEY.json"))
rc = {}
for f in glob.glob(f"{S}/rc/codes*.tsv"):
    for l in open(f):
        p = l.rstrip("\n").split("\t")
        if p and p[0]:
            rc[p[0].replace(".txt", "")] = p
DIL = [("research/power-company", "power-company"), ("/b1/", "power-company"), ("clinic-mail", "clinic-mail"),
       ("dog-warden", "dog-warden"), ("injection-revocation", "injection-revocation")]
for c, p in rc_key.items():
    dil = next(d for k, d in DIL if k in p)
    v = rc.get(c, [c, "N", "-", "-", ""])
    v += [""] * (5 - len(v))
    george = "/b1/" in p
    add(dil, p, v[1], v[2] == "yes", v[4], method="blind (re-coded 10.11)" if not george else
        "blind (re-coded 10.11; matrix uses George's labels)", batch="recode-20261110")

# 2. saved blind pools
for pool, dil, base in [
        ("parcel-office/action-blind/v17d-ta", "parcel-office", "parcel-office"),
        ("parcel-office/action-blind/v17d-main", "parcel-office", "parcel-office"),
        ("parcel-office/action-blind/v17d-gq", "parcel-office", "parcel-office"),
        ("parcel-office/action-blind/v17d-05", "parcel-office", "parcel-office"),
        ("parcel-office/action-blind/v17d-cn", "parcel-office", "parcel-office"),
        ("clinic-mail/runs/blind-v23-ta", "clinic-mail", ""),
        ("clinic-mail/runs/blind-v23main-ta", "clinic-mail", ""),
        ("dog-warden/runs/blind-v14closed-ta", "dog-warden", ""),
        ("dog-warden/runs/blind-v14to10-ta", "dog-warden", ""),
        ("dog-warden/runs/blind-v14hq-ta", "dog-warden", ""),
        ("injection-revocation/runs/blind-v2away-ta", "injection-revocation", ""),
        ("research/dilemmas/eviction-freeze/runs/blind-test-talk-20261103", "eviction", ""),
        ("research/dilemmas/eviction-freeze/runs/blind-test-talk-sa-20261106", "eviction", "")]:
    from_pool(dil, pool, base)

# eviction sa: KEY maps code -> run path?  (handled by from_pool)

# 3. test-awareness folders (sonnet, astra, honesty)
TA = "research/test-awareness"
for c, v in json.load(open(f"{TA}/power-b1-blind/codes.json")).items():
    add("power-company", f"{S}/b1/{v['run']}", norm(v), v.get("time_triggered"), batch="power-b1-blind")
for c, v in json.load(open(f"{TA}/power-b1-blind/codes-astra-q60.json")).items():
    add("power-company", os.path.join(R, "research/power-company/queue-size/runs", v["run"]), norm(v), batch="power-b1-blind")
for c, v in json.load(open(f"{TA}/parcel-clinic-sa-blind/codes.json")).items():
    dil = "parcel-office" if v["run"].startswith("parcel-office") else "clinic-mail"
    q = {"weak": "W"}.get(v["code"])
    add(dil, os.path.join(R, v["run"]), norm(v), v["code"] == "weak", batch="parcel-clinic-sa-blind")
for c, v in json.load(open(f"{TA}/dogwarden-sa-blind/codes.json")).items():
    add("dog-warden", os.path.join(R, "dog-warden/runs", v["run"]), norm(v), v.get("time_triggered"), batch="dogwarden-sa-blind")
for c, v in json.load(open(f"{TA}/injection-sa-blind/codes.json")).items():
    add("injection-revocation", os.path.join(R, v["run"]), norm(v), batch="injection-sa-blind")
for fn in ("codes.json", "codes-new3.json"):
    for c, v in json.load(open(f"{TA}/honesty-d5-blind/{fn}")).items():
        add("timesheet", os.path.join(R, "research/dilemmas/honesty-reverse/stand/runs", v["run"]), norm(v),
            False, v.get("quote", ""), batch="honesty-d5-blind")

# 4. theory: one row per answer (code = highest over reasoning and answer; N when no excerpt matched)
def theory(dil, root, keyf, codesf, batch):
    key = json.load(open(keyf))
    if codesf.endswith(".tsv"):
        cs = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(codesf)}
        code = {c: (cs[c][1], cs[c][2] if len(cs[c]) > 2 else "") for c in cs}
    else:
        cs = json.load(open(codesf))
        code = {c: (v["code"], v.get("quote", "")) for c, v in cs.items()}
    rank = {"N": 0, "G": 0, "W": 1, "S": 2}
    best = {}
    for c, k in key.items():
        cd, q = code.get(c, ("N", ""))
        cur = best.get(k["src"], ("N", ""))
        if rank[cd] > rank[cur[0]]:
            best[k["src"]] = ("N" if cd == "G" else cd, q)
    for f in sorted(glob.glob(root + "/*/*/[01][0-9]/result.json")):
        fr, m, rep = f.split("/")[-4:-1]
        cd, q = best.get(f, ("N", ""))
        rows.append(dict(dilemma_id=dil, model=MODEL_ALIAS.get(m, m), kind="theory", question=fr, rep=int(rep),
                         answer_path=f, code=cd, about_clock=False, quote=q, method="blind", batch=batch))


theory("clinic-mail", "clinic-mail/runs/judgment-v23-retold/v23r", f"{TA}/theory-retold-blind/KEY.json",
       f"{TA}/theory-retold-blind/codes.tsv", "theory-v23-retold")
theory("parcel-office", "parcel-office/judgment-retold-v17d", f"{TA}/theory-retold-blind/KEY.json",
       f"{TA}/theory-retold-blind/codes.tsv", "theory-v17d-retold")
theory("timesheet", "research/dilemmas/honesty-reverse/runs/theory/v1d5", f"{TA}/honesty-d5-blind/theory-KEY.json",
       f"{TA}/honesty-d5-blind/theory-codes.json", "theory-v1d5")

# theory-retold codes: 0080 and 0458 were moved to N in RESULTS.md (already in codes.tsv)
# keep only rows that join the branch exports; theory: drop empty answers and the dropped sonnet/astra v17d-retold v1
dropped = collections.Counter()
keep = []
br = {d: {json.loads(l)["run_path"] for l in open(f"research/dataset/export/{d}/action_runs.jsonl")}
      for d in {r["dilemma_id"] for r in rows}}
for r in rows:
    if r["kind"] == "action" and r["run_path"] not in br[r["dilemma_id"]]:
        dropped[(r["dilemma_id"], "action not in branch export")] += 1; continue
    if r["kind"] == "theory":
        d = json.load(open(r["answer_path"]))
        if not (d.get("final_text") or "").strip():
            dropped[(r["dilemma_id"], "theory: empty answer")] += 1; continue
        if r["dilemma_id"] == "parcel-office" and r["model"] in ("sonnet", "astra"):
            dropped[(r["dilemma_id"], "theory: sonnet/astra v1, dropped by the branch")] += 1; continue
    keep.append(r)
rows = keep
print(dict(dropped))
os.makedirs("research/dataset/export", exist_ok=True)
with open("research/dataset/export/test_talk.jsonl", "w") as o:
    for r in rows:
        o.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows))
c = collections.Counter((r["dilemma_id"], r["kind"]) for r in rows)
for k, v in sorted(c.items()):
    print(k, v)
