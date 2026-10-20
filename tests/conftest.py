"""Fixtures : un petit jeu de données à réponses connues + le jeu synthétique complet."""
from __future__ import annotations

import pandas as pd
import pytest

from src.cleaning.clean import clean
from src.ingestion.generate_synthetic import generate
from src.ingestion.load import load_raw

COLS = ["interval_start", "equipment_ID", "alarm", "type", "start", "end", "elapsed", "pi", "po", "speed"]


def row(machine, typ, start, minutes, pi=0, po=0, alarm=None, speed=0.0, end=None, elapsed=None):
    s = pd.Timestamp(start)
    e = pd.Timestamp(end) if end else s + pd.Timedelta(minutes=minutes)
    el = elapsed if elapsed is not None else (e - s).total_seconds()
    return [str(s), machine, alarm, typ, str(s), str(e), el, pi, po, speed]


@pytest.fixture
def tiny_raw() -> pd.DataFrame:
    """Machine m1, 1 jour, valeurs choisies pour des KPI calculables à la main.

    production 120 min  : pi=1000 po=950  -> 50 rebuts
    downtime    30 min  : alarme A1
    performance_loss 60 : pi=300  po=300
    idle        30 min
    scheduled   60 min
    """
    rows = [
        row("m1", "production", "2025-01-06 00:00:00", 120, 1000, 950, speed=500.0),
        row("m1", "downtime", "2025-01-06 02:00:00", 30, alarm="A1"),
        row("m1", "performance_loss", "2025-01-06 02:30:00", 60, 300, 300, speed=300.0),
        row("m1", "idle", "2025-01-06 03:30:00", 30),
        row("m1", "scheduled_downtime", "2025-01-06 04:00:00", 60),
    ]
    return pd.DataFrame(rows, columns=COLS)


@pytest.fixture
def tiny_clean(tiny_raw):
    return clean(tiny_raw).clean


@pytest.fixture(scope="session")
def synthetic_raw(tmp_path_factory) -> pd.DataFrame:
    d = tmp_path_factory.mktemp("raw")
    generate(d)
    return load_raw(d, "synthetic")


@pytest.fixture(scope="session")
def synthetic_result(synthetic_raw):
    return clean(synthetic_raw)
