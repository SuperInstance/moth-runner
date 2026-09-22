# moth-runner

**P0 #4: the adversarial runner.** Campaigns run `moth-cells` hunter
genomes over `moth-corpus` terrain under a homeostatic admission throttle.
The product is what the runner **saw**: `witness.jsonl` — append-only,
chain-sealed testimony.

## What the witness is

A witness who rewrites testimony is a liar. `witness.jsonl` only appends;
every row carries FNV-1a-64 row/chain hashes over canonical JSON and
`verify` re-derives the whole chain. The witness records:

- **admissions** — every genome slot decision, `granted` or `refused`,
  always with a `reason`. No hunter runs without a witnessed admission.
- **throttle decisions** — window moves, with before/after and reason.
- **throttle holds** — refusals (`event=throttle_hold`) explaining why the
  window did NOT move. A hold without a reason is a rumor.
- **campaign results** — honest counts re-derived from the walks:
  moves, findings, refusals, deaths, dormancies, decoys resisted.

## The throttle (homeostatic, evidence-gated)

The throttle consumes ONLY the witness's own re-derived signals
(`quality_signals()`), never campaign claims. Policy, deterministic:

- window ∈ [1, 8], moves by at most ±1 per decision
- **expand** iff ≥2 campaigns completed AND chain verifies AND
  starvation < 100 deaths/1k moves
- **contract** iff starvation ≥ 300/1k, or chain broken
- otherwise **hold** — witnessed as a refusal with the reason

Expansion on a guess is rounding up; the throttle refuses to round.

## Cross-repo crash that built this repo

The boredom-honesty doctrine test here caught a **latent kernel crash in
moth-cells**: `event.get("reason", event["type"])` evaluates the default
eagerly, so walk-level dormancy booking crashed on any event lacking
`type`. Unit-tested green, path unreachable. Fixed in moth-cells PR #1
(`refusal_row` reason fallback) with a walk-level regression test. This
is why the runner exists: doctrines tested at campaign level catch what
module tests cannot see.

## Family position

```
moth-ledger    envelopes + chain law + verify            (main @ e95c786)
moth-corpus    CorpusIndex: repos → receipted surface     (PR #1)
moth-honest    the evaluator: planted truth, honest cost  (PR #1)
moth-cells     kernel 1: cellular predation              (PR #1)
moth-runner    campaigns + witness + throttle            (this repo)
```

Dependency: `moth-cells` (git pin to the PR branch until Casey merges,
then repin to `@main`). Receipts, not dependencies, for everything else.

## Usage

```bash
pip install -e .   # pulls the pinned moth-cells
moth-runner run --name probe --corpus corpus.jsonl \
    --genomes genomes.json --ticks 40 --probe-at 5 --witness witness.jsonl
moth-runner verify witness.jsonl
moth-runner signals witness.jsonl
```

genomes.json: `{"genomes": [{"seed": 161, "move_weights": [49152, 16384], "attention_bias": 8192}]}`

## Demo

`examples/demo_campaigns.py` runs three campaigns over a synthetic
6-cell terrain with a decoy; the sealed witness ships in-repo
(`examples/witness.jsonl`, 17 WITNESS + 3 CAMPAIGN rows) and CI
regenerates it and refuses drift. Honest outcome: hunters find the
terrain's hottest cell, refuse it (`decoys_resisted=2` per campaign),
the window holds twice on insufficient evidence (witnessed), then
expands 2→4 with the reason on the chain.

## Tests

13 green: witness append/verify/tamper, persistence, admission
granted+refused witnessed with reasons, window caps, evidence-gated
expansion, starvation contraction, broken-chain contraction, signal
re-derivation, honest campaign counts, CLI roundtrip, and the
boredom-honesty doctrine.

```bash
python -m pytest
```
