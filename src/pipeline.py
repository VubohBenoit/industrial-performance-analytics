"""Pipeline de bout en bout : brut -> propre -> entrepôt SQL -> KPI -> figures.

Usage :
    python -m src.pipeline --source synthetic     # données simulées (défaut)
    python -m src.pipeline --source real          # PIADE réel (data/raw/raw_data.csv)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analytics.eda import run_eda
from src.cleaning.clean import clean
from src.ingestion.generate_synthetic import generate
from src.ingestion.load import SOURCES, load_raw
from src.transformations.kpi import compute_kpis, nominal_speed
from src.transformations.warehouse import build_warehouse, export_powerbi_tables, run_kpi_queries


def run(source: str = "synthetic", root: Path | str = ".") -> dict:
    root = Path(root)
    raw_dir, proc = root / "data/raw", root / "data/processed"
    if source == "synthetic" and not (raw_dir / SOURCES["synthetic"]).exists():
        generate(raw_dir)
    raw = load_raw(raw_dir, source)
    res = clean(raw, quantities="increments" if source == "real" else "interval")
    proc.mkdir(parents=True, exist_ok=True)
    res.clean.to_csv(proc / "clean_intervals.csv", index=False)
    res.rejected.to_csv(proc / "rejected_rows.csv", index=False)
    res.report["data_source"] = source
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports/data_quality_report.json").write_text(
        json.dumps(res.report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    nom = nominal_speed(res.clean)
    compute_kpis(res.clean, ["equipment_ID"], nom).to_csv(proc / "kpi_by_machine.csv", index=False)
    compute_kpis(res.clean, ["equipment_ID", "date"], nom).to_csv(proc / "kpi_by_machine_day.csv", index=False)

    con = build_warehouse(res.clean, proc / "warehouse.db")
    # Analyses « état précédent » (q07, q09) non valides sur compteurs cumulés : exclues en mode réel
    skip = ("q07_defects_after_downtime", "q09_defects_after_downtime_by_machine") if source == "real" else ()
    sql_results = run_kpi_queries(con, root / "reports/sql_results", skip=skip)
    export_powerbi_tables(con, root / "dashboard/powerbi_data")
    con.close()

    eda = run_eda(res.clean, root / "reports/figures", root / "reports/eda_summary.md",
                  quantities="increments" if source == "real" else "interval")
    (root / "reports/eda_findings.json").write_text(json.dumps(eda["findings"], indent=2, default=str), encoding="utf-8")
    return {"quality": res.report, "sql_queries": list(sql_results), "findings": eda["findings"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SOURCES), default="synthetic")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    out = run(a.source, a.root)
    q = out["quality"]
    print(f"[ok] source={a.source} brut={q['rows_raw']} propre={q['rows_clean']} "
          f"rejeté={q['rows_rejected']} doublons={q['rows_dropped_duplicates']} conservation={q['conservation_ok']}")
