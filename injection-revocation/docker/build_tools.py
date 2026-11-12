"""Install the register client as `pa`: the Python source, as an internal tool is usually shipped (pilot v2: flash
took a bytecode-only zip apart)."""
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
out = dst / "pa"
out.write_text((src / "client.py").read_text())
out.chmod(0o755)
