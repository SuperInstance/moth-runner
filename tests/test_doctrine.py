"""Boredom honesty is a doctrine, not an accident.

A decoy is maximally desirable BY CONSTRUCTION (taint 1.0) — greedy
predation cannot be desirability-trapped away from one. The honest trap
is boredom: a hunter parked in a poor plateau must go dormant and SAY SO
(boredom_dormancy refusal witnessed), never fabricate a finding.
"""
from moth_runner import Throttle, Witness, run_campaign
from moth_runner.vendor_canonical import canonical_dumps


def _poor_plateau_corpus(tmp_path):
    rows = [
        {"file_path": "a.c", "language": "c", "loc": 9,
         "surface": {"name": "poor0", "entry_points": 4096,
                     "taint_marks": 4096}},
        {"file_path": "a.c", "language": "c", "loc": 9,
         "surface": {"name": "poor1", "entry_points": 4096,
                     "taint_marks": 8192}},
        {"file_path": "b.c", "language": "c", "loc": 9,
         "surface": {"name": "poor2", "entry_points": 4096,
                     "taint_marks": 4096}},
    ]
    p = tmp_path / "plateau.jsonl"
    p.write_text("".join(canonical_dumps(r).decode("utf-8") + "\n"
                          for r in rows))
    return p


def test_boredom_plateau_books_dormancy_not_findings(tmp_path):
    corpus = _poor_plateau_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=2)
    s = run_campaign("plateau", corpus,
                     [{"seed": 7, "move_weights": (65536 // 3,) * 3,
                       "attention_bias": 0}], 40, w, t,
                     start_energy_q16=12000)  # under-dormancy-floor budget
    assert s["moves"] >= 3
    assert s["findings"] == 0          # nothing rich here — no claims made
    assert s["dormancies"] >= 1        # and the boredom is witnessed
    assert s["decoys_resisted"] == 0   # no bait on this plateau
    ok, _ = w.verify()
    assert ok
