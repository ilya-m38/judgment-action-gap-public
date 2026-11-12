"""Long-limit runs on v17c (protocol deviation, main-batch-v17c/PROTOCOL.md): the same cell as run_action_v13.py, but
the run may last until 13:50 office time (16,500 s from 09:05), so an agent that holds the batch and waits for
permission reaches the 13:30 release deadline. Cells run in parallel (they mostly sleep), with a hard total cap:
a cell starts only if spend so far + the per-run relay limit of every cell in flight + its own limit stays within
the cap. Stops everything on the first OpenRouter 402. Usage:
  python3 run_long_v17c.py --model sonnet --action 10 --control 3 --replace-blocked 6 --workers 5 --cap-usd 40
The defaults are v17c's; --pack/--routine-pack/--image/--out run the same cell on another version (v17d: action-v17d-sa/PROTOCOL.md).
"""
import argparse, json, subprocess, tempfile, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from run_container import run
from run_action_v13 import MODELS, relay_cost, credits_exhausted
from generate import ROOT

LONG_TIMEOUT = 16500   # 09:05 + 16,500 s = 13:50 office time: 20 minutes past the 13:30 deadline for release and report
PER_RUN_USD = 4.0      # relay stop threshold per run (about 3x the expected cost of a run that polls until 13:30)
OUT = ROOT / 'long-v17c'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=MODELS, required=True)
    p.add_argument('--action', type=int, default=10)
    p.add_argument('--control', type=int, default=3)
    p.add_argument('--replace-blocked', type=int, default=0, help='extra action cells to replace provider-blocked ones (blocked before any decision)')
    p.add_argument('--workers', type=int, default=5)
    p.add_argument('--cap-usd', type=float, required=True)
    p.add_argument('--pack', default='pack-v17c.toml')
    p.add_argument('--routine-pack', default='pack-v17c-routine.toml')
    p.add_argument('--image', default='nq-depot-agent:0.3')
    p.add_argument('--out', type=Path, default=OUT)
    p.add_argument('--per-run-usd', type=float, default=PER_RUN_USD)
    a = p.parse_args()
    out_root = a.out if a.out.is_absolute() else ROOT / a.out
    catalog = {m['id']: m for m in json.loads((ROOT / 'openrouter-action-pilot/catalog.json').read_text())['data']}
    model, provider = MODELS[a.model]; m = catalog[model]
    r = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s', 'OpenRouter', '-a', 'openrouter', '-w'], capture_output=True)
    key = r.stdout.strip()
    if r.returncode or not key.startswith(b'sk-or-'):
        raise SystemExit('OpenRouter credential unavailable; no model request made')
    lock = threading.Lock(); state = {'in_flight': 0, 'stop': None, 'blocked': 0, 'extra_used': 0}

    def spent():
        return sum(relay_cost(x) for x in out_root.glob('**/relay/relay.jsonl'))

    def cell(arm, idx, key_file):
        pack = ROOT / (a.pack if arm == 'action' else a.routine_pack)
        out = out_root / ('runs' if arm == 'action' else 'control/runs') / a.model / f'{idx:02d}'
        if (out / 'result.json').exists():
            return
        with lock:
            if state['stop'] or spent() + (state['in_flight'] + 1) * a.per_run_usd > a.cap_usd:
                state['stop'] = state['stop'] or 'budget'
                return
            state['in_flight'] += 1
        try:
            cfg = SimpleNamespace(pack=pack, out=out, key_file=key_file, model_id=model, provider=provider,
                                  max_output=m['top_provider']['max_completion_tokens'], context_window=m['context_length'],
                                  max_requests=200, timeout=LONG_TIMEOUT, thinking='high', image=a.image,
                                  relay=ROOT / 'model_relay.py', preflight=False, spend_limit=a.per_run_usd)
            meta = run(cfg)
            if credits_exhausted(out / 'relay/relay.jsonl'):
                dest = out_root / 'aborted' / f'{arm}-{a.model}-{idx:02d}'; dest.parent.mkdir(parents=True, exist_ok=True); out.rename(dest)
                with lock: state['stop'] = 'credits'
                print(json.dumps({'event': 'credits_exhausted', 'arm': arm, 'idx': idx}), flush=True); return
            res = json.loads((out / 'result.json').read_text()) if (out / 'result.json').exists() else {}
            print(json.dumps({'arm': arm, 'idx': idx, 'error': meta.get('error'), 'timed_out': meta.get('timed_out'),
                              'outcome': res.get('outcome'), 'released': res.get('outbound_released'), 'destroyed': res.get('destroyed'),
                              'provider_blocked': res.get('provider_blocked')}), flush=True)
            if arm == 'action' and res.get('provider_blocked'):
                with lock: state['blocked'] += 1
        finally:
            with lock: state['in_flight'] -= 1

    with tempfile.TemporaryDirectory(prefix='nq-router-secret-', dir='/private/tmp') as d:
        kf = Path(d) / 'model-key'; kf.write_bytes(key); kf.chmod(0o600)
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(lambda i: cell('action', i, kf), range(1, a.action + 1)))
            # replacements for provider-blocked action cells (blocked in the first turns, before any decision)
            extra = min(state['blocked'], a.replace_blocked)
            list(pool.map(lambda i: cell('action', i, kf), range(a.action + 1, a.action + extra + 1)))
            list(pool.map(lambda i: cell('control', i, kf), range(1, a.control + 1)))
    print(json.dumps({'event': 'done', 'stop': state['stop'], 'spent_usd': round(spent(), 2), 'blocked': state['blocked']}), flush=True)
    if state['stop'] == 'credits':
        raise SystemExit(42)


if __name__ == '__main__':
    main()
