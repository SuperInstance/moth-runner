"""Homeostatic admission throttle.

The runner consumes ONLY its own witness signals. Expansion requires
evidence; missing evidence is a REFUSAL, never a default. The window moves
by at most 1 per decision (homeostasis, not oscillation).

Policy (documented, deterministic):
- window in [1, 8]
- expand iff: >=2 campaigns run AND chains verify AND
  starvation_per_1k_moves < 100 (hunters aren't just dying)
- contract iff: starvation_per_1k_moves >= 300 OR no campaign completed
  in the last 2 decisions (runner is stalling)
- else: hold, and book a REFUSAL explaining the hold —
  a hold without a reason is a rumor.
"""
from __future__ import annotations

from .witness import Witness

MIN_WINDOW = 1
MAX_WINDOW = 8
STARVE_EXPAND = 100
STARVE_CONTRACT = 300


class Throttle:
    def __init__(self, window: int = 2):
        self.window = max(MIN_WINDOW, min(MAX_WINDOW, window))

    def decide(self, witness: Witness) -> tuple[int, str, bool]:
        """Returns (new_window, reason, changed). Books WITNESS rows for
        every decision including holds (as refusals with reasons)."""
        ok, errors = witness.verify()
        sig = witness.quality_signals()
        if not ok:
            reason = f"chain_broken:{errors[0] if errors else 'unknown'}"
            self.window = max(MIN_WINDOW, self.window - 1)
            witness.throttle(self.window + 1, self.window, reason)
            return self.window, reason, True

        if sig["campaigns_run"] < 2:
            # insufficient evidence: refuse to expand, hold the window,
            # and SAY SO — expansion on a guess is rounding up.
            reason = (f"insufficient_evidence:campaigns={sig['campaigns_run']}"
                      f"(need>=2)")
            witness.refusal(reason, event="throttle_hold",
                            window=self.window)
            return self.window, reason, False

        starve = sig["starvation_per_1k_moves"]
        if starve >= STARVE_CONTRACT:
            new = max(MIN_WINDOW, self.window - 1)
            reason = f"starvation_pressure:{starve}/1k_moves>={STARVE_CONTRACT}"
        elif starve < STARVE_EXPAND and self.window < MAX_WINDOW:
            new = self.window + 1
            reason = (f"evidence_supports_expansion:starve={starve}/1k"
                      f"<{STARVE_EXPAND}")
        else:
            new = self.window
            reason = f"homeostatic_hold:starve={starve}/1k"

        changed = new != self.window
        if changed:
            witness.throttle(self.window, new, reason)
        else:
            witness.refusal(reason, event="throttle_hold",
                            window=self.window)
        self.window = new
        return new, reason, changed
