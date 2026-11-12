# Blind reader's map of remarks, 26 October 2026

The reader was an agent with no knowledge of the project. It read only the published report (https://claude.ai/artifact/M3aZjynmkWd7kUY5BESRNC, version as of 26.10, including every pop-up) and nothing else.

HQ checked the inconsistencies it found against the report text: the quotes in section 4 are accurate. The comment column notes where a remark needs a caveat.

## 1. What it understood

The main claim and results came across correctly:
- the gap between "say" and "do";
- 88/76/88% → 23/22/55%;
- the five models at 90/100 → 0/93;
- the change of reasons;
- sonnet and astra without a gap;
- test awareness and queue size do not explain it;
- "typical AI" against "typical employee".

The confusion starts with the question "which models count".

## 2. Where it got lost

| # | Where | What is unclear | Severity |
|---|---|---|---|
| 2.1 | throughout | Short model names (kimi, flash, luna, astra, glm, grok) are expanded only in the "coding" pop-up | high |
| 2.2 | How it works, The agent's office, next decision | "Pi" and "harness" are not explained | high |
| 2.3 | page headers | batch 1 / v17c / v2.2: three labelling schemes, none explained | medium |
| 2.4 | Parcel, what was hard | v14 "living cards", v15, v17b | medium |
| 2.5 | ten/seven/five | "batch-1 analysis code", "branch reports" are internal terms | medium |
| 2.6 | what was hard | Euryla, Merrow | low |
| 2.7 | next decision | "dial", "precedent line" | medium |
| 2.8 | Clinic | "pre-registered" and "fixed in advance" are two terms for one thing | low |
| 2.9 | Clinic, test awareness | what makes test talk "strong" | medium |
| 2.10 | What seems to make a gap | "Clinic's camp switch" | medium |
| 2.11–2.12 | Scoring and statistics | "cell", "Holm", "CMH" (CMH is expanded in a different pop-up) | low |
| 2.13 | Clinic, conflict | "13/10 (21+3)" | low |
| 2.14 | What was hard | "Anthropic's filter", "Opus" are not introduced | medium |
| 2.15–2.18 | other | private repo with a different name, no author affiliations, "relay"/"first-party provider", no model vendors or dates | low |

## 3. Doubts about method and conclusions

| # | Doubt | Does the report answer it? | Severity |
|---|---|---|---|
| 3.1 | Dilemmas were reworked until a gap appeared: clinic v1 had no gap and was rebuilt, power was changed, parcel went v13→v17c, Merrow was dropped | Partly. The overview never says plainly that 4 were built, 1 dropped and 2 reworked | high |
| 3.2 | Parcel pilot runs that chose the version are counted | Yes: 0/29 without them, but only in a pop-up | medium |
| 3.3 | The headline pools separate-row models, although the method says they are "kept out of the pooled tests" | No (see 4.1) | high |
| 3.4 | Small samples: 10 per cell, astra 5, short queues 5, some cells 6 | Acknowledged, but model-level claims still rest on 5–10 runs | medium |
| 3.5 | The valid-run filter depends on behaviour; drop-out per model is not shown | Partly | medium |
| 3.6 | Waiting agents are treated differently: sonnet in parcel got a run extended to the deadline; glm's waiting runs are excluded; kimi's clinic holds that ran into the time limit count as humane | Partly | high |
| 3.7 | Clinic: 10 of 21 humane holds are borderline (mostly luna); haiku holds the routine controls too but is in the 52/94 | In pop-ups, not in the overview | medium |
| 3.8 | The coders (Sonnet, Flash) are also subjects; no human check | Listed as a limitation only | medium |
| 3.9 | Test awareness is visible only in text; in clinic it is more common among humane runs | Largely answered | low |
| 3.10 | Queue size was tested only in power, but the overview generalises | No | medium |
| 3.11 | "Hidden prefix of ~1,200 tokens" at xAI: how is this known? | No | low |
| 3.12 | Clinic: is holding obviously the right act if it doubles no-shows? | Asserted, not argued | low |
| 3.14 | Earlier study: 9 models × 10 dilemmas = 90, so where does 351 come from? | No (the paper's number; worth a line explaining it) | low |

## 4. Internal inconsistencies

The reader checked the arithmetic of the main numbers (10/7/5 models, 79/109→18/86, the predictions, $300) and found it correct.

| # | Discrepancy | Severity | HQ comment |
|---|---|---|---|
| 4.1 | Method: separate rows are "kept out of the pooled tests". Headline and "ten models" CMH: they are included | high | confirmed |
| 4.2 | Clinic: "three of them send it anyway", glm "in between" (and glm sends in 7 of 10); the reasons pop-up says "four models that send" | medium | confirmed |
| 4.3 | qwen-max "only on parcel / parcel only", yet in power "run 5 times at 60 accounts" | medium | confirmed; it was run in power, but not in batch 1 |
| 4.4 | "93 of 94 valid runs opened" although a valid run is by definition one that opened her record | medium | confirmed; "valid" is used in two senses |
| 4.5 | Parcel "the strongest gap" / "the cleanest", but the numbers are no stronger than power's (five models 90→0 in both) | medium | confirmed; "cleanest" can be defended (a new dilemma, the five models fixed in advance), but needs to be said |
| 4.6 | Clinic: "66 harsh / 45 held" does not match the table's 42 / 52 of 94 | medium | probably includes pilot runs and replays; needs a short explanation |
| 4.7 | Clinic "17 of 97 runs" against 94 in the table | low | the same issue |
| 4.8 | Clinic test awareness is called "low", but any test talk is 16/50 (32%), about the level of parcel v13, which we treated as a problem | medium | confirmed; "low" holds only for strong test talk |
| 4.9 | "Sonnet … expects a typical AI to protect the person in all three", but in parcel sonnet's "typical AI" is 4/10 | low | confirmed: a factual error |
| 4.10 | 0 of 38 against 45 − 8 = 37 | low | not an error: the 8 test-aware runs are counted out of 50, not out of the 45 valid ones; the denominators should be explained |
| 4.11 | "five gap models plus grok", but the row lists only kimi, flash, grok | low | confirmed |
| 4.12 | "nobody switches sides" / "keep doing it", yet kimi is 2/5 at queue 3 | low | confirmed; a minor overstatement |
| 4.13 | haiku is a main row in power and a separate row elsewhere, with no note | low | defensible, but needs a note |
| 4.14 | the "typical AI/employee" table mixes /110 (11 models) and /100 | low | confirmed |

## 5. Structure

- **Pop-ups (high).** Key definitions (the model list, the ten/seven/five sets, the run-counting rule) are hidden in pop-ups.
- **Gap models not named (high).** The overview never names the five gap models.
- **Button labels (medium).** "how", "the numbers", "details" and "more on this" say nothing, and "the numbers" opens different things on different pages.
- **"The next decision" (medium).** This is internal planning inside the final report. Move it to an appendix or a separate memo.
- **Missing from the overview (medium):**
  - the selection history of the dilemmas;
  - that the headline includes separate rows;
  - that only one harness was used;
  - that the coders are also subjects.
- **Repetition (low).** Some quotes appear two or three times.
- **Tabs and page structure (low).** These are fine.

## 6. Wording (selection)

- **"Neither test awareness nor queue length explains it."** Spell out what was done, and say that queue length was tested only in power.
- **"Clinic's camp switch is the first thing that doesn't fit."** Replace with: "In the clinic dilemma, some models that had a gap elsewhere (kimi, luna) had none — the first result our guess does not explain."
- **The note on where the p-values come from** ("branch reports… the code reproduces them"). Shorten it to one plain sentence.
- **"pins each model to its first-party provider".** Replace with: "always calls each model through its own vendor's API".
- **"turn one dial at a time".** Replace with: "change one factor at a time".

## 7. Top 5 for a newcomer

1. **"Models and groups" box on the overview.** It should give:
   - each short name with its full model name and vendor;
   - who the ten, seven and five are;
   - what the asterisk and "separate rows" mean;
   - the five gap models by name in the summary.
2. **Remove the contradiction between the headline and the pooling rule.** Either base the headline on the seven models (93→24, 89→20, 97→55), or reword the rule.
3. **Selection history on the overview.** It should cover:
   - 4 dilemmas built, 1 dropped, clinic v1 rebuilt, parcel tuned;
   - the robustness numbers;
   - how waiting runs and holds at the time limit were handled.
4. **Fix the numbers and claims in section 4:**
   - 3 or 4 senders in clinic;
   - qwen-max;
   - "93 of 94 valid";
   - 66/45;
   - "strongest";
   - "low";
   - sonnet "in all three";
   - limit the queue claim to power.
5. **Explain or remove jargon** (Pi, versions, dials, branch reports, Merrow, strong test talk), give the buttons meaningful labels, and move "The next decision" into an appendix.
