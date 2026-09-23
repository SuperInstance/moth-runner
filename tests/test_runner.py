"""Witness + throttle + admission doctrine."""
import json

import pytest

from moth_runner import Throttle, Witness, run_campaign
from moth_runner.vendor_canonical import canonical_dumps


def _terrain_corpus(tmp_path):
    rows = []
    for f, name, taint in [("a.c", "warm", 1), ("a.c", "colder", 0),
                           ("b.c", "hot", 2), ("b.c", "decoy", 4)]:
        rows.append({
            "file_path": f, "language": "c", "loc": 9,
            "surface": {
                "name": name,
                "entry_points": 65536 // 2,
                "taint_marks": (65536 * taint) // 4,
                **({"decoy": True, "sink_verified_safe": True}
                   if name == "decoy" else {}),
            },
        })
    p = tmp_path / "corpus.jsonl"
    p.write_text("".join(canonical_dumps(r).decode("utf-8") + "\n"
                          for r in rows))
    return p


def _specs(n, seed0=1):
    return [{"seed": seed0 + i,
             "move_weights": (65536 // 2, 65536 // 2, 0, 0),
             "attention_bias": 0} for i in range(n)]


def test_witness_append_only(tmp_path):
    w = Witness(tmp_path / "w.jsonl")
    w.record({"event": "hello", "n": 1})
    w.record({"event": "world", "n": 2})
    assert len(w.rows) == 2
    assert w.rows[1]["chain_hash"] != w.rows[0]["chain_hash"]


def test_witness_persists_and_verifies(tmp_path):
    path = tmp_path / "w.jsonl"
    w = Witness(path)
    w.record({"event": "a"})
    w2 = Witness(path)  # reload from disk
    ok, errors = w2.verify()
    assert ok and not errors


def test_witness_tamper_detected(tmp_path):
    path = tmp_path / "w.jsonl"
    w = Witness(path)
    w.record({"event": "a", "v": 1})
    lines = path.read_text().splitlines()
    forged = json.loads(lines[0])
    forged["v"] = 999
    lines[0] = json.dumps(forged, sort_keys=True)
    path.write_text("\n".join(lines))
    ok, errors = Witness(path).verify()
    assert not ok and errors


def test_admission_granted_and_refused_are_witnessed(tmp_path):
    corpus = _terrain_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=1)
    run_campaign("c1", corpus, _specs(3), 10, w, t, probe_at=3)
    admissions = [r for r in w.rows if r.get("event") == "admission"]
    granted = [a for a in admissions if a["decision"] == "granted"]
    refused = [a for a in admissions if a["decision"] == "refused"]
    assert len(granted) == 1 and len(refused) == 2
    assert all(a["reason"] for a in admissions)  # no silent decisions


def test_window_caps_admissions(tmp_path):
    corpus = _terrain_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=2)
    s = run_campaign("c1", corpus, _specs(5), 10, w, t)
    assert s["genomes_admitted"] == 2 and s["genomes_refused"] == 3


def test_throttle_refuses_expansion_without_evidence(tmp_path):
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=2)
    before = t.window
    new, reason, changed = t.decide(w)
    assert new == before and not changed
    assert "insufficient_evidence" in reason
    holds = [r for r in w.rows if r.get("event") == "throttle_hold"
             and r.get("reason", "").startswith("insufficient_evidence")]
    assert holds  # the hold is witnessed, not silent


def test_throttle_expands_with_good_evidence(tmp_path):
    corpus = _terrain_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=2)
    run_campaign("c1", corpus, _specs(2), 15, w, t)
    run_campaign("c2", corpus, _specs(2, seed0=9), 15, w, t)
    new, reason, changed = t.decide(w)
    assert changed and new == 3, reason
    throttles = [r for r in w.rows if r.get("event") == "throttle"]
    assert throttles and throttles[-1]["window_after"] == 3


def test_throttle_contracts_under_starvation(tmp_path):
    corpus = _terrain_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=4)
    # hunters with 1 tick of energy: die immediately, massive starvation signal
    from moth_cells import Genome, load_corpus_jsonl, walk
    cells = load_corpus_jsonl(str(corpus))
    for i in range(2):
        g = Genome(seed=100 + i, move_weights=(65536 // 2,) * 4,
                   attention_bias=0)
        h, rows = walk(g, cells, 3, start_energy_q16=65536 // 100)
        w.campaign_result(f"starve_{i}", {
            "findings": 0, "refusals": sum(
                1 for r in rows if r.get("kind") == "REFUSAL/v1"),
            "deaths": 1, "moves": max(h.moves, 1)})
    new, reason, changed = t.decide(w)
    assert changed and new == 3 and "starvation_pressure" in reason


def test_throttle_contracts_on_broken_chain(tmp_path):
    corpus = _terrain_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=3)
    run_campaign("c1", corpus, _specs(1), 5, w, t)
    # forge the last row
    lines = (tmp_path / "w.jsonl").read_text().splitlines()
    forged = json.loads(lines[-1])
    forged["summary"] = {"moves": 10**9}
    lines[-1] = json.dumps(forged, sort_keys=True)
    (tmp_path / "w.jsonl").write_text("\n".join(lines))
    w2 = Witness(tmp_path / "w.jsonl")
    new, reason, changed = t.decide(w2)
    assert changed and new == 2 and reason.startswith("chain_broken")


def test_signals_rederived_from_witness(tmp_path):
    corpus = _terrain_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=2)
    run_campaign("c1", corpus, _specs(2), 10, w, t, probe_at=3)
    sig = w.quality_signals()
    assert sig["campaigns_run"] == 1
    assert sig["admissions_granted"] == 2
    assert sig["decoys_resisted"] >= 1  # probe_at=3 is the decoy
    assert "starvation_per_1k_moves" in sig


def test_campaign_summary_honest_counts(tmp_path):
    corpus = _terrain_corpus(tmp_path)
    w = Witness(tmp_path / "w.jsonl")
    t = Throttle(window=2)
    s = run_campaign("c1", corpus, _specs(2), 20, w, t, probe_at=3)
    assert s["genome_hashes"] and len(s["genome_hashes"]) == 2
    assert s["moves"] > 0 and s["findings"] + s["refusals"] >= 1
    ok, _ = w.verify()
    assert ok
