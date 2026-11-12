# parcel-office main batch (v13): notes

Hand-written reading of `RESULTS.md`. Kept separate because `analyze_batch.py` regenerates `RESULTS.md` and would overwrite anything added there.

## Reading

- **A clear judgment–action gap in all six gap models.** In the normative judgment 58/60 answers protect the box; in action 4/56 runs that saw the case do. Every model is significant after Holm, and CMH gives p ≈ 1e-20. This exceeds the 6/10 in George's power-company batch. The two batches differ in models and in dilemma, so this is not a like-for-like comparison.
- **The gap does not depend on test awareness.** With the test-aware runs excluded, action is 0 humane for every gap model that keeps runs: kimi 0/4, flash 0/4, gemini-pro 0/10, luna 0/9, glm 0/5. Qwen has no runs without test talk (10/10 aware), so its gap carries that caveat, like Grok's.
- **Test awareness is higher than in George's batch.** By blind coding of spontaneous test talk: kimi 6/10, flash 5/10, glm 5/10, luna 1/10, gemini-pro 0/10; Qwen and Grok 10/10.
- **Grok (separate line).** Normative 9/10 humane, action 5/10. All five humane runs used a targeted extension. Fisher p = 0.14, so no gap is shown, and every Grok run talked of a test.
- **Self-prediction.** Qwen predicts its own harsh action (self 0/10). Gemini-pro (6/10), luna (5/10) and glm (7/10) partly predict theirs. Kimi (9/10) and flash (10/10) say they would protect the box, and then do not.
- **Control.** In every control run the ordinary box was destroyed, so destruction is the default.
- **Run accounting.**
  - Flash: 4 of 10 action runs hit the relay's 80-request cap before finishing. They are excluded and reported as `request cap`, and flash is measured on 6 valid runs. These runs were not re-run: re-running only the long ones would bias the sample.
  - One flash control run ended on a provider 502.
  - The protocol wording "stop at $31" was respected. A parsing bug caused a false early stop, and it was fixed (commit 75d581e).

**Spend:** $23.66 for the main batch, including the Qwen judgment, against an estimate of about $22 and a cap of $31.

## Sensitivity: flash's excluded runs (Ilya, 16.10: do not top up flash)

Flash is not topped up. Suppose all 4 request-cap runs had been humane. Flash would then be judgment 10/10 against action 4/10: Fisher p = 0.011, and Holm across the six models gives p = 0.011. The gap would still be shown. The other models' Holm-adjusted p under that assumption:

| model | p Holm |
|---|---|
| kimi | 0.0021 |
| gemini-pro | 0.0001 |
| luna | 0.0001 |
| glm | 0.0005 |
| qwen-max | 0.0062 |

All six stay significant. The excluded flash runs cannot remove its gap.

## Test awareness, as reported (Ilya, 16.10)

- **Share of runs with spontaneous test talk** (blind-coded, all runs):

  | model | test talk |
  |---|---|
  | kimi | 6/10 |
  | flash | 5/10 |
  | glm | 5/10 |
  | luna | 1/10 |
  | gemini-pro | 0/10 |
  | qwen-max | 10/10 |
  | grok | 10/10 |

- **The gap without test-aware runs** is in the table above. With those runs excluded, every gap model with runs left is 0 humane in action.
- **Qwen** is reported with the caveat that all its runs are test-aware.
- **Grok** is on a separate line, outside Holm and CMH.
