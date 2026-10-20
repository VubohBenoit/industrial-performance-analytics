# Industrial Performance Analytics — Production, Quality & Downtime Intelligence

Pipeline analytique de bout en bout (Python · SQL · Power BI) pour comprendre les arrêts machine, les défauts et la disponibilité d'une ligne industrielle.

> **Données** : dataset industriel réel **PIADE** (Univ. Padoue, CC BY 4.0) — 5 machines d'emballage, 429 394 intervalles d'état, 2020-2022. Un jeu synthétique au même schéma sert aux tests et à une démo sans téléchargement.
>
> ⚠️ **Power BI** : aucun `.pbix` n'est fourni (Power BI Desktop indisponible lors de la construction). Les mesures DAX ([dashboard/measures.dax](dashboard/measures.dax)) n'ont **pas été exécutées** ; guide de construction et checklist de recette dans [dashboard/README.md](dashboard/README.md). Aucune capture d'écran n'est fournie.
>
> ⚠️ **Limites de lecture** : `pi`/`po` sont des compteurs cumulés ; l'« écart entrées/sorties » n'est pas un taux de rebut démontré, et l'indice de performance est relatif (voir [docs/data_sources.md](docs/data_sources.md)).

## Contexte et problématique

Une direction industrielle veut savoir : quelles machines s'arrêtent le plus, pour quelles causes, où le rebut est le plus élevé, comment évoluent production, qualité et disponibilité, et quoi investiguer en priorité.

## Architecture

```
data/raw (brut, intact) → src/ingestion → src/cleaning (R1–R10) → data/processed
        → src/transformations (SQLite étoile + sql/*.sql, KPI) → reports/ + dashboard/powerbi_data
        → src/analytics (7 figures commentées) ; tests/ (pytest) valide l'ensemble
```

Schémas détaillés (Mermaid) : [docs/architecture.md](docs/architecture.md). Dictionnaire des données : [docs/data_dictionary.md](docs/data_dictionary.md).

## Sources et licences

| Jeu | Usage | Licence |
|---|---|---|
| PIADE, Univ. Padoue, DOI 10.5281/zenodo.7071746 | **Analyse principale** (non versionné, à télécharger) | CC BY 4.0 (attribution requise) |
| Synthétique (`generate_synthetic.py`, graine fixe) | Tests et démo uniquement | MIT |

## Technologies

Python 3.11+, pandas, NumPy, matplotlib, SQLite (schéma portable PostgreSQL, non testé sur PostgreSQL), Jupyter, pytest, Power BI (DAX fourni, non validé). Docker volontairement absent : une seule dépendance runtime légère.

## Installation et lancement

```bash
git clone <votre-dépôt> && cd industrial-performance-analytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
curl -L -o data/raw/raw_data.csv https://researchdata.cab.unipd.it/1459/1/raw_data.csv
python -m src.pipeline --source real        # données PIADE (démo sans téléchargement : --source synthetic)
python -m pytest                            # 41 tests
python scripts/scenarios.py                 # estimations « what-if »
python scripts/build_notebook.py            # notebook exécuté
```

Le fichier brut n'est jamais modifié. Relire `reports/data_quality_report.json` après chaque exécution.

## KPI (détails : [docs/kpi_definitions.md](docs/kpi_definitions.md))

| KPI | Formule |
|---|---|
| Taux de défauts | Σ max(pi − po, 0) / Σ pi |
| Disponibilité | heures de marche / (marche + arrêts non planifiés) |
| Durée moyenne d'arrêt | heures d'arrêt × 60 / nb d'arrêts |
| Indice de performance (relatif) | Σ pi / (vitesse nominale P95 × heures de marche) |
| OEE proxy | Disponibilité × min(Performance relative, 1) × Qualité |

Limites : pas de cycle idéal ni d'objectif dans les données, donc **pas d'OEE normatif** ni de taux de réalisation d'objectif ; l'OEE proxy égale algébriquement le taux de réalisation de la capacité de référence (vérifié par test).

## Résultats observés (PIADE réel, 2020-2022)

Détail : [reports/eda_summary.md](reports/eda_summary.md) et [reports/business_recommendations.md](reports/business_recommendations.md).

- **3 147 h d'arrêt non planifié sur 92 084 arrêts.** s_1 en concentre 44 % (1 393 h), puis s_2 574 h, s_3 466 h, s_4 358 h, s_5 356 h.
- **Concentration des causes** : 4 alarmes sur 133 (A_065, A_101, A_006, A_001) expliquent environ 69 % des heures d'arrêt ; A_065 seule 27 %.
- **Micro-arrêts** : durée médiane d'un arrêt ≈ 1 min, P95 ≈ 7 min ; les 5 % d'arrêts les plus longs pèsent 43 % du temps d'arrêt.
- **Disponibilité** (temps observé) : de 75 % (s_2) à 94 % (s_5) ; creux de s_2 à 53 % en août 2020.
- **Écart entrées/sorties agrégé** : 0,24 % (s_3) à 0,69 % (s_4) — indicatif, voir limites.

Ce sont des associations descriptives ; aucune intervention n'a été réalisée et aucun gain n'est mesuré.

## Tests

41 tests : normalisation du format PIADE (dates, ms, compteurs, sauts), règles de nettoyage et conservation des lignes, KPI vérifiés à la main, cas limites (dénominateurs nuls), additivité des agrégats, concordance SQL ↔ Python, contraintes et clés étrangères, contrôle anti double-comptage, déterminisme du pipeline, intégrité du brut.

## Limites et pistes

Définition de `pi`/`po` non vérifiée ; pas de produit, d'équipe ni d'objectif ; couverture temporelle irrégulière ; convention `idle` hors temps de charge à valider ; PostgreSQL et Power BI non exécutés. Pistes : regroupement des 133 alarmes, vrai OEE avec cycle idéal, analyse de survie sur les pannes récurrentes, étude avant/après.

## Licence

MIT (code et données générées). Citer PIADE (CC BY 4.0) si le jeu réel est utilisé.
