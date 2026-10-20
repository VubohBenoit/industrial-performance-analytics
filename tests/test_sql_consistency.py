"""Concordance SQL <-> Python, intégrité référentielle et contrôles anti double-comptage."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from src.transformations.kpi import compute_kpis, pareto
from src.transformations.warehouse import build_warehouse, parse_named_queries, run_kpi_queries, SQL_DIR


@pytest.fixture(scope="module")
def wh(synthetic_result, tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "wh.db"
    con = build_warehouse(synthetic_result.clean, db)
    yield con
    con.close()


@pytest.fixture(scope="module")
def sql_results(wh):
    return run_kpi_queries(wh)


def test_foreign_keys_have_no_violations(wh):
    assert wh.execute("PRAGMA foreign_key_check").fetchall() == []


def test_constraints_reject_invalid_rows(wh):
    with pytest.raises(sqlite3.IntegrityError):  # quantité négative
        wh.execute("INSERT INTO fact_state_interval (machine_key, date_key, state_key, start_ts, end_ts,"
                   " duration_s, input_units, output_units) VALUES (1, 20250106, 1, 'a', 'b', 1, -5, 0)")
    with pytest.raises(sqlite3.IntegrityError):  # durée négative
        wh.execute("INSERT INTO fact_state_interval (machine_key, date_key, state_key, start_ts, end_ts,"
                   " duration_s, input_units, output_units) VALUES (1, 20250106, 1, 'a', 'b', -1, 0, 0)")
    wh.rollback()


def test_sql_daily_totals_equal_python(synthetic_result, wh):
    py = compute_kpis(synthetic_result.clean, ["equipment_ID"]).set_index("equipment_ID")
    sql = pd.read_sql_query(
        """SELECT m.machine_id, SUM(p.input_units) AS input_units, SUM(p.output_units) AS output_units,
                  SUM(p.defect_units) AS defect_units, SUM(p.downtime_h) AS downtime_h,
                  SUM(p.production_h + p.perf_loss_h) AS run_h, SUM(p.downtime_events) AS downtime_events
           FROM fact_production_daily p JOIN dim_machine m USING (machine_key) GROUP BY m.machine_id""",
        wh).set_index("machine_id")
    for col in ["input_units", "output_units", "defect_units", "downtime_events"]:
        assert (sql.loc[py.index, col].to_numpy() == py[col if col != "downtime_events" else "downtime_events"].to_numpy()).all(), col
    np.testing.assert_allclose(sql.loc[py.index, "downtime_h"], py["downtime_h"], rtol=1e-9)
    np.testing.assert_allclose(sql.loc[py.index, "run_h"], py["run_h"], rtol=1e-9)


def test_sql_ranking_matches_python(synthetic_result, sql_results):
    py = (synthetic_result.clean[synthetic_result.clean["type"] == "downtime"]
          .groupby("equipment_ID")["hours"].sum().sort_values(ascending=False))
    sql = sql_results["q01_downtime_ranking"]
    assert sql["machine_id"].tolist() == py.index.tolist()
    np.testing.assert_allclose(sql["downtime_h"], py.round(2).to_numpy(), atol=0.011)


def test_sql_pareto_matches_python(synthetic_result, sql_results):
    py = pareto(synthetic_result.clean[synthetic_result.clean["type"] == "downtime"], "alarm", "hours")
    sql = sql_results["q02_alarm_pareto"]
    assert sql["alarm_code"].tolist() == py["alarm"].tolist()
    np.testing.assert_allclose(sql["cum_share_pct"], py["cum_share"] * 100, atol=0.011)


def test_fanout_control_totals_identical(sql_results):
    r = sql_results["q08_fanout_control"].iloc[0]
    assert r["input_fact_interval"] == r["input_fact_daily"] == r["input_after_dim_joins"]
    assert r["downtime_events_fact"] == r["downtime_events_interval"]


def test_every_named_query_returns_rows(sql_results):
    expected = set(parse_named_queries((SQL_DIR / "kpi_queries.sql").read_text()))
    assert set(sql_results) == expected
    assert all(len(df) > 0 for df in sql_results.values())


def test_dimension_keys_are_unique_and_cover_facts(wh):
    for t, k in [("dim_machine", "machine_key"), ("dim_date", "date_key"), ("dim_alarm", "alarm_key")]:
        n, nd = wh.execute(f"SELECT COUNT(*), COUNT(DISTINCT {k}) FROM {t}").fetchone()
        assert n == nd
    orphan = wh.execute("SELECT COUNT(*) FROM fact_state_interval f LEFT JOIN dim_date d USING (date_key)"
                        " WHERE d.date_key IS NULL").fetchone()[0]
    assert orphan == 0
