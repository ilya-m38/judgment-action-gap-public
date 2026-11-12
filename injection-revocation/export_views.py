"""Everything the agent can see through `pa` and the shared drive, in one file, for reading the world with the agent's
eyes (WORLD-AND-LEAK-CHECKLIST.md part 2, step 3).

  python3 export_views.py OUT_DIR [--variant away|routine]
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import generate

ROOT = Path(__file__).resolve().parent
PY = str(ROOT.parent / "clinic-mail" / ".venv" / "bin" / "python")  # has aiosmtpd, as the office image


def main(out: Path, variant: str = "away"):
    tmp = Path(tempfile.mkdtemp(prefix="irviews-"))
    generate.build(ROOT / "pack.toml", tmp / "state", tmp / "drive", "http://127.0.0.1:8792", variant)
    svc = subprocess.Popen([PY, str(ROOT / "service.py"), "--data", str(tmp / "state"), "--port", "8792"],
                           env={"PA_SMTP_PORT": "2526", "PATH": "/usr/bin:/bin"})
    time.sleep(1)
    env = {"PA_CONFIG": str(tmp / "state" / "pa.json"), "PATH": "/usr/bin:/bin"}
    pa = lambda *a: subprocess.run([sys.executable, str(ROOT / "client.py"), *a], capture_output=True, text=True,
                                   env=env).stdout
    parts = ["# System prompt\n" + (tmp / "state" / "action-system.txt").read_text(),
             "# Trigger\n" + (tmp / "state" / "action-trigger.txt").read_text()]
    for args in (["--help"], ["status"], ["register"], ["revocations"], ["history"], ["notices"], ["inbox"],
                 ["inbox", "--folder", "sent"]):
        parts.append(f"# pa {' '.join(args)}\n" + pa(*args))
    ids = [line.split()[1] for line in pa("register").splitlines() if " QLO-" in line]
    parts.append("# pa show (all overrides)\n" + pa("show", *ids))
    import sqlite3
    db = sqlite3.connect(tmp / "state" / "pa.sqlite")
    mids = [r[0] for r in db.execute("SELECT id FROM mailbox ORDER BY id")]
    db.close()
    for mid in mids:
        parts.append(f"# pa read {mid}\n" + pa("read", str(mid)))
    for p in sorted((tmp / "drive").rglob("*.md")):
        parts.append(f"# Shared Drive/{p.relative_to(tmp / 'drive')}\n" + p.read_text())
    svc.terminate()
    out.mkdir(parents=True, exist_ok=True)
    (out / "OFFICE-VIEWS.txt").write_text("\n\n".join(parts))
    (out / "manifest.json").write_text((tmp / "state" / "manifest.json").read_text())
    print(f"wrote {out / 'OFFICE-VIEWS.txt'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--variant" else "away")
