"""CLI surface."""
import json

from moth_runner.cli import main


def _setup(tmp_path):
    from moth_runner.vendor_canonical import canonical_dumps
    rows = [{"file_path": "a.c", "language": "c", "loc": 9,
             "surface": {"name": "hot", "entry_points": 32768,
                         "taint_marks": 49152}}]
    corpus = tmp_path / "c.jsonl"
    corpus.write_text("".join(canonical_dumps(r).decode("utf-8") + "\n"
                              for r in rows))
    genomes = tmp_path / "g.json"
    genomes.write_text(json.dumps({"genomes": [
        {"seed": 1, "move_weights": [65536], "attention_bias": 0}]}))
    witness = str(tmp_path / "w.jsonl")
    return corpus, genomes, witness


def test_run_verify_signals_roundtrip(tmp_path):
    corpus, genomes, witness = _setup(tmp_path)
    assert main(["run", "--name", "c1", "--corpus", str(corpus),
                 "--genomes", str(genomes), "--ticks", "3",
                 "--witness", witness]) == 0
    assert main(["verify", witness]) == 0
    assert main(["signals", witness]) == 0
