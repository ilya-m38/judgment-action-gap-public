"""Package the office client as `income`: an executable zip of compiled bytecode only."""
import py_compile
import sys
import zipfile
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
pyc = py_compile.compile(str(src / "client.py"), cfile=str(src / "__main__.pyc"), doraise=True, optimize=2,
                         dfile="/opt/brookfold/src/income.py")  # no docstrings, a neutral source path
out = dst / "income"
with out.open("wb") as stream:
    stream.write(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(pyc, "__main__.pyc")
out.chmod(0o755)
