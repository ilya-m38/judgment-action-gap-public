"""Does the provider add hidden input to Grok requests? Measure billed prompt tokens on minimal requests.

Same three inputs for Grok and two control models, same routing as the action pilots (one provider, no fallbacks):
  hi        - user "hi", no system prompt, no tools
  paragraph - user: a fixed neutral English paragraph, no system prompt (tokenizer slope)
  system    - user "hi" with the parcel-office action system prompt (v14)
A constant surplus on "hi" that the paragraph does not explain = hidden input. Nothing asks the model about its prompt.
"""
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
MODELS = {'grok': ('x-ai/grok-4.7', 'xai'), 'qwen-max': ('qwen/qwen3.8-max-0902', 'alibaba'),
          'flash': ('google/gemini-3.8-flash', 'google-ai-studio')}
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

key = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s', 'OpenRouter', '-a', 'openrouter', '-w'],
                     capture_output=True).stdout.strip().decode()
if not key.startswith('sk-or-'):
    raise SystemExit('OpenRouter credential unavailable; no request made')

rows = []
for label, (model, provider) in MODELS.items():
    for name, messages in INPUTS.items():
        body = {'model': model, 'messages': messages, 'max_tokens': 400, 'reasoning': {'effort': 'low'}, 'usage': {'include': True},
                'provider': {'only': [provider], 'allow_fallbacks': False}}
        # System curl (system trust store); the key goes through stdin, never argv.
        cfg = f'header = "Authorization: Bearer {key}"\nheader = "Content-Type: application/json"\n'
        r = subprocess.run(['/usr/bin/curl', '-sS', '--max-time', '120', '-K', '-', '--data-binary', json.dumps(body),
                            'https://openrouter.ai/api/v1/chat/completions'], input=cfg.encode(), capture_output=True, check=True)
        resp = json.loads(r.stdout)
        if 'error' in resp:
            raise SystemExit(f'{label}/{name}: {resp["error"]}')
        u = resp.get('usage') or {}
        row = {'model': label, 'input': name, 'provider': resp.get('provider'), 'resolved_model': resp.get('model'),
               'request_chars': sum(len(m['content']) for m in messages), 'prompt_tokens': u.get('prompt_tokens'),
               'cached_tokens': (u.get('prompt_tokens_details') or {}).get('cached_tokens'),
               'completion_tokens': u.get('completion_tokens'), 'cost_usd': u.get('cost'),
               'reply': ((resp.get('choices') or [{}])[0].get('message') or {}).get('content')}
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != 'reply'}))

(HERE / 'results.json').write_text(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'rows': rows}, indent=2, ensure_ascii=False))
print('total cost', round(sum(r['cost_usd'] or 0 for r in rows), 6))
