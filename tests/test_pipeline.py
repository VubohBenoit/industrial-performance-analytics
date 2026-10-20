"""Reproductibilité et exécution de bout en bout."""
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.generate_synthetic import generate
from src.ingestion.load import load_raw
from src.pipeline import run


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_generator_is_deterministic(tmp_path):
    a = generate(tmp_path / "a", seed=1)
    b = generate(tmp_path / "b", seed=1)
    c = generate(tmp_path / "c", seed=2)
    assert _sha(a) == _sha(b)
    assert _sha(a) != _sha(c)


def test_loader_reports_missing_file_helpfully(tmp_path):
    with pytest.raises(FileNotFoundError, match="PIADE"):
        load_raw(tmp_path, "real")


def test_loader_rejects_wrong_schema(tmp_path):
    pd.DataFrame({"a": [1]}).to_csv(tmp_path / "raw_data.csv", index=False)
    with pytest.raises(ValueError, match="Colonnes manquantes"):
        load_raw(tmp_path, "real")


def test_pipeline_end_to_end_and_reproducible(tmp_path):
    (tmp_path / "sql").mkdir()  # le SQL est lu depuis le dépôt ; root ne sert qu'aux sorties
    out1 = run("synthetic", tmp_path / "r1")
    out2 = run("synthetic", tmp_path / "r2")
    assert out1["quality"]["conservation_ok"]
    for f in ["data/processed/clean_intervals.csv", "data/processed/kpi_by_machine.csv",
              "reports/sql_results/q01_downtime_ranking.csv", "reports/sql_results/q02_alarm_pareto.csv"]:
        assert _sha(tmp_path / "r1" / f) == _sha(tmp_path / "r2" / f), f
    assert out1["findings"] == out2["findings"]
    for fig in range(1, 8):
        assert list((tmp_path / "r1/reports/figures").glob(f"fig0{fig}_*.png")), fig


def test_raw_file_is_never_modified_by_pipeline(tmp_path):
    root = tmp_path / "r"
    generate(root / "data/raw")
    raw = root / "data/raw/raw_data_synthetic.csv"
    before = _sha(raw)
    run("synthetic", root)
    assert _sha(raw) == before
