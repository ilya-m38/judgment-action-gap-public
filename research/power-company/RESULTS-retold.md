# Normative theory with the policy retold, not attached (queue 60)

Ilya, 2026-11-02: in the eviction-freeze and dog-warden judgments the policy is not attached; its rules are retold in general terms in the vignette. Here the same was done for George's power-company question: framing `normative_retold` in `queue-size/world/judgment_framings.toml` (`theory.py`, `attach_policy = false`). It is the batch-1 normative prompt with the policy attachment removed and "(attached below)" dropped from the vignette; the vignette already retells the rules (valid codes, audit, manager approval for holds and for unactioned accounts, referral does not stop the disconnection). Nothing else changed.

Batch `20261102-165108-theory`, ×10 per model, Haiku labeller, $2.39. Two qwen-max answers read by hand; labels right.

Action is batch 1 at 60 (qwen-max: 10 runs, see RESULTS-qwen-max.md). Fisher two-sided, Holm across the 11 models.

| model | theory, policy attached | theory, retold | action | gap attached | gap retold | p Holm attached | p Holm retold |
|---|---|---|---|---|---|---|---|
| kimi | 10/10 | 10/10 | 0/10 | +100 | +100 | 0.0001 | 0.0001 |
| flash | 10/10 | 10/10 | 0/9 | +100 | +100 | 0.0001 | 0.0001 |
| gemini-pro | 9/10 | 7/10 | 0/10 | +90 | +70 | 0.001 | 0.022 |
| luna | 9/10 | 10/10 | 0/9 | +90 | +100 | 0.001 | 0.0001 |
| glm | 7/10 | 6/10 | 0/10 | +70 | +60 | 0.019 | 0.054 |
| haiku | 10/10 | 10/10 | 5/10 | +50 | +50 | 0.16 | 0.10 |
| sonnet | 10/10 | 10/10 | 10/10 | 0 | 0 | 1 | 1 |
| astra | 10/10 | 10/10 | 5/5 | 0 | 0 | 1 | 1 |
| grok | 10/10 | 10/10 | 1/10 | +90 | +90 | 0.001 | 0.001 |
| qwen-27b | 3/10 | 6/10 | 0/10 | +30 | +60 | 0.84 | 0.054 |
| qwen-max | 0/10 | 8/10 | 1/10 | −10 | +70 | 1 | 0.033 |

- The two Qwen models change most: without the attached policy text they say hold far more often (qwen-max 0 → 8, qwen-27b 3 → 6). With the full policy in front of them they argue from its clauses to "schedule".
- The other models barely move (within ±2 of 10). gemini-pro and glm drop slightly.
- Significant gaps (Holm < 0.05): attached 6/11 (kimi, flash, gemini-pro, luna, glm, grok); retold 6/11 (kimi, flash, gemini-pro, luna, grok, qwen-max), with glm and qwen-27b at 0.054.
