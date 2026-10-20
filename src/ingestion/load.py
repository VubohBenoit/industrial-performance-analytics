"""Chargement des données brutes (lecture seule : le brut n'est jamais modifié)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.normalize_piade import normalize_piade

RAW_COLUMNS = [
    "interval_start", "equipment_ID", "alarm", "type",
    "start", "end", "elapsed", "pi", "po", "speed",
]
SOURCES = {
    "synthetic": "raw_data_synthetic.csv",
    "real": "raw_data.csv",  # PIADE, à déposer manuellement dans data/raw/
}


def load_raw(raw_dir: Path | str = "data/raw", source: str = "synthetic") -> pd.DataFrame:
    """Charge le CSV brut tel quel (chaînes pour les dates, pas de correction)."""
    path = Path(raw_dir) / SOURCES[source]
    if not path.exists():
        hint = (
            "Générez-les avec `python -m src.ingestion.generate_synthetic`."
            if source == "synthetic"
            else "Téléchargez raw_data.csv (PIADE, DOI 10.5281/zenodo.7071746, CC BY 4.0) "
                 "et placez-le dans data/raw/."
        )
        raise FileNotFoundError(f"Fichier introuvable : {path}. {hint}")
    df = pd.read_csv(path, dtype={"equipment_ID": "string", "alarm": "string", "type": "string"})
    if source == "real":
        # le brut PIADE est rechargé tel quel ; la conversion se fait dans normalize_piade (le fichier n'est jamais modifié)
        pass
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path.name} : {sorted(missing)}")
    if source == "real":
        df = normalize_piade(df)  # dates Unix, elapsed en ms, compteurs cumulés -> variations
        extra = [c for c in ("flag_counter_reset", "flag_counter_gap", "flag_counter_jump") if c in df.columns]
        return df[RAW_COLUMNS + extra].copy()
    return df[RAW_COLUMNS].copy()
