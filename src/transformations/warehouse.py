"""Construction de l'entrepôt SQLite (schéma en étoile) et exécution des requêtes KPI."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.transformations.kpi import nominal_speed

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"

STATE_DIM = [  # (state_name, is_run, is_loading)
    ("production", 1, 1), ("performance_loss", 1, 1), ("downtime", 0, 1),
    ("scheduled_downtime", 0, 0), ("idle", 0, 0),
]


def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    d = pd.DataFrame({"full_date": pd.date_range(dates.min(), dates.max(), freq="D")})
    d["date_key"] = d["full_date"].dt.strftime("%Y%m%d").astype(int)
    d["year"] = d["full_date"].dt.year
    d["month"] = d["full_date"].dt.month
    d["year_month"] = d["full_date"].dt.strftime("%Y-%m")
    d["iso_week"] = d["full_date"].dt.isocalendar().week.astype(int)
    d["week_start"] = (d["full_date"] - pd.to_timedelta(d["full_date"].dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")
    d["weekday"] = d["full_date"].dt.weekday
    d["is_weekend"] = (d["weekday"] >= 5).astype(int)
    d["full_date"] = d["full_date"].dt.strftime("%Y-%m-%d")
    return d[["date_key", "full_date", "year", "month", "year_month", "iso_week", "week_start", "weekday", "is_weekend"]]


def build_dimensions(clean: pd.DataFrame) -> dict[str, pd.DataFrame]:
    nom = nominal_speed(clean)
    machines = pd.DataFrame({"machine_id": sorted(clean["equipment_ID"].unique())})
    machines["machine_key"] = range(1, len(machines) + 1)
    machines["nominal_speed"] = machines["machine_id"].map(nom)
    alarms = pd.DataFrame({"alarm_code": sorted(clean["alarm"].dropna().unique())})
    alarms["alarm_key"] = range(1, len(alarms) + 1)
    states = pd.DataFrame(STATE_DIM, columns=["state_name", "is_run", "is_loading"])
    states["state_key"] = range(1, len(states) + 1)
    return {
        "dim_date": build_dim_date(clean["date"]),
        "dim_machine": machines[["machine_key", "machine_id", "nominal_speed"]],
        "dim_state": states[["state_key", "state_name", "is_run", "is_loading"]],
        "dim_alarm": alarms[["alarm_key", "alarm_code"]],
    }


def build_fact_state_interval(clean: pd.DataFrame, dims: dict[str, pd.DataFrame]) -> pd.DataFrame:
    mk = dims["dim_machine"].set_index("machine_id")["machine_key"]
    sk = dims["dim_state"].set_index("state_name")["state_key"]
    ak = dims["dim_alarm"].set_index("alarm_code")["alarm_key"]
    f = pd.DataFrame({
        "machine_key": clean["equipment_ID"].map(mk),
        "date_key": clean["date"].dt.strftime("%Y%m%d").astype(int),
        "state_key": clean["type"].map(sk),
        "alarm_key": clean["alarm"].map(ak),
        "start_ts": clean["start"].dt.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "end_ts": clean["end"].dt.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "duration_s": clean["elapsed"].astype(float),
        "input_units": clean["pi"].astype(int),
        "output_units": clean["po"].astype(int),
        "speed": clean["speed"].astype(float),
        "flag_long_duration": clean["flag_long_duration"].astype(int),
    })
    f = f.sort_values(["machine_key", "start_ts", "end_ts"]).reset_index(drop=True)
    f.insert(0, "interval_id", range(1, len(f) + 1))
    f["alarm_key"] = f["alarm_key"].astype("Int64")
    return f


def build_warehouse(clean: pd.DataFrame, db_path: Path | str) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript((SQL_DIR / "schema.sql").read_text())
    dims = build_dimensions(clean)
    for name, df in dims.items():
        df.to_sql(name, con, if_exists="append", index=False)
    fact = build_fact_state_interval(clean, dims)
    fact.to_sql("fact_state_interval", con, if_exists="append", index=False)
    con.executescript((SQL_DIR / "transformations.sql").read_text())
    con.commit()
    return con


def parse_named_queries(sql_text: str) -> dict[str, str]:
    parts = re.split(r"^-- name:\s*(\w+)\s*$", sql_text, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run_kpi_queries(con: sqlite3.Connection, out_dir: Path | str | None = None,
                    skip: tuple[str, ...] = ()) -> dict[str, pd.DataFrame]:
    queries = parse_named_queries((SQL_DIR / "kpi_queries.sql").read_text())
    queries = {k: v for k, v in queries.items() if k not in skip}
    results = {name: pd.read_sql_query(q, con) for name, q in queries.items()}
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, df in results.items():
            df.to_csv(out_dir / f"{name}.csv", index=False)
    return results


def export_powerbi_tables(con: sqlite3.Connection, out_dir: Path | str) -> list[Path]:
    """Exporte les tables du modèle en CSV pour l'import Power BI."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in ["dim_date", "dim_machine", "dim_state", "dim_alarm",
              "fact_state_interval", "fact_production_daily", "fact_downtime"]:
        p = out_dir / f"{t}.csv"
        pd.read_sql_query(f"SELECT * FROM {t}", con).to_csv(p, index=False)
        paths.append(p)
    return paths
