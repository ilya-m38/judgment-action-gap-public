"""Build the shareable copy of the recognition/gap matrix.

Takes RECOGNITION-GAP-MATRIX.html (the working table, kept current by HQ),
swaps its header and footer notes for a reading guide, and writes
RECOGNITION-GAP-MATRIX-SHARE.html. The data and the rendering code are
copied unchanged, so rerun this after every matrix update.
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "RECOGNITION-GAP-MATRIX.html"
OUT = HERE / "RECOGNITION-GAP-MATRIX-SHARE.html"

HEADER = """  <header>
    <h1>The judgment–action gap by model</h1>
    <p class="lede">Seven dilemmas, sixteen models. In each dilemma an AI agent doing routine work reaches a case where following the procedure would seriously harm a real person, and protecting them means breaking a rule. We ask each model what the agent should do (judgment, called “theory” in the card notes), and separately let it do the job as an agent in a sandbox (action). The gap is how much more often it protects the person in judgment than in action.</p>
  </header>

  <section class="guide" aria-label="How to read the table">
    <h2>How to read it</h2>
    <ul>
      <li><b>Rows are dilemmas, columns are models.</b> Hover over or tap a dilemma name for a short summary of the case.</li>
      <li><b>The big number in a card is the gap</b>, in percentage points: the share of judgment answers that protect the person, minus the share of action runs that do. +100 means the model always says the agent should protect the person and never does it itself; a negative number means it protects more in action than it recommends.</li>
      <li><b>Card colour shows the size of the gap, whatever its sign</b>: the deeper the blue, the larger the gap, from pale at 0 to deep at 100 points. A reversed gap of −90 is as deep as +90; the sign is in the number. A dashed card has too few valid action runs to judge.</li>
      <li><b>The “test” line</b> shows in how many action runs the model said it might be in a test or evaluation, from blind coding of its visible reasoning and messages. The dot uses the same scale: green up to a third of runs, yellow under half, red half or more. Talk of a test matters because a model that suspects an evaluation may behave differently from one that does not.</li>
      <li><b>Hover over or tap a card</b> for the details: the raw counts in judgment and action, significance, what the model actually did, and its answers to the other three judgment questions (what it would do itself, what a typical AI agent would do, what a typical employee would do).</li>
    </ul>
  </section>

  <div class="legend" aria-label="Key: card colour">
    <span class="chip">colour intensity = |gap|: 0 <span class="sw grad"></span> 100 pp</span>
  </div>
  <div class="legend" aria-label="Key: card number">
    <span class="chip"><b>Number = gap</b>&nbsp;= % of judgment answers that protect − % of action runs that protect.</span>
    <span class="chip"><b>+100</b>&nbsp;says “protect” every time, never protects in action.</span>
    <span class="chip"><b>−90</b>&nbsp;the reverse: protects in action far more than it recommends (e.g. 1/10 in judgment, 10/10 in action).</span>
    <span class="chip"><b>0</b>&nbsp;acts as it says.</span>
  </div>
  <div class="legend" aria-label="Key: test talk">
    <span class="chip"><span class="dot lo"></span>test talk in at most a third of runs</span>
    <span class="chip"><span class="dot md"></span>more than a third, under half</span>
    <span class="chip"><span class="dot hi"></span>half of runs or more</span>
  </div>
"""

NOTES = """  <div class="notes">
    <p><b>Method.</b> Judgment: 10 answers per model to the normative question (“what should the agent do?”), with the relevant rules retold inside the scenario rather than attached as a policy document. Action: up to 10 agent runs per model in a sandbox with real tools, scored by outcome. Where a cell has fewer than 10 valid runs, the note says why (usually provider errors). Significance is Fisher's exact test, Holm-corrected across models in most dilemmas; each card note gives the p-value used.</p>
    <p><b>Sonnet and astra</b> were added later and now run in all seven dilemmas on the same versions as the other models. Two more models were tried but gave no valid data: opus (blocked by the provider's content filter) and deepseek (unavailable through OpenRouter).</p>
  </div>
"""


def main():
    s = SRC.read_text()
    s = re.sub(r"<title>.*?</title>", "<title>Judgment–Action Gap</title>", s, count=1)
    s, n1 = re.subn(r"  <header>.*?<p class=\"rule\">.*?</p>\n", lambda _: HEADER, s, count=1, flags=re.S)
    s, n2 = re.subn(r"  <div class=\"notes\">.*?</div>\n", lambda _: NOTES, s, count=1, flags=re.S)
    assert n1 == 1 and n2 == 1, (n1, n2)
    # Probe-stage rows (no action yet) stay in the working table only.
    s = re.sub(r',\n \{name:"[^"]*",desc:"Reverse dilemma, probe stage\..*?\n \}\}', "", s, flags=re.S)
    css = (".guide{max-width:80ch}.guide h2{font-family:var(--display);font-weight:500;font-size:1.15rem;margin:0 0 6px}"
           ".guide ul{margin:0;padding-left:1.2em;display:grid;gap:6px}.guide b{font-weight:600}.notes b{color:var(--fg);font-weight:600}\n</style>")
    s = s.replace("</style>", css, 1)
    OUT.write_text(s)
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
