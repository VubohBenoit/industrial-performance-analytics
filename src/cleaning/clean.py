"""Règles de nettoyage et rapport de qualité.

Principes
---------
* Le brut n'est jamais modifié ; on travaille sur une copie.
* Rien n'est supprimé silencieusement : toute ligne écartée va dans une table de
  quarantaine avec la raison (``reject_reason``).
* Une valeur atypique mais plausible (ex. arrêt très long) est CONSERVÉE et
  seulement signalée (``flag_long_duration``).

Règles (voir aussi docs/cleaning_rules.md)
------------------------------------------
R1  Doublons exacts            -> supprimés (une copie conservée), comptés.
R2  Type inconnu / nul         -> quarantaine.
R3  Dates non parsables        -> quarantaine.
R4  end < start (durée < 0)    -> quarantaine (durée impossible).
R5  elapsed incohérent         -> ``elapsed`` recalculé depuis end-start, signalé.
R6  pi/po négatifs             -> quarantaine.
R7  po > pi (production)       -> quarantaine (sorties > entrées impossibles).
R8  downtime sans alarme       -> alarm = 'UNKNOWN' (imputation explicite), signalé.
R9  Chevauchement intra-machine-> signalé seulement.
R10 Durée extrême (Tukey 1.5xIQR sur log-durée, par type) -> signalé seulement, conservé.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

VALID_TYPES = {"production", "idle", "downtime", "performance_loss", "scheduled_downtime"}
ELAPSED_TOLERANCE_S = 2.0


@dataclass
class CleaningResult:
    clean: pd.DataFrame
    rejected: pd.DataFrame
    report: dict = field(default_factory=dict)


def _reject(df: pd.DataFrame, mask: pd.Series, reason: str, bucket: list[pd.DataFrame]) -> pd.DataFrame:
    if mask.any():
        bad = df[mask].copy()
        bad["reject_reason"] = reason
        bucket.append(bad)
    return df[~mask]


def profile_raw(raw: pd.DataFrame) -> dict:
    """Instantané descriptif du brut (dimensions, types, manquants)."""
    return {
        "rows": int(len(raw)),
        "columns": list(raw.columns),
        "dtypes": {c: str(t) for c, t in raw.dtypes.items()},
        "missing": {c: int(v) for c, v in raw.isna().sum().items()},
        "exact_duplicates": int(raw.duplicated().sum()),
        "machines": sorted(raw["equipment_ID"].dropna().unique().tolist()),
        "types": raw["type"].value_counts(dropna=False).to_dict(),
    }


def clean(raw: pd.DataFrame, quantities: str = "interval") -> CleaningResult:
    """quantities="interval" : pi/po par intervalle (po > pi est impossible -> R7 rejette).
    quantities="increments" : variations de compteurs cumulés (po > pi possible par décalage -> R7 signale seulement)."""
    rejected: list[pd.DataFrame] = []
    report: dict = {"rows_raw": int(len(raw)), "profile_raw": profile_raw(raw), "rules": {}}
    df = raw.copy()
    df["raw_row_id"] = np.arange(len(df))  # traçabilité vers le brut

    # R1 doublons exacts (hors identifiant de traçabilité)
    dup_mask = df.duplicated(subset=[c for c in df.columns if c != "raw_row_id"], keep="first")
    report["rules"]["R1_exact_duplicates_dropped"] = int(dup_mask.sum())
    df = df[~dup_mask]

    # R1b doublons « conflictuels » : même machine/début/fin/état mais valeurs différentes -> 1re gardée
    n0 = len(df)
    key = ["equipment_ID", "start", "end", "type"]
    df = _reject(df, df.duplicated(subset=key, keep="first"), "R1b_conflicting_duplicate", rejected)
    report["rules"]["R1b_conflicting_duplicate"] = n0 - len(df)

    # Normalisation légère
    df["type"] = df["type"].str.strip().str.lower()
    df["equipment_ID"] = df["equipment_ID"].str.strip()
    df["alarm"] = df["alarm"].str.strip().replace({"": pd.NA})

    # R2 type
    n0 = len(df)
    df = _reject(df, ~df["type"].isin(VALID_TYPES), "R2_unknown_type", rejected)
    report["rules"]["R2_unknown_type"] = n0 - len(df)

    # R3 dates
    for c in ("interval_start", "start", "end"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    n0 = len(df)
    df = _reject(df, df[["start", "end"]].isna().any(axis=1) | df["equipment_ID"].isna(),
                 "R3_unparsable_date_or_missing_machine", rejected)
    report["rules"]["R3_unparsable_date_or_missing_machine"] = n0 - len(df)

    # R4 durée négative
    n0 = len(df)
    df = _reject(df, df["end"] < df["start"], "R4_end_before_start", rejected)
    report["rules"]["R4_end_before_start"] = n0 - len(df)

    # R6 quantités négatives
    n0 = len(df)
    df = _reject(df, (df["pi"] < 0) | (df["po"] < 0), "R6_negative_quantity", rejected)
    report["rules"]["R6_negative_quantity"] = n0 - len(df)

    # R7 po > pi
    n0 = len(df)
    if quantities == "interval":
        df = _reject(df, df["po"] > df["pi"], "R7_output_greater_than_input", rejected)
        report["rules"]["R7_output_greater_than_input"] = n0 - len(df)
    else:  # compteurs cumulés : décalage de comptage normal, signalé et conservé
        report["rules"]["R7_po_gt_pi_flagged_kept"] = int((df["po"] > df["pi"]).sum())

    df = df.copy()
    # R5 elapsed recalculé
    recomputed = (df["end"] - df["start"]).dt.total_seconds()
    mismatch = (df["elapsed"] - recomputed).abs() > ELAPSED_TOLERANCE_S
    df["flag_elapsed_recomputed"] = mismatch
    df["elapsed"] = recomputed
    report["rules"]["R5_elapsed_recomputed"] = int(mismatch.sum())

    # R8 alarme manquante sur arrêt
    miss = (df["type"] == "downtime") & df["alarm"].isna()
    df.loc[miss, "alarm"] = "UNKNOWN"
    df["flag_alarm_imputed"] = miss
    report["rules"]["R8_downtime_alarm_set_unknown"] = int(miss.sum())

    # R9 chevauchements intra-machine (signalement)
    df = df.sort_values(["equipment_ID", "start", "end"]).reset_index(drop=True)
    prev_end = df.groupby("equipment_ID")["end"].shift(1)
    df["flag_overlap_prev"] = prev_end.notna() & (df["start"] < prev_end - pd.Timedelta(seconds=1))
    report["rules"]["R9_overlap_flagged"] = int(df["flag_overlap_prev"].sum())

    # R10 durées extrêmes par type (Tukey sur log-durée, borne haute 1.5 x IQR).
    # Signalement uniquement : un arrêt long peut être réel et est précisément ce qu'on veut analyser.
    df["flag_long_duration"] = False
    for t, g in df.groupby("type"):
        x = np.log1p(g["elapsed"].clip(lower=0))
        q1, q3 = x.quantile([0.25, 0.75])
        hi = q3 + 1.5 * (q3 - q1)
        df.loc[g.index, "flag_long_duration"] = x > hi
    report["rules"]["R10_long_duration_flagged_kept"] = int(df["flag_long_duration"].sum())

    # Colonnes dérivées de base
    df["hours"] = df["elapsed"] / 3600.0
    df["date"] = df["start"].dt.normalize()
    df["flag_po_gt_pi"] = df["po"] > df["pi"]
    # En mode compteurs, pi - po n'est pas borné à 0 par ligne (sinon biais haussier) : seul l'agrégat a un sens.
    df["rejects"] = (df["pi"] - df["po"]) if quantities == "increments" else (df["pi"] - df["po"]).clip(lower=0)

    rej = pd.concat(rejected, ignore_index=True) if rejected else pd.DataFrame(columns=list(raw.columns) + ["reject_reason"])
    report["quantities_mode"] = quantities
    report["rows_clean"] = int(len(df))
    report["rows_rejected"] = int(len(rej))
    report["rows_dropped_duplicates"] = report["rules"]["R1_exact_duplicates_dropped"]
    # Équation de conservation : brut = propre + rejeté + doublons
    report["conservation_ok"] = bool(
        report["rows_raw"] == report["rows_clean"] + report["rows_rejected"] + report["rows_dropped_duplicates"]
    )
    report["date_range"] = [str(df["start"].min()), str(df["end"].max())]
    report["machines"] = sorted(df["equipment_ID"].unique().tolist())
    return CleaningResult(clean=df, rejected=rej, report=report)
