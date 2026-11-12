"""Re-score finished action runs from their saved state (no model calls), e.g. after an outcome.py change.

  python3 rescore.py runs/action-pilot-20261102 [more batch dirs]
"""
import json
import sys
from pathlib import Path

import outcome

for batch in sys.argv[1:]:
    for res in sorted(Path(batch).glob("*/*/*/result.json")):
        old = json.loads(res.read_text())
        if not (res.parent / "state" / "income.sqlite").exists():
            continue
        new = outcome.score(res.parent / "state")
        new.update(trace=old.get("trace"), run_error=old.get("run_error"),
                   classification=outcome.classify(new, old.get("trace")))
        if (old.get("primary"), old.get("classification")) != (new["primary"], new["classification"]):
            print(res.parent.relative_to(batch), old.get("classification"), "->", new["classification"])
        res.write_text(json.dumps(new, indent=2, ensure_ascii=False))
