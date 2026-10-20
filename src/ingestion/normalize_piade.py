"""Normalisation du format brut PIADE vers le schéma interne du pipeline.

Constats (diagnostic réalisé sur le vrai raw_data.csv, 429 394 lignes) :
* ``start`` / ``end`` : timestamps Unix en SECONDES (flottants) ; ``interval_start`` : ISO UTC.
* ``elapsed`` : MILLISECONDES (écart avec (end-start)*1000 <= 1 ms).
* ``pi`` / ``po`` : COMPTEURS CUMULÉS (quasi monotones). Les quantités par intervalle
  sont les variations entre deux lignes consécutives d'une même machine.
* Convention retenue : la variation est attribuée à la ligne COURANTE
  (valeur - valeur de la ligne précédente). Raison empirique : avec cette convention
  les lignes 'production' ont un débit médian ~3 900 paquets/h cohérent avec ``speed``
  (≈ 600/h avec la convention inverse). Les lignes d'arrêt reçoivent ~50 paquets par arrêt
  (résidu de fin de flux supposé) : à garder en tête pour toute analyse PAR ÉTAT.
* ``po`` dépasse ``pi`` sur ~15 % des lignes (décalage de comptage) : le taux de défauts
  n'est interprétable qu'agrégé, jamais ligne à ligne.
* Réinitialisations de compteur (variation < 0), variations après un trou de données
  > GAP_S et SAUTS implausibles (variation > JUMP_RATE_PER_H x durée + JUMP_SLACK, ex. un compteur
  qui passe de 0 à 3e8 d'un coup sur s_2) : variation mise à 0 et signalée
  (``flag_counter_reset`` / ``flag_counter_gap`` / ``flag_counter_jump``).
"""
from __future__ import annotations

import pandas as pd

GAP_S = 3600.0
# Cadence physique maximale observée ~6 500 paquets/h : une variation > 20 000/h (+ marge) est un saut de compteur.
JUMP_RATE_PER_H = 20_000.0
JUMP_SLACK = 5_000.0


def normalize_piade(raw: pd.DataFrame) -> pd.DataFrame:
    d = raw.copy()
    d["start"] = pd.to_datetime(d["start"], unit="s", utc=True).dt.tz_localize(None).dt.round("ms")
    d["end"] = pd.to_datetime(d["end"], unit="s", utc=True).dt.tz_localize(None).dt.round("ms")
    d["interval_start"] = pd.to_datetime(d["interval_start"], utc=True, format="ISO8601").dt.tz_localize(None)
    d["elapsed"] = d["elapsed"].astype("float64") / 1000.0
    d = d.sort_values(["equipment_ID", "start", "end"], kind="mergesort").reset_index(drop=True)

    g = d.groupby("equipment_ID")
    gap_s = (d["start"] - g["end"].shift(1)).dt.total_seconds()
    dpi, dpo = g["pi"].diff(), g["po"].diff()

    reset = (dpi < 0) | (dpo < 0)
    gap = gap_s.isna() | (gap_s > GAP_S)  # première ligne de machine ou trou de données
    bound = JUMP_RATE_PER_H * (d["elapsed"] / 3600.0) + JUMP_SLACK
    jump = (dpi > bound) | (dpo > bound)
    bad = reset | gap | jump
    d["flag_counter_jump"] = jump.fillna(False)
    d["flag_counter_reset"] = reset.fillna(False)
    d["flag_counter_gap"] = gap
    d["pi"] = dpi.where(~bad, 0).fillna(0).astype("int64")
    d["po"] = dpo.where(~bad, 0).fillna(0).astype("int64")
    return d
