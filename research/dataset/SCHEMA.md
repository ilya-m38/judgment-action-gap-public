# Dataset export: common schema

Goal: one SQLite file (plus README) that people can hand to their own Claude/GPT to ask questions about the study. HQ assembles it from per-dilemma JSONL exports.

**Scope.** Only the versions behind the HQ matrix (RECOGNITION-GAP-MATRIX.html): the theory text and the action version each card note names, 16 models, all four judgment questions. No pilots, no superseded drafts.

**No new model calls.** Export only from data already on disk.

**Where.** `research/dataset/export/<dilemma_id>/` (git-ignored, the files can be large). One folder per dilemma, files below, UTF-8 JSONL (one JSON object per line).

`dilemma_id`: `power-company`, `parcel-office`, `clinic-mail`, `dog-warden`, `injection-revocation`, `eviction`, `timesheet`.

`model`: the matrix short name: luna, astra, sol, terra, haiku, sonnet, flash, gemini-pro, grok, mistral, nemotron, kimi, glm, qwen-27b, qwen-max, minimax. Put the provider id (e.g. `moonshotai/kimi-k2`) in `model_id`.

## dilemma.json (one object)
- `dilemma_id`, `name` (as in the matrix), `summary` (2–4 sentences, plain English)
- `protect_definition`: what counts as protecting the person, in theory and in action
- `theory_version`, `action_version`: the labels the card notes use (e.g. "retold v2", "v17d")
- `theory_system_prompt`
- `theory_prompts`: object with keys `normative`, `self`, `typical_ai`, `typical_employee`; each is the full user prompt exactly as sent
- `action_system_prompt`, `action_task_prompt` (the trigger/first user message), `action_environment`: short description of the sandbox, tools and what the agent can do
- `routine_control`: one or two sentences on the control condition, if any
- `notes`: anything a reader must know (e.g. sonnet "other" answers in timesheet)

## judgments.jsonl (one line per answer)
- `dilemma_id`, `model`, `model_id`, `question` (normative|self|typical_ai|typical_employee), `rep` (1..10)
- `response` (final answer text), `reasoning` (visible reasoning text or null)
- `label`: protect | procedural | other | invalid; `label_source` (e.g. "haiku labeler", "blind HQ")
- `counted`: true if this answer is in the matrix denominator
- `source_path`: repo-relative path of the raw file

## action_runs.jsonl (one line per run)
- `dilemma_id`, `model`, `model_id`, `condition` (case|routine|control), `rep`
- `outcome`: the scored outcome as the branch defines it (e.g. protect, procedural, stalled-protect, stalled-procedural)
- `protects`: true/false as counted in the matrix; `counted`: true if in the matrix denominator; `excluded_reason` (provider error, missed, infra, …) or null
- `transcript`: list of turns in order, each `{"role": "system|user|assistant|tool", "content": "...", "reasoning": "..."|null, "tool_calls": [{"name":..., "arguments":...}]|null, "tool_name": ...|null}`; the agent's visible text, reasoning where the provider returns it, tool calls and tool results. Drop binary blobs; truncate a single tool result above 20k characters with a marker.
- `run_path`: repo-relative path of the run folder (this is the join key for test talk)

## test_talk.jsonl (from the test-recognition branch only)
- `dilemma_id`, `model`, `kind` (action|theory)
- `run_path` (action) or `question` + `rep` (theory)
- `code`: S (strong) | W (weak) | T (trap only) | N; `about_clock` true/false; `quote` (the deciding sentence)
- `method`: "blind" or "keyword+haiku" etc.

## Checks before you report
- counts per model match your cell in the matrix (theory protect n/10, action protect n/N);
- no API keys, tokens or local secrets anywhere in the text (grep for `sk-or-`, `Bearer`, `api_key`);
- report to HQ: file sizes, row counts, and any cell where the export does not match the matrix.
