# Dashboard Power BI — guide de construction

> **Statut honnête : aucun fichier `.pbix` n'a été généré.** Power BI Desktop n'est pas
> exécutable dans l'environnement où le projet a été construit (Linux, sans Windows).
> Ce dossier fournit tout ce qu'il faut pour le construire en ~1 h : tables prêtes à
> importer, mesures DAX, modèle, relations, spécification des 4 pages et checklist de recette.
> Les mesures DAX **n'ont pas été exécutées** : validez-les avec la checklist ci-dessous.

## 1. Données à importer

Dossier `dashboard/powerbi_data/` (généré par `python -m src.pipeline`) :

| Fichier | Rôle | Grain |
|---|---|---|
| `dim_date.csv` | Calendrier | 1 ligne / jour |
| `dim_machine.csv` | Machines + vitesse nominale empirique | 1 ligne / machine |
| `dim_state.csv` | États machine | 1 ligne / état |
| `dim_alarm.csv` | Codes d'alarme (`UNKNOWN` = manquante) | 1 ligne / alarme |
| `fact_state_interval.csv` | Intervalles d'état | 1 ligne / intervalle |
| `fact_production_daily.csv` | Agrégat machine x jour | 1 ligne / machine / jour |
| `fact_downtime.csv` | Événements d'arrêt | 1 ligne / arrêt |

Power Query : *Obtenir les données > Texte/CSV* pour chaque fichier. Types à corriger :
`dim_date[full_date]` → **Date** (puis *Marquer comme table de dates*), `date_key` / `*_key` →
Nombre entier, `start_ts`/`end_ts` → Date/Heure. Ajoutez une table vide `_Measures` et collez
`measures.dax` (une mesure à la fois).

## 2. Modèle et relations

```
dim_date ──1:*── fact_production_daily ──*:1── dim_machine ──1:*── fact_downtime ──*:1── dim_alarm
   │                                                  │
   └──1:*── fact_downtime        dim_state ──1:*── fact_state_interval ──*:1── dim_machine / dim_date
```

| De (1) | Vers (*) | Colonne | Filtrage |
|---|---|---|---|
| `dim_date` | `fact_production_daily`, `fact_downtime`, `fact_state_interval` | `date_key` | unique (dim → fait) |
| `dim_machine` | idem | `machine_key` | unique |
| `dim_alarm` | `fact_downtime` | `alarm_key` | unique |
| `dim_state` | `fact_state_interval` | `state_key` | unique |

Aucune relation bidirectionnelle (évite ambiguïtés et double comptage). Les 3 tables de faits
ne se filtrent qu'à travers les dimensions partagées ; ne **jamais** sommer `fact_state_interval`
et `fact_production_daily` dans un même visuel sans passer par une dimension.

## 3. Pages

**P1 — Executive Overview** : cartes `Output Units`, `Defect Rate`, `Downtime Hours`,
`Availability`, `OEE Proxy` (avec sous-titre « indicatif ») ; courbe `Output Units` + `Output 7D Avg`
par `dim_date[full_date]` ; barres `Downtime Hours` par machine ; carte texte `Attention Text` ;
bandeau `Data Disclaimer`. Segments : période (`dim_date`), machine.

**P2 — Machine Performance** : tableau classé (`Downtime Rank`, `Downtime Hours`, `Avg Downtime (min)`,
`Availability`, `Defect Rate`) ; barres empilées `Alarm Downtime Hours` par machine x alarme ;
Pareto (barres `Alarm Share` + ligne `Alarm Pareto Cum %`) ; comparaison `Downtime Hours` vs `Downtime Hours PM`.

**P3 — Quality Analytics** : barres `Defect Rate` par machine ; courbe `Defect Rate` par semaine
(`dim_date[week_start]`) par machine ; matrice machine x mois en mise en forme conditionnelle ;
info-bulle avec `Defect Units` et `Input Units`. *Pas de dimension produit ni de type de défaut dans les données.*

**P4 — Production Trends** : `Output Units` vs `Reference Capacity` par mois (**capacité de référence,
pas un objectif**) ; `Reference Attainment` par machine ; `Output MoM %` ; segment jour de semaine
(`dim_date[weekday]`) pour la saisonnalité hebdomadaire.

Navigation : boutons de page (Insertion > Boutons > Navigateur de pages). Unités : heures « h »,
taux en %, paquets en milliers. Un titre explicite par visuel et des info-bulles de page pour
afficher la formule du KPI.

## 4. Checklist de recette (à faire après import)

Comparer les valeurs Power BI (aucun filtre) aux sorties du pipeline :

| Mesure Power BI | Doit égaler |
|---|---|
| `Downtime Hours` par machine | `reports/sql_results/q01_downtime_ranking.csv` (`downtime_h`) |
| `Alarm Downtime Hours` par alarme | `reports/sql_results/q02_alarm_pareto.csv` (`downtime_h`) |
| `Availability` par machine | `data/processed/kpi_by_machine.csv` (`availability`) |
| `Defect Rate` par machine | idem (`defect_rate`) |
| `OEE Proxy` par machine | idem (`oee_proxy`) |

Tout écart > 0,01 % indique une relation ou un type de colonne incorrect.

## 5. Captures d'écran

À produire par vous après construction (`dashboard/screenshots/`). Aucune capture n'est fournie
car aucune n'a pu être réellement générée.
