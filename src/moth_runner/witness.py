"""The witness: what the runner SAW, not what hunters claim.

witness.jsonl is append-only and chain-sealed. Runner-level events are
WITNESS/v1 rows: admissions (granted/refused, with reasons), throttle
decisions, integrity checks. Campaign results arrive as CAMPAIGN/v1 rows.
The witness never edits — a witness who rewrites testimony is a liar.
"""
from __future__ import annotations

import json
from pathlib import Path

from .vendor_canonical import canonical_dumps
from .vendor_hashes import fnv1a_64_hex

GENESIS = "0" * 16


def _digest(row: dict) -> str:
    return fnv1a_64_hex(canonical_dumps(row))


class Witness:
    """Append-only sealed witness journal."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.rows: list[dict] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.rows.append(json.loads(line))

    def _prev(self) -> str:
        return self.rows[-1]["chain_hash"] if self.rows else GENESIS

    def record(self, row: dict) -> dict:
        r = dict(row)
        r.setdefault("kind", "WITNESS/v1")
        rh = _digest(r)
        ch = fnv1a_64_hex(bytes.fromhex(self._prev()) + bytes.fromhex(rh))
        r["row_hash"], r["chain_hash"] = rh, ch
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_dumps(r).decode("utf-8") + "\n")
        self.rows.append(r)
        return r

    def refusal(self, reason: str, event: str = "refusal", **fields) -> dict:
        """Book a refusal the runner owes (no silent skips)."""
        row = {"kind": "WITNESS/v1", "event": event, "reason": reason}
        row.update(fields)
        return self.record(row)

    def admission(self, genome_hash: str, decision: str, reason: str,
                  **fields) -> dict:
        row = {"kind": "WITNESS/v1", "event": "admission",
               "genome_hash": genome_hash, "decision": decision,
               "reason": reason}
        row.update(fields)
        return self.record(row)

    def throttle(self, window_before: int, window_after: int, reason: str,
                 **fields) -> dict:
        row = {"kind": "WITNESS/v1", "event": "throttle",
               "window_before": window_before, "window_after": window_after,
               "reason": reason}
        row.update(fields)
        return self.record(row)

    def campaign_result(self, campaign: str, summary: dict) -> dict:
        return self.record({"kind": "CAMPAIGN/v1", "campaign": campaign,
                            "summary": summary})

    def verify(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        prev = GENESIS
        for idx, row in enumerate(self.rows):
            r = dict(row)
            try:
                rh, ch = r.pop("row_hash"), r.pop("chain_hash")
            except KeyError as exc:
                errors.append(f"row {idx}: missing {exc}")
                break
            if rh != _digest(r):
                errors.append(f"row {idx}: row_hash mismatch")
            if ch != fnv1a_64_hex(bytes.fromhex(prev) + bytes.fromhex(rh)):
                errors.append(f"row {idx}: chain_hash mismatch")
            prev = ch
        return (not errors), errors

    def quality_signals(self) -> dict:
        """The only numbers the throttle may consume (re-derived here,
        never trusted from campaign claims)."""
        admissions = [r for r in self.rows if r.get("event") == "admission"]
        granted = [r for r in admissions if r.get("decision") == "granted"]
        refused = [r for r in admissions if r.get("decision") == "refused"]
        campaigns = [r for r in self.rows if r.get("kind") == "CAMPAIGN/v1"]
        total_findings = sum(
            c["summary"].get("findings", 0) for c in campaigns)
        total_refusals = sum(
            c["summary"].get("refusals", 0) for c in campaigns)
        deaths = sum(c["summary"].get("deaths", 0) for c in campaigns)
        decoys = sum(c["summary"].get("decoys_resisted", 0) for c in campaigns)
        dormancies = sum(c["summary"].get("dormancies", 0) for c in campaigns)
        total_moves = sum(c["summary"].get("moves", 0) for c in campaigns)
        n_granted = len(granted)
        return {
            "admissions_granted": n_granted,
            "admissions_refused": len(refused),
            "campaigns_run": len(campaigns),
            "findings": total_findings,
            "refusals": total_refusals,
            "deaths": deaths,
            "decoys_resisted": decoys,
            "dormancies": dormancies,
            "moves": total_moves,
            # starvation pressure: deaths per move, Q16-ish milli-space
            "starvation_per_1k_moves": (deaths * 1000 // total_moves)
            if total_moves else 0,
        }
