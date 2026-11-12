"""Package the comms CLI as `reminders`, `records` and `mail`: executable zips of compiled bytecode only."""
import py_compile
import sys
import zipfile
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
pyc = py_compile.compile(str(src / "comms.py"), cfile=str(src / "__main__.pyc"), doraise=True)
for tool in ("reminders", "records", "mail"):
    out = dst / tool
    with out.open("wb") as stream:
        stream.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(pyc, "__main__.pyc")
    out.chmod(0o755)
