"""Same minimal-input probe as probe.py, but Grok 4.7 directly through the xAI API (no OpenRouter).

If "hi" again bills ~1240 prompt tokens, the hidden prefix comes from xAI itself; if ~90 or less, it is OpenRouter-route only.
Key: macOS Keychain item "xAI direct probe" (account xai); it goes to curl through stdin, never argv or files.
"""
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
# Same three inputs as probe.py (copied: importing probe.py would send its OpenRouter requests).
PARAGRAPH = ("The library opens at nine on weekdays and at ten on Saturdays. Books can be borrowed for three weeks and "
             "renewed twice, unless another reader has reserved them. Laptops are available at the front desk for use "
             "inside the building only. The reading room on the second floor is kept quiet, and group study rooms can be "
             "booked up to a week in advance. Printing costs ten cents per page, and scanning is free. Lost cards can be "
             "replaced at the desk for a small fee. During the summer the library runs a reading programme for children, "
             "with weekly prizes and a party at the end of August.")
SYSTEM = (ROOT / 'parcel-office/action-pilot-v14/runs/grok/01/state/action-system.txt').read_text()
INPUTS = {'hi': [{'role': 'user', 'content': 'hi'}],
          'paragraph': [{'role': 'user', 'content': PARAGRAPH}],
          'system': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': 'hi'}]}

key = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s', 'xAI direct probe', '-a', 'xai', '-w'],
                     capture_output=True).stdout.strip().decode()
if not key.startswith('xai-'):
    raise SystemExit('xAI credential unavailable; no request made')

rows = []
for name, messages in INPUTS.items():
    body = {'model': 'grok-4.7', 'messages': messages, 'max_tokens': 400, 'reasoning_effort': 'low'}
    cfg = f'header = "Authorization: Bearer {key}"\nheader = "Content-Type: application/json"\n'
    r = subprocess.run(['/usr/bin/curl', '-sS', '--max-time', '120', '-K', '-', '--data-binary', json.dumps(body),
                        'https://api.x.ai/v1/chat/completions'], input=cfg.encode(), capture_output=True, check=True)
    resp = json.loads(r.stdout)
    if 'error' in resp or 'usage' not in resp:
        raise SystemExit(f'{name}: {resp}')
    u = resp['usage']
    row = {'model': 'grok-4.7 (api.x.ai)', 'input': name, 'resolved_model': resp.get('model'),
           'request_chars': sum(len(m['content']) for m in messages), 'prompt_tokens': u.get('prompt_tokens'),
           'cached_tokens': (u.get('prompt_tokens_details') or {}).get('cached_tokens'),
           'completion_tokens': u.get('completion_tokens'), 'cost_usd_ticks': u.get('cost_in_usd_ticks'),
           'reply': ((resp.get('choices') or [{}])[0].get('message') or {}).get('content')}
    rows.append(row)
    print(json.dumps({k: v for k, v in row.items() if k != 'reply'}))

(HERE / 'results-direct.json').write_text(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'rows': rows}, indent=2, ensure_ascii=False))
