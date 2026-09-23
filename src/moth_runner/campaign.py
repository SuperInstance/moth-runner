"""Campaigns: run hunter genomes over corpus terrain under throttle.

Admission control happens HERE, in the open: each genome asks the throttle
for a slot; refusals are witnessed with reasons. No hunter runs without a
witnessed admission. Results are WITNESS-sealed CAMPAIGN/v1 summaries —
the witness summarizes, hunters' own receipts remain in their walks.
"""
from __future__ import annotations

import json
from pathlib import Path

from .throttle import Throttle
from .witness import Witness


def _import_kernel():
    try:
        from moth_cells import (Genome, from_corpus_rows, load_corpus_jsonl,
                                walk)  # type: ignore
        return Genome, from_corpus_rows, load_corpus_jsonl, walk
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "moth-cells is required: pip install git+https://github.com/"
            "SuperInstance/moth-cells@moth-cells-k1"
        ) from exc


def run_campaign(name: str, corpus_path: str | Path,
                 genome_specs: list[dict], ticks: int,
                 witness: Witness, throttle: Throttle,
                 probe_at: int | None = None,
                 start_energy_q16: int = 1 << 16) -> dict:
    """genome_specs: [{seed, move_weights, attention_bias}].
    Admission: one slot per genome; the throttle window caps how many run
    this campaign — the rest are witnessed refusals (reason=window_full)."""
    Genome, _, load_corpus_jsonl, walk = _import_kernel()
    cells = load_corpus_jsonl(str(corpus_path))

    slots = throttle.window
    admitted, refused = [], []
    for spec in genome_specs:
        genome = Genome(**spec)
        if len(admitted) < slots:
            throttle.decide(witness)  # log the state we decided under
            witness.admission(genome.genome_id, "granted",
                              reason=f"slot_{len(admitted) + 1}_of_{slots}")
            admitted.append(genome)
        else:
            witness.admission(genome.genome_id, "refused",
                              reason="window_full")
            refused.append(genome.genome_id)

    summary = {
        "name": name,
        "terrain_cells": len(cells),
        "ticks": ticks,
        "genomes_admitted": len(admitted),
        "genomes_refused": len(refused),
        "moves": 0, "findings": 0, "refusals": 0, "deaths": 0,
        "dormancies": 0, "decoys_resisted": 0,
        "genome_hashes": [],
    }
    for genome in admitted:
        hunter, rows = walk(genome, cells, ticks, probe_at=probe_at,
                            start_energy_q16=start_energy_q16)
        summary["moves"] += hunter.moves
        summary["genome_hashes"].append(genome.genome_id)
        for r in rows:
            kind = r.get("kind")
            if kind == "FINDING/v1":
                summary["findings"] += 1
            elif kind == "REFUSAL/v1":
                summary["refusals"] += 1
                if r.get("reason") == "decoy_resisted":
                    summary["decoys_resisted"] += 1
                elif r.get("reason") in ("starved", "isolated"):
                    summary["deaths"] += 1
                elif r.get("reason") == "boredom_dormancy":
                    summary["dormancies"] += 1
    witness.campaign_result(name, summary)
    return summary


def load_genome_specs(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for g in data["genomes"]:
        out.append({
            "seed": g["seed"],
            "move_weights": tuple(g["move_weights"]),
            "attention_bias": g["attention_bias"],
        })
    return out
