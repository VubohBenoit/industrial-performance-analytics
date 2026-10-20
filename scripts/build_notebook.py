"""Construit et exécute notebooks/01_exploration.ipynb (sorties incluses)."""
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor
from pathlib import Path

import json
ROOT = Path(__file__).resolve().parents[1]
REPORT = json.loads((ROOT / "reports/data_quality_report.json").read_text())
SOURCE = REPORT.get("data_source", "synthetic")
MODE = REPORT.get("quantities_mode", "interval")
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
    md("# Exploration — Industrial Performance Analytics\n\n" + (
       "> Données réelles **PIADE** (Univ. Padoue, CC BY 4.0). `pi`/`po` sont des compteurs cumulés : l'écart entrées/sorties n'est qu'indicatif." if SOURCE == "real" else
       "> ⚠️ **Données synthétiques** (schéma PIADE). Les chiffres décrivent la simulation, pas une usine réelle.")),
    code("import sys, json\nfrom pathlib import Path\nROOT = Path.cwd().parent\nsys.path.insert(0, str(ROOT))\n"
         "import pandas as pd\nfrom IPython.display import Image, display\n"
         "from src.ingestion.load import load_raw\nfrom src.cleaning.clean import clean, profile_raw\n"
         "from src.transformations.kpi import compute_kpis\n"
         "pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)"),
    md("## 1. Chargement et profil du brut"),
    code("raw = load_raw(ROOT / 'data/raw', '" + SOURCE + "')\nprint(raw.shape)\nraw.head()"),
    code("p = profile_raw(raw)\nprint('doublons exacts :', p['exact_duplicates'])\npd.Series(p['missing'], name='manquants').to_frame().T"),
    code("raw['type'].value_counts()"),
    md("## 2. Nettoyage (règles R1–R10, voir `docs/cleaning_rules.md`)"),
    code("res = clean(raw, quantities='" + MODE + "')\npd.Series(res.report['rules'], name='lignes concernées').to_frame()"),
    code("print('conservation brut = propre + rejeté + doublons :', res.report['conservation_ok'])\n"
         "res.rejected['reject_reason'].value_counts()"),
    md("## 3. KPI par machine"),
    code("k = compute_kpis(res.clean, ['equipment_ID'])\n"
         "k[['equipment_ID','input_units','output_units','defect_rate','availability','avg_downtime_min','performance_index','oee_proxy']].round(4)"),
    md("Rappel : `performance_index` est **relatif** (vitesse nominale = P95 empirique) et `oee_proxy` "
       "égale algébriquement le taux de réalisation de la référence (voir `docs/kpi_definitions.md`)."),
    md("## 4. Figures commentées\nLe commentaire (question, méthode, résultat, limites) est dans `reports/eda_summary.md`."),
    code("for f in sorted((ROOT / 'reports/figures').glob('fig*.png')):\n    print(f.name)\n    display(Image(filename=str(f)))"),
]
if MODE == "interval":
    cells += [
        md("## 5. Effet de composition : rebut après arrêt"),
        code("pd.read_csv(ROOT / 'reports/sql_results/q07_defects_after_downtime.csv')"),
        code("pd.read_csv(ROOT / 'reports/sql_results/q09_defects_after_downtime_by_machine.csv')"),
        md("Le rapport global (≈ ×1,9) dépasse le rapport intra-machine (≈ ×1,6) parce que les arrêts sont "
           "plus fréquents sur les machines qui rebutent déjà le plus. Association observée, pas causalité démontrée."),
    
    ]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
ExecutePreprocessor(timeout=300, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT / "notebooks")}})
nbf.write(nb, ROOT / "notebooks/01_exploration.ipynb")
print("notebook exécuté :", ROOT / "notebooks/01_exploration.ipynb")
