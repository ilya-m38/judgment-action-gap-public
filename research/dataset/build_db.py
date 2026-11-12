"""Build the shareable SQLite file from the per-dilemma JSONL exports (see SCHEMA.md).

python3 -I research/dataset/build_db.py  ->  research/dataset/build/judgment_action_gap.sqlite
"""
import json, sqlite3, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
EXPORT, BUILD = ROOT / "export", ROOT / "build"
DILEMMAS = ["power-company", "parcel-office", "clinic-mail", "dog-warden",
            "injection-revocation", "eviction", "timesheet"]
QUESTIONS = ["normative", "self", "typical_ai", "typical_employee"]

DDL = """
CREATE TABLE dilemmas (
  dilemma_id TEXT PRIMARY KEY, name TEXT, summary TEXT, protect_definition TEXT,
  theory_version TEXT, action_version TEXT, theory_system_prompt TEXT,
  action_system_prompt TEXT, action_task_prompt TEXT, action_environment TEXT,
  routine_control TEXT, notes TEXT);
CREATE TABLE theory_prompts (
  dilemma_id TEXT, question TEXT, prompt TEXT, PRIMARY KEY (dilemma_id, question));
CREATE TABLE models (model TEXT PRIMARY KEY, model_id TEXT, family TEXT);
CREATE TABLE judgments (
  id INTEGER PRIMARY KEY, dilemma_id TEXT, model TEXT, question TEXT, rep INTEGER,
  response TEXT, reasoning TEXT, label TEXT, label_source TEXT, counted INTEGER,
  source_path TEXT);
CREATE TABLE action_runs (
  id INTEGER PRIMARY KEY, dilemma_id TEXT, model TEXT, condition TEXT, rep INTEGER,
  outcome TEXT, protects INTEGER, counted INTEGER, excluded_reason TEXT,
  n_turns INTEGER, run_path TEXT UNIQUE);
CREATE TABLE action_turns (
  run_id INTEGER, turn INTEGER, role TEXT, content TEXT, reasoning TEXT,
  tool_calls TEXT, tool_name TEXT, PRIMARY KEY (run_id, turn));
CREATE TABLE test_talk (
  id INTEGER PRIMARY KEY, dilemma_id TEXT, model TEXT, kind TEXT, run_path TEXT,
  question TEXT, rep INTEGER, code TEXT, about_clock INTEGER, quote TEXT, method TEXT);
CREATE INDEX j_dm ON judgments(dilemma_id, model, question);
CREATE INDEX a_dm ON action_runs(dilemma_id, model, condition);
CREATE INDEX t_dm ON test_talk(dilemma_id, model, kind);

-- The gap as in the matrix: normative judgment protect % minus action protect % (case runs).
CREATE VIEW gap_summary AS
WITH t AS (
  SELECT dilemma_id, model, SUM(label='protect') AS theory_protect, COUNT(*) AS theory_n
  FROM judgments WHERE question='normative' AND counted=1 GROUP BY dilemma_id, model),
a AS (
  SELECT dilemma_id, model, SUM(protects) AS action_protect, COUNT(*) AS action_n
  FROM action_runs WHERE condition='case' AND counted=1 GROUP BY dilemma_id, model),
-- test talk counts every coded case run, including runs left out of the gap (as the matrix does)
tt AS (
  SELECT r.dilemma_id, r.model, SUM(x.code IN ('S','W')) AS test_talk_runs, COUNT(x.code) AS test_talk_coded
  FROM action_runs r JOIN test_talk x ON x.kind='action' AND x.run_path=r.run_path
  WHERE r.condition='case' GROUP BY r.dilemma_id, r.model)
SELECT t.dilemma_id, t.model, t.theory_protect, t.theory_n, a.action_protect, a.action_n,
  ROUND(100.0*t.theory_protect/t.theory_n - 100.0*a.action_protect/a.action_n) AS gap_pp,
  tt.test_talk_runs, tt.test_talk_coded
FROM t JOIN a USING (dilemma_id, model) LEFT JOIN tt USING (dilemma_id, model);
"""

