"""Two campaigns under the throttle, sealed into a shipped witness.

Deterministic: same genomes, same terrain, same dice -> same witness.
CI regenerates and refuses drift. The witness file is rebuilt from
scratch each run (append-only journals don't re-run; they replay).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from moth_runner import Throttle, Witness, run_campaign
from moth_runner.vendor_canonical import canonical_dumps

OUT = Path(__file__).parent / "witness.jsonl"


def build_corpus(path: Path) -> None:
    specs = [
        ("parse.c", "tokenize", 1, 1), ("parse.c", "parse", 2, 3),
        ("run.c", "dispatch", 2, 2), ("run.c", "sink", 1, 4),
        ("net.c", "route", 2, 3), ("net.c", "decoy_route", 3, 4),
    ]
    rows = []
    for f, name, e, t in specs:
        rows.append({
            "file_path": f, "language": "c", "loc": 10,
            "surface": {
                "name": name,
                "entry_points": (65536 * e) // 4,
                "taint_marks": (65536 * t) // 4,
                **({"decoy": True, "sink_verified_safe": True}
                   if name == "decoy_route" else {}),
            },
        })
    path.write_text("".join(canonical_dumps(r).decode("utf-8") + "\n"
                            for r in rows))


def main() -> int:
    work = Path(__file__).parent / "_demo"
    work.mkdir(exist_ok=True)
    corpus = work / "corpus.jsonl"
    build_corpus(corpus)
    if OUT.exists():
        OUT.unlink()

    witness = Witness(OUT)
    throttle = Throttle(window=2)
    genomes_a = [{"seed": 0xA1, "move_weights": (49152, 16384, 0, 0, 0, 0),
                  "attention_bias": 8192}] * 3
    s1 = run_campaign("probe-net-decoy", corpus, genomes_a, 40,
                      witness, throttle, probe_at=5)
    genomes_b = [{"seed": 0xB1 + i,
                  "move_weights": (65536 // 6,) * 6, "attention_bias": 0}
                 for i in range(4)]
    s2 = run_campaign("wide-sweep", corpus, genomes_b, 40,
                      witness, throttle, probe_at=5)
    # evidence gate needs >=2 completed campaigns; expansion is witnessed here
    genomes_c = [{"seed": 0xC1 + i,
                  "move_weights": (65536 // 6,) * 6, "attention_bias": 0}
                 for i in range(4)]
    s3 = run_campaign("post-evidence-sweep", corpus, genomes_c, 40,
                      witness, throttle, probe_at=5)

    ok, errors = witness.verify()
    print(f"witness sealed ({'intact' if ok else errors}) -> {OUT}")
    print(f"campaign 1: {s1['genomes_admitted']} admitted / "
          f"{s1['genomes_refused']} refused; decoys_resisted="
          f"{s1['decoys_resisted']} deaths={s1['deaths']}")
    print(f"campaign 2: {s2['genomes_admitted']} admitted / "
          f"{s2['genomes_refused']} refused; decoys_resisted="
          f"{s2['decoys_resisted']} deaths={s2['deaths']}")
    print(f"campaign 3: {s3['genomes_admitted']} admitted / "
          f"{s3['genomes_refused']} refused; decoys_resisted="
          f"{s3['decoys_resisted']} deaths={s3['deaths']}")
    events = {}
    for r in witness.rows:
        events[r["kind"]] = events.get(r["kind"], 0) + 1
    throttles = [r for r in witness.rows if r.get("event") == "throttle"]
    holds = [r for r in witness.rows if r.get("event") == "throttle_hold"]
    print(f"rows: {events}; throttle moves={len(throttles)}, "
          f"witnessed holds={len(holds)}")
    print(f"final window: {throttle.window}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
