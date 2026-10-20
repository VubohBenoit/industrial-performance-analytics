import numpy as np
import pandas as pd
import pytest

from src.transformations.kpi import compute_kpis, pareto
from tests.conftest import COLS, row
from src.cleaning.clean import clean


def test_kpis_match_hand_calculation(tiny_clean):
    nominal = pd.Series({"m1": 500.0})
    k = compute_kpis(tiny_clean, ["equipment_ID"], nominal).iloc[0]
    assert k["production_h"] == pytest.approx(2.0)
    assert k["perf_loss_h"] == pytest.approx(1.0)
    assert k["downtime_h"] == pytest.approx(0.5)
    assert k["run_h"] == pytest.approx(3.0)
    assert k["loading_h"] == pytest.approx(3.5)
    assert k["input_units"] == 1300 and k["output_units"] == 1250
    assert k["defect_units"] == 50
    assert k["defect_rate"] == pytest.approx(50 / 1300)
    assert k["quality"] == pytest.approx(1 - 50 / 1300)
    assert k["availability"] == pytest.approx(3.0 / 3.5)
    assert k["avg_downtime_min"] == pytest.approx(30.0)
    assert k["output_per_run_hour"] == pytest.approx(1250 / 3.0)
    assert k["performance_index"] == pytest.approx(1300 / (500 * 3.0))
    # OEE proxy = A x min(P,1) x Q
    expected = (3.0 / 3.5) * (1300 / 1500) * (1 - 50 / 1300)
    assert k["oee_proxy"] == pytest.approx(expected)


def test_idle_and_scheduled_excluded_from_loading_time(tiny_clean):
    k = compute_kpis(tiny_clean, ["equipment_ID"], pd.Series({"m1": 500.0})).iloc[0]
    assert k["idle_h"] == pytest.approx(0.5) and k["scheduled_h"] == pytest.approx(1.0)
    assert k["loading_h"] == pytest.approx(k["run_h"] + k["downtime_h"])


def test_zero_denominators_give_nan_not_inf():
    only_idle = clean(pd.DataFrame([row("m1", "idle", "2025-01-06 00:00:00", 30)], columns=COLS)).clean
    df = compute_kpis(only_idle, ["equipment_ID"], pd.Series({"m1": 500.0}))
    k = df.iloc[0]
    for col in ["defect_rate", "availability", "avg_downtime_min", "output_per_run_hour", "performance_index"]:
        assert np.isnan(k[col]), col
    assert not np.isinf(df.select_dtypes("number").to_numpy(dtype=float)).any()


def test_aggregation_is_additive_across_days(synthetic_result):
    c = synthetic_result.clean
    by_day = compute_kpis(c, ["equipment_ID", "date"])
    by_machine = compute_kpis(c, ["equipment_ID"]).set_index("equipment_ID")
    summed = by_day.groupby("equipment_ID")[["input_units", "output_units", "downtime_h", "run_h"]].sum()
    pd.testing.assert_frame_equal(
        summed.sort_index(), by_machine[["input_units", "output_units", "downtime_h", "run_h"]].sort_index(),
        check_exact=False, rtol=1e-9)


def test_kpi_bounds_on_synthetic(synthetic_result):
    k = compute_kpis(synthetic_result.clean, ["equipment_ID"])
    assert k["defect_units"].ge(0).all()
    assert k["defect_rate"].between(0, 1).all()
    assert k["availability"].between(0, 1).all()
    assert k["oee_proxy"].between(0, 1).all()


def test_pareto_shares_sum_to_one_and_are_sorted():
    df = pd.DataFrame({"alarm": ["a", "b", "b", "c"], "hours": [1.0, 5.0, 2.0, 2.0]})
    p = pareto(df, "alarm", "hours")
    assert p["alarm"].tolist() == ["b", "c", "a"]
    assert p["share"].sum() == pytest.approx(1.0)
    assert p["cum_share"].iloc[-1] == pytest.approx(1.0)
    assert p["cum_share"].is_monotonic_increasing


def test_oee_proxy_equals_reference_attainment_when_performance_not_capped(synthetic_result):
    """Identité algébrique : A x P x Q = (run/load) x (in/(nom x run)) x (out/in) = out/(nom x load).
    Les deux indicateurs ne sont donc pas indépendants (à documenter, pas à présenter comme deux mesures)."""
    k = compute_kpis(synthetic_result.clean, ["equipment_ID"])
    ok = k["performance_index"] <= 1
    assert ok.all()
    np.testing.assert_allclose(k.loc[ok, "oee_proxy"], k.loc[ok, "reference_attainment"], rtol=1e-9)
