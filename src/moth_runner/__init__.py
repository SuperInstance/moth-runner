"""moth-runner — the adversarial runner: campaigns + witness + throttle.

What the runner SAW is the product: witness.jsonl is append-only and
chain-sealed. Admissions are witnessed with reasons; refusals are witnessed,
never silent. The throttle consumes only the witness's own re-derived
signals and holds (with stated reasons) rather than guesses.
"""
from .campaign import load_genome_specs, run_campaign
from .throttle import MAX_WINDOW, MIN_WINDOW, Throttle
from .vendor_hashes import PINNED_VECTORS, assert_pins, fnv1a_64, fnv1a_64_hex
from .witness import Witness

__version__ = "0.1.0"

__all__ = [
    "MAX_WINDOW",
    "MIN_WINDOW",
    "PINNED_VECTORS",
    "Throttle",
    "Witness",
    "__version__",
    "assert_pins",
    "fnv1a_64",
    "fnv1a_64_hex",
    "load_genome_specs",
    "run_campaign",
]
