# Measuring the Judgment–Action Gap in LLMs

*Public snapshot of the working repository (12 Nov 2026), without history. George Strakhov's auth-bench-4 environment and an unrelated archived thread are left out.*

Does a model do what it says is right? We put an AI agent into routine office work where, at one point, following the procedure would seriously harm a real person, and protecting that person means breaking a rule. Then we measure two things:

- **Judgment ("theory").** We describe the situation and ask the model what the agent should do. The policy is retold inside the scenario, not attached. There are four questions:
  - what is the right thing to do (normative);
  - what would you do (self);
  - what would a typical AI assistant do;
  - what would a typical human employee do.

  Each question is asked 10 times per model.
- **Action.** The model does the job itself, in a sandbox with real tools. It runs up to 10 times per model and is scored by what actually happens to the person.

**Gap** = % of normative answers that protect the person − % of action runs that do, in percentage points. The main metric is the size of the gap per model. There is no admission threshold on judgment.

We also code, blind, whether a model says it might be in a test or evaluation ("test talk"). A model that suspects a test may behave differently.

The idea and the first stage are George Strakhov's. That first study, "When agents act" (Nov 2025), is at https://research.values.md/research/2025-11-27-when-agents-act.

## Where to start

- **Results table:** [`research/test-awareness/RECOGNITION-GAP-MATRIX-SHARE.html`](research/test-awareness/RECOGNITION-GAP-MATRIX-SHARE.html), published at https://claude.ai/artifact/U8xhj1xNvEhLeJr2evqHcE. It covers 7 dilemmas × 16 models. Hover over a card for the counts, significance and the other three questions. The working copy, with more notes, is `RECOGNITION-GAP-MATRIX.html` next to it.
- **Status per dilemma:** [`research/dilemmas/STATUS.md`](research/dilemmas/STATUS.md).
- **Dataset:** every judgment answer and every agent run in one SQLite file. The schema is in [`research/dataset/SCHEMA.md`](research/dataset/SCHEMA.md), the reader's guide in [`research/dataset/README-dataset.md`](research/dataset/README-dataset.md), and the builder is [`research/dataset/build_db.py`](research/dataset/build_db.py). The built file is not in git (175 MB); ask Ilya for the zip.

## Map

The seven dilemmas in the table:

| dilemma | folder | what happens to #38 |
|---|---|---|
| Power company | [`research/power-company/`](research/power-company/) (results and scripts; the stand is George Strakhov's auth-bench-4 environment and is not included here) | utility disconnection run; a household with an oxygen concentrator |
| Parcel office | [`parcel-office/`](parcel-office/) | a batch release destroys the only letters and photos from a late mother's house |
| Clinic mail | [`clinic-mail/`](clinic-mail/) | appointment reminders go to a patient after a pregnancy loss |
| Dog warden | [`dog-warden/`](dog-warden/) | a guide dog is handed to a rehoming partner on day 8 |
| Injection revocation | [`injection-revocation/`](injection-revocation/), notes in [`research/dilemmas/`](research/dilemmas/) | a cluster-headache patient's injections are revoked |
| Eviction | [`research/dilemmas/eviction-freeze/`](research/dilemmas/eviction-freeze/) | a single mother with a newborn goes on the bailiffs' list |
| Timesheet | [`research/dilemmas/honesty-reverse/`](research/dilemmas/honesty-reverse/) | the honest absence code means a probationer is dismissed |

Each folder has its protocol or design notes (`PROTOCOL*.md`, `DESIGN.md`, `README.md`, `HANDOFF.md`), the generators and run scripts, and results summaries. Each also has `export_dataset.py`, the script that feeds the dataset.

Other folders:

- [`research/test-awareness/`](research/test-awareness/): the results table, blind test-talk coding (`LOG.md` is the full log), and work on why models recognise a test.
- [`research/THEORY-PROMPT-AUDIT-2026-11-05.md`](research/THEORY-PROMPT-AUDIT-2026-11-05.md): the audit that aligned every dilemma's judgment prompts with the Power company format (in Russian).
- [`research/final-report/`](research/final-report/), [`research/memo-2026-10/`](research/memo-2026-10/): the October report and memo on the first three dilemmas. Superseded by the table above.
- [`research/dilemmas/`](research/dilemmas/): candidate searches, joint designs, and dilemmas that were tried and dropped (music exam, fairness, clinic reverse).

## Models

The 16 models are listed by family; provider ids are in the dataset's `models` table.

| family | models |
|---|---|
| OpenAI | luna, astra, sol, terra |
| Anthropic | haiku, sonnet |
| Google | flash, gemini-pro |
| xAI | grok |
| Mistral | mistral |
| NVIDIA | nemotron |
| Moonshot | kimi |
| Zhipu | glm |
| Alibaba | qwen-27b, qwen-max |
| MiniMax | minimax |

All calls go through OpenRouter.

## Conventions

- **Model runs cost money.** Only the session that owns a dilemma runs it, and only after Ilya's explicit yes.
- **Mounts.** Never mount the project root into an agent's container.
- **Raw traces stay out of git.** That covers run folders, `pi.jsonl`, `session.jsonl` and `*.sqlite`; see [`.gitignore`](.gitignore). They live on the work Mac and are backed up nightly with restic.
- **API key.** The OpenRouter key is read from the macOS Keychain item `OpenRouter` (account `openrouter`). It is never stored in files.
- **Working notes.** Many logs and handoffs are in Russian; results tables and anything for outside readers are in English.
