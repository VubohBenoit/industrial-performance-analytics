"""KPI industriels : définitions, unités, dénominateurs, limites.

Temps de référence (par machine, sur une période) :
    run_h        = heures en états 'production' + 'performance_loss'
    downtime_h   = heures en état 'downtime' (arrêts non planifiés)
    scheduled_h  = heures en 'scheduled_downtime' (arrêts programmés)
    idle_h       = heures en 'idle' (machine disponible mais non chargée)
    loading_h    = run_h + downtime_h            (temps de charge)

Décisions de modélisation (à lire avant d'interpréter) :
* 'idle' est considéré comme manque de charge et n'entre PAS dans le temps de charge ;
  'scheduled_downtime' non plus. Choix discutable, documenté dans docs/kpi_definitions.md.
* Il n'existe pas de cycle idéal validé dans les données. La vitesse nominale est
  donc EMPIRIQUE (P95 de la vitesse en état 'production', par machine).
  => 'performance_index' est un indice RELATIF, pas la Performance OEE normative.
  => 'oee_proxy' est un proxy indicatif, à ne pas comparer à un TRS publié.
* Aucune quantité cible fournie : la « capacité de référence » = vitesse nominale x
  temps de charge n'est PAS un objectif de production.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RUN_STATES = ("production", "performance_loss")


def _safe_div(num, den):
    num = pd.Series(num, dtype="float64") if not isinstance(num, pd.Series) else num.astype("float64")
    den = pd.Series(den, dtype="float64") if not isinstance(den, pd.Series) else den.astype("float64")
    return num.div(den.where(den != 0))


def nominal_speed(clean: pd.DataFrame, quantile: float = 0.95) -> pd.Series:
    """Vitesse nominale empirique par machine (paquets/heure)."""
    prod = clean[(clean["type"] == "production") & (clean["speed"] > 0)]
    return prod.groupby("equipment_ID")["speed"].quantile(quantile).rename("nominal_speed")


def state_hours(clean: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Heures par état, en colonnes, pour un niveau d'agrégation donné."""
    p = clean.pivot_table(index=by, columns="type", values="hours", aggfunc="sum", fill_value=0.0)
    for s in ("production", "performance_loss", "downtime", "scheduled_downtime", "idle"):
        if s not in p.columns:
            p[s] = 0.0
    p = p.rename(columns={
        "production": "production_h", "performance_loss": "perf_loss_h",
        "downtime": "downtime_h", "scheduled_downtime": "scheduled_h", "idle": "idle_h",
    })
    p["run_h"] = p["production_h"] + p["perf_loss_h"]
    p["loading_h"] = p["run_h"] + p["downtime_h"]
    return p.reset_index()


def compute_kpis(clean: pd.DataFrame, by: list[str], nominal: pd.Series | None = None) -> pd.DataFrame:
    """KPI agrégés au niveau ``by`` (ex. ['equipment_ID'] ou ['equipment_ID', 'date'])."""
    nominal = nominal_speed(clean) if nominal is None else nominal
    hours = state_hours(clean, by)
    qty = clean.groupby(by, as_index=False).agg(
        input_units=("pi", "sum"), output_units=("po", "sum"),
        downtime_events=("type", lambda s: int((s == "downtime").sum())),
    )
    k = hours.merge(qty, on=by, how="outer")
    mach = k["equipment_ID"] if "equipment_ID" in k.columns else None
    if mach is not None:
        k["nominal_speed"] = mach.map(nominal)
    else:  # agrégation sans machine : moyenne pondérée par heures de run n'a pas de sens
        k["nominal_speed"] = np.nan
    k["defect_units"] = (k["input_units"] - k["output_units"]).clip(lower=0)
    k["defect_rate"] = _safe_div(k["defect_units"], k["input_units"])
    k["quality"] = 1 - k["defect_rate"]
    k["availability"] = _safe_div(k["run_h"], k["loading_h"])
    k["avg_downtime_min"] = _safe_div(k["downtime_h"] * 60, k["downtime_events"])
    k["output_per_run_hour"] = _safe_div(k["output_units"], k["run_h"])
    k["reference_capacity"] = k["nominal_speed"] * k["loading_h"]
    k["reference_attainment"] = _safe_div(k["output_units"], k["reference_capacity"])
    k["performance_index"] = _safe_div(k["input_units"], k["nominal_speed"] * k["run_h"])
    k["oee_proxy"] = k["availability"] * k["performance_index"].clip(upper=1.0) * k["quality"]
    return k


def pareto(df: pd.DataFrame, cat: str, value: str) -> pd.DataFrame:
    """Pareto : valeur par catégorie, part et cumul (ordre décroissant)."""
    g = df.groupby(cat, as_index=False)[value].sum().sort_values(value, ascending=False)
    total = g[value].sum()
    g["share"] = g[value] / total if total else np.nan
    g["cum_share"] = g["share"].cumsum()
    return g.reset_index(drop=True)