FAMILIES = {"luna": "OpenAI", "astra": "OpenAI", "sol": "OpenAI", "terra": "OpenAI",
            "haiku": "Anthropic", "sonnet": "Anthropic", "flash": "Google", "gemini-pro": "Google",
            "grok": "xAI", "mistral": "Mistral", "nemotron": "NVIDIA", "kimi": "Moonshot",
            "glm": "Zhipu", "qwen-27b": "Alibaba", "qwen-max": "Alibaba", "minimax": "MiniMax"}


def rows(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    BUILD.mkdir(exist_ok=True)
    out = BUILD / "judgment_action_gap.sqlite"
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript(DDL)
    model_ids = {}
    missing = []
    for d in DILEMMAS:
        folder = EXPORT / d
        if not (folder / "dilemma.json").exists():
            missing.append(d)
            continue
        m = json.loads((folder / "dilemma.json").read_text(encoding="utf-8"))
        db.execute("INSERT INTO dilemmas VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            d, m.get("name"), m.get("summary"), m.get("protect_definition"),
            m.get("theory_version"), m.get("action_version"), m.get("theory_system_prompt"),
            m.get("action_system_prompt"), m.get("action_task_prompt"),
            m.get("action_environment"), m.get("routine_control"), m.get("notes")))
        for q in QUESTIONS:
            db.execute("INSERT INTO theory_prompts VALUES (?,?,?)",
                       (d, q, (m.get("theory_prompts") or {}).get(q)))
        for r in rows(folder / "judgments.jsonl"):
            model_ids.setdefault(r["model"], r.get("model_id"))
            db.execute("INSERT INTO judgments (dilemma_id, model, question, rep, response, reasoning,"
                       " label, label_source, counted, source_path) VALUES (?,?,?,?,?,?,?,?,?,?)", (
                d, r["model"], r["question"], r.get("rep"), r.get("response"), r.get("reasoning"),
                r.get("label"), r.get("label_source"), int(bool(r.get("counted"))), r.get("source_path")))
        for r in rows(folder / "action_runs.jsonl"):
            model_ids.setdefault(r["model"], r.get("model_id"))
            turns = r.get("transcript") or []
            cur = db.execute("INSERT INTO action_runs (dilemma_id, model, condition, rep, outcome,"
                             " protects, counted, excluded_reason, n_turns, run_path)"
                             " VALUES (?,?,?,?,?,?,?,?,?,?)", (
                d, r["model"], r.get("condition"), r.get("rep"), r.get("outcome"),
                int(bool(r.get("protects"))), int(bool(r.get("counted"))), r.get("excluded_reason"),
                len(turns), r.get("run_path")))
            for i, t in enumerate(turns):
                calls = t.get("tool_calls")
                db.execute("INSERT INTO action_turns VALUES (?,?,?,?,?,?,?)", (
                    cur.lastrowid, i, t.get("role"), t.get("content"), t.get("reasoning"),
                    json.dumps(calls, ensure_ascii=False) if calls else None, t.get("tool_name")))
    tt = EXPORT / "test_talk.jsonl"
    if tt.exists():
        for r in rows(tt):
            db.execute("INSERT INTO test_talk (dilemma_id, model, kind, run_path, question, rep, code,"
                       " about_clock, quote, method) VALUES (?,?,?,?,?,?,?,?,?,?)", (
                r["dilemma_id"], r["model"], r["kind"], r.get("run_path"), r.get("question"),
                r.get("rep"), r.get("code"), int(bool(r.get("about_clock"))), r.get("quote"),
                r.get("method")))
    else:
        missing.append("test_talk.jsonl")
    for model, fam in FAMILIES.items():
        db.execute("INSERT INTO models VALUES (?,?,?)", (model, model_ids.get(model), fam))
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB)")
    if missing:
        print("missing exports:", ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
