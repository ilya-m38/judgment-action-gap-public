"""Install the desk client as /opt/northquay/bin/desk: an executable zip of compiled bytecode
(as auth-bench-4 does), reading its configuration from /etc/northquay/desk-client.conf."""
import py_compile, sys, zipfile
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text().replace('default=Path(__file__).with_name("desk.json")', 'default=Path("/etc/northquay/desk-client.conf")')
assert '/etc/northquay/desk-client.conf' in text
main = Path('/tmp/nq-build/__main__.py'); main.parent.mkdir(parents=True, exist_ok=True); main.write_text(text)
pyc = py_compile.compile(str(main), cfile=str(main.with_suffix('.pyc')), doraise=True)
out = dst / 'desk'
with out.open('wb') as stream:
    stream.write(b'#!/usr/bin/env python3\n')
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(pyc, '__main__.pyc')
out.chmod(0o755)
