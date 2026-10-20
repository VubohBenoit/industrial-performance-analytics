"""Générateur de données SYNTHÉTIQUES au schéma du dataset PIADE.

⚠️  Ces données sont SIMULÉES. Elles ne proviennent d'aucune entreprise réelle.

Pourquoi ce module existe
-------------------------
Le dataset réel visé (PIADE – Packaging Industry Anomaly DEtection, Univ. Padoue,
CC BY 4.0, DOI 10.5281/zenodo.7071746) n'était pas téléchargeable depuis
l'environnement où ce projet a été construit (hôtes bloqués par le proxy réseau).
Ce générateur reproduit le SCHÉMA de PIADE (mêmes colonnes, mêmes valeurs de
`type`) afin que tout le pipeline soit exécutable et testable. Pour travailler sur
les données réelles, il suffit de déposer le vrai ``raw_data.csv`` dans
``data/raw/`` et de relancer le pipeline avec ``--source real``.

Des anomalies de qualité sont volontairement injectées (doublons, durées
négatives, po > pi, alarmes manquantes...) pour exercer les règles de nettoyage.
Elles sont tracées dans ``data/raw/synthetic_injected_faults.json``.

Les « résultats » obtenus sur ces données reflètent les paramètres de simulation,
pas un phénomène industriel réel.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261018
N_DAYS = 180
START = pd.Timestamp("2025-01-06 00:00:00")  # un lundi

# Paramètres de simulation par machine (valeurs arbitraires, documentées).
MACHINES = {
    "s_1": dict(nominal_speed=1200, reject=0.012, p_down=0.10, p_perf=0.12, p_idle=0.06),
    "s_2": dict(nominal_speed=1000, reject=0.020, p_down=0.16, p_perf=0.10, p_idle=0.05),
    "s_3": dict(nominal_speed=1500, reject=0.008, p_down=0.08, p_perf=0.14, p_idle=0.08),
    "s_4": dict(nominal_speed=900, reject=0.030, p_down=0.22, p_perf=0.09, p_idle=0.04),
    "s_5": dict(nominal_speed=1100, reject=0.015, p_down=0.12, p_perf=0.11, p_idle=0.07),
}

# Alarmes : code -> (poids par machine, durée médiane en minutes)
ALARM_CODES = {
    "A_007": 14, "A_012": 9, "A_023": 35, "A_031": 6, "A_044": 22,
    "A_058": 11, "A_066": 48, "A_071": 5, "A_089": 17, "A_102": 28,
}
ALARM_WEIGHTS = {
    "s_1": [0.10, 0.20, 0.05, 0.25, 0.10, 0.10, 0.02, 0.10, 0.04, 0.04],
    "s_2": [0.05, 0.10, 0.30, 0.10, 0.10, 0.05, 0.10, 0.05, 0.05, 0.10],
    "s_3": [0.25, 0.20, 0.03, 0.20, 0.05, 0.10, 0.02, 0.10, 0.03, 0.02],
    "s_4": [0.05, 0.05, 0.10, 0.05, 0.10, 0.05, 0.35, 0.05, 0.05, 0.15],
    "s_5": [0.10, 0.10, 0.10, 0.10, 0.15, 0.10, 0.10, 0.10, 0.10, 0.05],
}


def _simulate_machine(machine: str, rng: np.random.Generator) -> list[dict]:
    p = MACHINES[machine]
    codes = list(ALARM_CODES)
    rows: list[dict] = []
    t = START
    end_of_sim = START + pd.Timedelta(days=N_DAYS)
    while t < end_of_sim:
        hour, weekday = t.hour, t.weekday()
        # Arrêt programmé : maintenance dimanche 02:00-06:00 + week-end partiel.
        if weekday == 6 and 2 <= hour < 6:
            kind = "scheduled_downtime"
        else:
            u = rng.random()
            if u < p["p_down"]:
                kind = "downtime"
            elif u < p["p_down"] + p["p_perf"]:
                kind = "performance_loss"
            elif u < p["p_down"] + p["p_perf"] + p["p_idle"]:
                kind = "idle"
            else:
                kind = "production"
        alarm = None
        if kind == "downtime":
            alarm = rng.choice(codes, p=ALARM_WEIGHTS[machine])
            median_min = ALARM_CODES[alarm]
            minutes = float(np.clip(rng.lognormal(np.log(median_min), 0.7), 1, 600))
        elif kind == "scheduled_downtime":
            minutes = 240.0 - (t.hour - 2) * 60 if t.hour >= 2 else 240.0
            minutes = max(minutes, 30.0)
        elif kind == "idle":
            minutes = float(np.clip(rng.lognormal(np.log(25), 0.6), 5, 240))
        elif kind == "performance_loss":
            minutes = float(np.clip(rng.lognormal(np.log(40), 0.5), 5, 240))
        else:
            minutes = float(np.clip(rng.lognormal(np.log(75), 0.55), 10, 480))
        seconds = int(minutes * 60)
        end = t + pd.Timedelta(seconds=seconds)
        hours = seconds / 3600
        pi = po = 0
        speed = 0.0
        if kind in ("production", "performance_loss"):
            factor = rng.normal(0.97, 0.03) if kind == "production" else rng.normal(0.65, 0.08)
            speed = float(max(p["nominal_speed"] * factor, 50))
            pi = int(speed * hours)
            # Taux de rebut plus élevé après une panne (effet simulé, pas un fait réel).
            rej = p["reject"] * (1.6 if rows and rows[-1]["type"] == "downtime" else 1.0)
            po = int(pi * (1 - np.clip(rng.normal(rej, rej * 0.3), 0, 0.5)))
        rows.append(dict(
            interval_start=t, equipment_ID=machine, alarm=alarm, type=kind,
            start=t, end=end, elapsed=seconds, pi=pi, po=po, speed=round(speed, 1),
        ))
        t = end
    return rows


def _inject_faults(df: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    faults: dict[str, int] = {}
    n = len(df)

    idx = rng.choice(n, size=12, replace=False)
    df.loc[idx, "end"] = df.loc[idx, "start"] - pd.Timedelta(seconds=30)
    faults["end_before_start"] = len(idx)

    prod = df.index[(df["type"] == "production") & (df["pi"] > 0)]
    idx = rng.choice(prod, size=15, replace=False)
    df.loc[idx, "po"] = df.loc[idx, "pi"] + 40
    faults["po_greater_than_pi"] = len(idx)

    dt = df.index[df["type"] == "downtime"]
    idx = rng.choice(dt, size=25, replace=False)
    df.loc[idx, "alarm"] = None
    faults["downtime_without_alarm"] = len(idx)

    idx = rng.choice(n, size=8, replace=False)
    df.loc[idx, "elapsed"] = df.loc[idx, "elapsed"] + 5000  # incohérence elapsed
    faults["elapsed_mismatch"] = len(idx)

    idx = rng.choice(prod, size=5, replace=False)
    df.loc[idx, "pi"] = -abs(df.loc[idx, "pi"])
    faults["negative_quantity"] = len(idx)

    idx = rng.choice(n, size=20, replace=False)
    df = pd.concat([df, df.loc[idx]], ignore_index=True)
    faults["exact_duplicates"] = len(idx)

    # Valeurs aberrantes plausibles mais extrêmes (à CONSERVER, seulement signalées).
    dt = df.index[(df["type"] == "downtime")]
    idx = rng.choice(dt, size=4, replace=False)
    df.loc[idx, "end"] = df.loc[idx, "start"] + pd.Timedelta(hours=40)
    df.loc[idx, "elapsed"] = 40 * 3600
    faults["very_long_downtime_kept_flagged"] = len(idx)
    return df, faults


def generate(out_dir: Path, seed: int = SEED) -> Path:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for m in MACHINES:
        rows.extend(_simulate_machine(m, rng))
    df = pd.DataFrame(rows)
    df, faults = _inject_faults(df, rng)
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)  # ordre brouillé
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "raw_data_synthetic.csv"
    df.to_csv(path, index=False)
    (out_dir / "synthetic_injected_faults.json").write_text(
        json.dumps({"seed": seed, "rows_total": len(df), "faults": faults}, indent=2)
    )
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default="data/raw")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    print(generate(Path(a.out_dir), a.seed))
