import pandas as pd

from src.cleaning.clean import clean
from tests.conftest import COLS, row


def _frame(*rows):
    return pd.DataFrame(list(rows), columns=COLS)


def test_clean_input_is_not_mutated(tiny_raw):
    before = tiny_raw.copy(deep=True)
    clean(tiny_raw)
    pd.testing.assert_frame_equal(tiny_raw, before)


def test_exact_duplicates_dropped_once():
    r = row("m1", "production", "2025-01-06 00:00:00", 60, 100, 90, speed=100.0)
    res = clean(_frame(r, r, r))
    assert len(res.clean) == 1
    assert res.report["rules"]["R1_exact_duplicates_dropped"] == 2


def test_negative_duration_is_quarantined_not_silently_lost():
    bad = row("m1", "downtime", "2025-01-06 10:00:00", 0, alarm="A1", end="2025-01-06 09:59:00", elapsed=-60)
    ok = row("m1", "production", "2025-01-06 11:00:00", 60, 100, 100, speed=100.0)
    res = clean(_frame(bad, ok))
    assert len(res.clean) == 1
    assert res.rejected["reject_reason"].tolist() == ["R4_end_before_start"]


def test_output_greater_than_input_rejected():
    res = clean(_frame(row("m1", "production", "2025-01-06 00:00:00", 60, 100, 120, speed=100.0)))
    assert res.clean.empty and res.rejected["reject_reason"].iloc[0] == "R7_output_greater_than_input"


def test_negative_quantity_rejected():
    res = clean(_frame(row("m1", "production", "2025-01-06 00:00:00", 60, -5, 0, speed=100.0)))
    assert res.rejected["reject_reason"].iloc[0] == "R6_negative_quantity"


def test_unknown_type_rejected():
    res = clean(_frame(row("m1", "exploded", "2025-01-06 00:00:00", 60)))
    assert res.rejected["reject_reason"].iloc[0] == "R2_unknown_type"


def test_type_is_normalised_before_validation():
    res = clean(_frame(row("m1", " Production ", "2025-01-06 00:00:00", 60, 10, 10, speed=10.0)))
    assert res.clean["type"].iloc[0] == "production"


def test_unparsable_date_rejected():
    r = row("m1", "idle", "2025-01-06 00:00:00", 10)
    r[4] = "not-a-date"
    res = clean(_frame(r))
    assert res.rejected["reject_reason"].iloc[0].startswith("R3")


def test_downtime_without_alarm_gets_explicit_unknown_and_flag():
    res = clean(_frame(row("m1", "downtime", "2025-01-06 00:00:00", 15, alarm=None)))
    assert res.clean["alarm"].iloc[0] == "UNKNOWN"
    assert bool(res.clean["flag_alarm_imputed"].iloc[0])


def test_inconsistent_elapsed_is_recomputed_and_flagged():
    res = clean(_frame(row("m1", "idle", "2025-01-06 00:00:00", 10, elapsed=9999)))
    assert res.clean["elapsed"].iloc[0] == 600
    assert bool(res.clean["flag_elapsed_recomputed"].iloc[0])


def test_atypical_but_plausible_value_is_kept_and_flagged():
    base = [row("m1", "downtime", f"2025-01-{d:02d} 08:00:00", 15, alarm="A1") for d in range(6, 26)]
    base.append(row("m1", "downtime", "2025-02-10 08:00:00", 40 * 60, alarm="A1"))  # 40 h
    res = clean(_frame(*base))
    assert len(res.clean) == 21  # aucune suppression
    assert res.clean.sort_values("elapsed").iloc[-1]["flag_long_duration"]
    assert res.report["rows_rejected"] == 0


def test_row_conservation_equation_on_synthetic(synthetic_result):
    rep = synthetic_result.report
    assert rep["conservation_ok"]
    assert rep["rows_raw"] == rep["rows_clean"] + rep["rows_rejected"] + rep["rows_dropped_duplicates"]


def test_synthetic_injected_faults_are_all_caught(synthetic_result):
    r = synthetic_result.report["rules"]
    assert r["R1_exact_duplicates_dropped"] == 20
    assert r["R4_end_before_start"] == 12
    assert r["R7_output_greater_than_input"] == 15
    assert r["R6_negative_quantity"] == 5
    assert r["R8_downtime_alarm_set_unknown"] == 25
    assert r["R5_elapsed_recomputed"] >= 8
    assert r["R10_long_duration_flagged_kept"] >= 4


def test_clean_output_respects_hard_invariants(synthetic_result):
    c = synthetic_result.clean
    assert (c["elapsed"] >= 0).all()
    assert (c["po"] <= c["pi"]).all()
    assert (c["pi"] >= 0).all() and (c["po"] >= 0).all()
    assert (c["end"] >= c["start"]).all()
    assert not c.duplicated(subset=["equipment_ID", "start", "end", "type"]).any()
    assert c.loc[c["type"] == "downtime", "alarm"].notna().all()
