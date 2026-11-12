"""Judgment arm for the parcel pack: plain API calls, no tools, one fresh conversation per answer.

Follows auth-bench-4's theory.py: same plain system prompt, high reasoning, each model pinned to its
first-party provider with fallbacks disabled. Answers are labelled afterwards by label_judgment.py.
"""
import argparse, json, ssl, subprocess, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = 'https://openrouter.ai/api/v1/chat/completions'
THINKING = 'high'
# id, provider, max_output: as in auth-bench-4 src/ab4/config.py
MODELS = {
    'kimi': ('moonshotai/kimi-k3', 'moonshotai', 943718),
    'flash': ('google/gemini-3.8-flash', 'google-ai-studio', 65536),
    'grok': ('x-ai/grok-4.7', 'xai', 450000),
    'gemini-pro': ('google/gemini-3.1-pro-preview-customtools', 'google-ai-studio', 65536),
    'luna': ('openai/gpt-6-luna', 'openai', 128000),
    'glm': ('z-ai/glm-5.3', 'z-ai', 131072),
    'haiku': ('anthropic/claude-haiku-5.5', 'anthropic', 128000),
    'sonnet': ('anthropic/claude-sonnet-5.5', 'anthropic', 128000),
    'astra': ('openai/gpt-6-astra', 'openai', 128000),
    'qwen-27b': ('qwen/qwen3.8-27b', 'alibaba', 131072),
}
try:  # python.org builds ship without system CAs
    import certifi
    SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
FRAMINGS = ('normative', 'self', 'typical_ai', 'typical_employee', 'full')


def load_key():
    r = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s', 'OpenRouter',
                        '-a', 'openrouter', '-w'], capture_output=True)
    key = r.stdout.strip().decode()
    if r.returncode or not key.startswith('sk-or-'):
        raise SystemExit('OpenRouter credential unavailable; no model request made')
    return key


def complete(key, model, system, user, retries=5):
    model_id, provider, max_output = MODELS[model]
    body = {'model': model_id, 'max_tokens': max_output, 'reasoning_effort': THINKING,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'provider': {'only': [provider], 'allow_fallbacks': False}, 'usage': {'include': True}}
    request = urllib.request.Request(URL, data=json.dumps(body).encode(), method='POST',
                                     headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=600, context=SSL) as response:
                return body, json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:2000].decode('utf-8', 'replace')
            if (exc.code < 500 and exc.code != 429) or attempt == retries - 1:
                raise RuntimeError(f'HTTP {exc.code}: {detail}') from exc
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
        time.sleep(min(60, 5 * 2 ** attempt))


def run_cell(key, state, out, framing, model, rep):
    cell = out / framing / model / f'{rep:02d}'
    if (cell / 'result.json').exists():
        previous = json.loads((cell / 'result.json').read_text())
        if previous.get('completed') or previous.get('final_text'):
            return previous
    cell.mkdir(parents=True, exist_ok=True)
    system = (state / 'judgment-system.txt').read_text()
    prompt = (state / f'judgment-{framing}.txt').read_text()
    result = {'framing': framing, 'model': model, 'rep': rep, 'model_id': MODELS[model][0],
              'started_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    try:
        request, response = complete(key, model, system, prompt)
        (cell / 'response.json').write_text(json.dumps(response, indent=2, ensure_ascii=False))
        choice = response['choices'][0]; message = choice['message']; usage = response.get('usage') or {}
        result.update(completed=choice.get('finish_reason') == 'stop', finish_reason=choice.get('finish_reason'),
                      final_text=(message.get('content') or '').strip(), reasoning=message.get('reasoning') or '',
                      provider=response.get('provider'), resolved_model=response.get('model'),
                      cost_usd=usage.get('cost'), tokens={k: usage.get(k) for k in ('prompt_tokens', 'completion_tokens')})
    except Exception as exc:  # noqa: BLE001 - recorded, never silently retried as a different cell
        result.update(completed=False, error=f'{type(exc).__name__}: {exc}'[:2000])
    (cell / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--state', type=Path, default=ROOT / 'generated/v13/state')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--models', nargs='+', choices=MODELS, required=True)
    p.add_argument('--framings', nargs='+', choices=FRAMINGS, default=['normative'])
    p.add_argument('--reps', type=int, default=10)
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--budget-usd', type=float, default=8.0, help='stop submitting new cells past this reported spend')
    a = p.parse_args()
    key = load_key()
    a.out.mkdir(parents=True, exist_ok=True)
    # Interleave models so one slow model does not hold up the rest; completed cells are kept and skipped.
    cells = [(f, m, r) for f in a.framings for r in range(1, a.reps + 1) for m in a.models]
    spent = 0.0
    with ThreadPoolExecutor(a.workers) as pool:
        for start in range(0, len(cells), a.workers):  # chunks, so the budget is checked between them
            if spent > a.budget_usd:
                print(json.dumps({'event': 'budget_stop', 'spent_usd': round(spent, 4)})); break
            chunk = cells[start:start + a.workers]
            for res in pool.map(lambda c: run_cell(key, a.state, a.out, *c), chunk):
                spent += res.get('cost_usd') or 0
                print(json.dumps({k: res.get(k) for k in ('framing', 'model', 'rep', 'completed', 'cost_usd', 'error')}), flush=True)
    print(json.dumps({'event': 'done', 'cells': len(cells), 'spent_usd': round(spent, 4)}))


if __name__ == '__main__':
    main()
