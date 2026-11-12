"""Export one generated world as text for review (no model calls).  python3 -I export_views.py OUT_DIR severe|routine"""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, '.')
import generate
from service import Office
base = Path(sys.argv[1]); variant = sys.argv[2]
if base.exists(): shutil.rmtree(base)
generate.build(Path('pack.toml'), base/'state', base/'Shared Drive', variant=variant)
o = Office(base/'state')
ids = [r[0] for r in o.db.execute("SELECT id FROM dogs WHERE id IN (SELECT dog_id FROM contacts) OR status='day8' ORDER BY position")]
def line(cmd, args):
    bits = []
    for k, v in args.items():
        bits.append(' '.join(v) if isinstance(v, list) else (f'--{k}' if v is True else f'--{k} {v}'))
    return f"$ kennel {cmd} {' '.join(bits)}".rstrip()
parts = []
for cmd, args in [('status', {}), ('register', {}), ('register', {'day8': True}), ('dog', {'ids': ids}), ('transfers', {}),
                  ('inbox', {}), ('inbox', {'folder': 'sent'}), ('history', {})]:
    ok, out = o.call(cmd, args); parts.append(line(cmd, args) + "\n" + out + "\n")
for (mid,) in o.db.execute("SELECT id FROM mailbox ORDER BY id").fetchall():
    ok, out = o.call('read', {'id': mid}); parts.append(f"$ kennel read {mid}\n{out}\n")
(base/'OFFICE-VIEWS.txt').write_text("\n".join(parts))
o.db.close()
for f in (base/'state').glob('kennel.sqlite*'): f.unlink()
(base/'state'/'clock.json').unlink()
