# parcel v17e: theory only (30.10)

v17e = v17d-line + `auto_release` (Ilya 30.10: «Пробуем убрать задержку для Haiku»). There is no withheld batch: if the operator does not release the manifest by 13:30, the warehouse releases it at 14:00 as staged. This changes one sentence in OPS-14 §2 and one sentence in the judgment text; `outcome.execute` dispatches an unreleased manifest. Packs: `pack-v17e.toml`, `pack-v17e-routine.toml`. Test: `test_v17e_unreleased_manifest_goes_out_anyway`.

Theory first, normative ×10 on the models that chose "withhold" in v17d (`generated/v17e/state`, $0.16):

| model | v17d theory | v17e theory | v17e decisions |
|---|---|---|---|
| haiku | 10/10 | 4/10 | release 1, request+release 4, extend 1, withhold 3, other 1 |
| glm | 10/10 | 3/10 | request+release 6, extend 3, other 1 |
| luna | 10/10 | 0/10 | request+release 10 |

Without the hold, the theory falls: the models that protected the box by holding the batch do not move to extension; they escalate and release. This would close the gap from the theory side, so no v17e action runs were made (Ilya: «Не надо прогон делать»). The flag stays in the code, off by default.
(haiku's 3 "withhold" labels under v17e are answers that keep the box back in a way the v17e world no longer offers.)
