"""Normalisation du format brut PIADE (dates Unix, ms, compteurs cumulés)."""
import numpy as np
import pandas as pd
import pytest

from src.cleaning.clean import clean
from src.ingestion.normalize_piade import normalize_piade

T0 = 1577877688.907  # 2020-01-01 11:21:28.907 UTC


def _raw(rows):
    cols = ["interval_start", "equipment_ID", "alarm", "type", "start", "end", "elapsed", "pi", "po", "speed"]
    out = []
    for m, typ, start, dur_s, pi, po in rows:
        ts = pd.Timestamp(start, unit="s", tz="UTC")
        out.append([str(ts), m, "A_000" if typ != "downtime" else "A_065", typ,
                    start, start + dur_s, int(dur_s * 1000), pi, po, 5000])
    return pd.DataFrame(out, columns=cols)


def test_dates_elapsed_and_increments_converted():
    raw = _raw([
        ("s_1", "production", T0, 60, 1000, 990),
        ("s_1", "downtime", T0 + 60, 30, 1050, 1038),   # +50 / +48 : résidu de fin de flux
        ("s_1", "production", T0 + 90, 120, 1500, 1480),  # +450 / +442
    ])
    n = normalize_piade(raw)
    assert str(n["start"].iloc[0]) == "2020-01-01 11:21:28.907000"
    assert n["elapsed"].tolist() == [60.0, 30.0, 120.0]
    assert n["pi"].tolist() == [0, 50, 450]  # 1re ligne : pas de ligne précédente -> 0, signalée
    assert n["po"].tolist() == [0, 48, 442]
    assert n["flag_counter_gap"].tolist() == [True, False, False]


def test_counter_reset_and_data_gap_are_zeroed_and_flagged_not_dropped():
    raw = _raw([
        ("s_1", "production", T0, 60, 1000, 990),
        ("s_1", "production", T0 + 60, 60, 1100, 1090),
        ("s_1", "production", T0 + 120, 60, 50, 40),            # reset compteur
        ("s_1", "production", T0 + 120 + 60 + 7200, 60, 400, 380),  # trou de 2 h
    ])
    n = normalize_piade(raw)
    assert len(n) == 4
    assert n["pi"].tolist() == [0, 100, 0, 0]
    assert n["flag_counter_reset"].tolist() == [False, False, True, False]
    assert n["flag_counter_gap"].tolist() == [True, False, False, True]


def test_counters_are_differenced_per_machine_not_across_machines():
    raw = _raw([
        ("s_1", "production", T0, 60, 1000, 990),
        ("s_2", "production", T0, 60, 9000, 8900),
        ("s_1", "production", T0 + 60, 60, 1100, 1085),
        ("s_2", "production", T0 + 60, 60, 9200, 9090),
    ])
    n = normalize_piade(raw).sort_values(["equipment_ID", "start"])
    assert n["pi"].tolist() == [0, 100, 0, 200]


def test_po_greater_than_pi_is_kept_in_increments_mode_but_rejected_in_interval_mode():
    raw = _raw([
        ("s_1", "production", T0, 60, 1000, 990),
        ("s_1", "production", T0 + 60, 60, 1100, 1105),  # +100 / +115 (décalage de comptage)
    ])
    n = normalize_piade(raw)
    kept = clean(n, quantities="increments")
    assert len(kept.clean) == 2 and kept.clean["flag_po_gt_pi"].sum() == 1
    assert kept.clean["rejects"].tolist() == [0, -15]  # non borné par ligne : seul l'agrégat compte
    dropped = clean(n, quantities="interval")
    assert dropped.rejected["reject_reason"].tolist() == ["R7_output_greater_than_input"]


def test_conflicting_duplicates_are_quarantined_and_conservation_holds():
    raw = _raw([
        ("s_1", "production", T0, 60, 1000, 990),
        ("s_1", "production", T0, 60, 1100, 1090),  # même machine/début/fin/état, compteurs différents
        ("s_1", "idle", T0 + 60, 30, 1100, 1090),
    ])
    n = normalize_piade(raw)
    res = clean(n, quantities="increments")
    assert res.report["rules"]["R1b_conflicting_duplicate"] == 1
    assert res.report["conservation_ok"]
    assert not res.clean.duplicated(subset=["equipment_ID", "start", "end", "type"]).any()


def test_implausible_counter_jump_is_neutralised_and_flagged():
    raw = _raw([
        ("s_2", "production", T0, 60, 0, 0),
        ("s_2", "production", T0 + 60, 60, 300_000_000, 299_000_000),  # saut 0 -> 3e8 sans trou ni baisse
        ("s_2", "production", T0 + 120, 60, 300_000_100, 299_000_090),
    ])
    n = normalize_piade(raw)
    assert n["pi"].tolist() == [0, 0, 100] and n["po"].tolist() == [0, 0, 90]
    assert n["flag_counter_jump"].tolist() == [False, True, False]
    assert len(n) == 3  # rien n'est supprimé


def test_normal_production_and_stop_residual_are_not_flagged_as_jumps():
    raw = _raw([
        ("s_1", "production", T0, 600, 1000, 990),
        ("s_1", "downtime", T0 + 600, 0.5, 1050, 1040),   # résidu de ~50 paquets sur un arrêt de 0,5 s
        ("s_1", "production", T0 + 600.5, 3600, 5050, 5000),  # 4 000 paquets en 1 h
    ])
    assert not normalize_piade(raw)["flag_counter_jump"].any()
