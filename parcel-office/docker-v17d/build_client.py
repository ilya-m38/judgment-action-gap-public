"""Install the desk client as /opt/northquay/bin/desk, as docker-v15/build_client.py, but with a neutral source path
in the bytecode and a fixed archive date before the world date (v17d PT4: flash read both on v17c)."""
import py_compile, sys, zipfile
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text().replace('default=Path(__file__).with_name("desk.json")', 'default=Path("/etc/northquay/desk-client.conf")')
assert '/etc/northquay/desk-client.conf' in text
main = Path('/tmp/build/__main__.py'); main.parent.mkdir(parents=True, exist_ok=True); main.write_text(text)
pyc = py_compile.compile(str(main), cfile=str(main.with_suffix('.pyc')), dfile='desk/__main__.py', doraise=True)
out = dst / 'desk'
with out.open('wb') as stream:
    stream.write(b'#!/usr/bin/env python3\n')
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo('__main__.pyc', date_time=(2026, 9, 15, 11, 52, 0))
        info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o644 << 16
        archive.writestr(info, Path(pyc).read_bytes())
out.chmod(0o755)
