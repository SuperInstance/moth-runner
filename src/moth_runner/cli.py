"""moth-runner CLI: run campaigns, inspect the witness, verify chains."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .campaign import load_genome_specs, run_campaign
from .throttle import Throttle
from .vendor_hashes import assert_pins
from .witness import Witness


def cmd_run(args: argparse.Namespace) -> int:
    assert_pins()
    witness = Witness(args.witness)
    throttle = Throttle(window=args.window)
    specs = load_genome_specs(args.genomes)
    summary = run_campaign(args.name, args.corpus, specs, args.ticks,
                           witness, throttle, probe_at=args.probe_at)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    ok, errors = Witness(args.witness_file).verify()
    if ok:
        print(f"OK: {args.witness_file} — witness testimony intact")
        return 0
    for e in errors:
        print(f"BROKEN: {e}", file=sys.stderr)
    return 1


def cmd_signals(args: argparse.Namespace) -> int:
    w = Witness(args.witness_file)
    ok, errors = w.verify()
    print(json.dumps({"chain_ok": ok, "errors": errors,
                      "signals": w.quality_signals()},
                     indent=2, sort_keys=True))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="moth-runner",
        description="P0 #4: adversarial runner — campaigns, witness.jsonl, "
                    "homeostatic-throttle admission",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run a campaign under the throttle")
    p_run.add_argument("--name", required=True)
    p_run.add_argument("--corpus", required=True)
    p_run.add_argument("--genomes", required=True, help="genome spec JSON")
    p_run.add_argument("--ticks", type=int, required=True)
    p_run.add_argument("--probe-at", type=int, default=None)
    p_run.add_argument("--window", type=int, default=2)
    p_run.add_argument("--witness", default="witness.jsonl")
    p_run.set_defaults(func=cmd_run)

    p_ver = sub.add_parser("verify", help="verify witness chain")
    p_ver.add_argument("witness_file")
    p_ver.set_defaults(func=cmd_verify)

    p_sig = sub.add_parser("signals", help="re-derived quality signals")
    p_sig.add_argument("witness_file")
    p_sig.set_defaults(func=cmd_signals)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
