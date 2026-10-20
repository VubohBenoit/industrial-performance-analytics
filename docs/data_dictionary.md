# Dictionnaire des données

## Brut (`data/raw/raw_data*.csv`, schéma PIADE)

| Colonne | Type | Description |
|---|---|---|
| `interval_start` | datetime | Début d'intervalle (identique à `start` dans le jeu synthétique) |
| `equipment_ID` | texte | Machine (`s_1`…`s_5`) |
| `alarm` | texte | Code d'alarme / raison d'arrêt (vide hors arrêt) |
| `type` | texte | `production`, `idle`, `downtime`, `performance_loss`, `scheduled_downtime` |
| `start`, `end` | datetime | Bornes de l'intervalle |
| `elapsed` | secondes | Durée de l'intervalle |
| `pi` | entier | Paquets en entrée |
| `po` | entier | Paquets en sortie |
| `speed` | réel | Vitesse (paquets/heure) |

## Propres (`data/processed/clean_intervals.csv`) — colonnes ajoutées

`raw_row_id` (traçabilité), `flag_elapsed_recomputed`, `flag_alarm_imputed`, `flag_overlap_prev`,
`flag_long_duration`, `hours` (= elapsed/3600), `date` (jour de début), `rejects` (= max(pi−po, 0)).

## Entrepôt (`data/processed/warehouse.db`, SQLite) et `dashboard/powerbi_data/`

| Table | Grain | Clé | Mesures / colonnes clés |
|---|---|---|---|
| `dim_date` | jour | `date_key` (AAAAMMJJ) | `full_date`, `year_month`, `iso_week`, `week_start`, `weekday`, `is_weekend` |
| `dim_machine` | machine | `machine_key` | `machine_id`, `nominal_speed` (P95 empirique) |
| `dim_state` | état | `state_key` | `state_name`, `is_run`, `is_loading` |
| `dim_alarm` | alarme | `alarm_key` | `alarm_code` (`UNKNOWN` = manquante) |
| `fact_state_interval` | intervalle | `interval_id` | `duration_s`, `input_units`, `output_units`, `speed`, `flag_long_duration` |
| `fact_production_daily` | machine × jour | (`machine_key`, `date_key`) | heures par état, `input_units`, `output_units`, `defect_units`, `downtime_events` |
| `fact_downtime` | arrêt | `interval_id` | `alarm_key`, `duration_min` |

Contraintes : durées ≥ 0, quantités ≥ 0, `output_units ≤ input_units`, `end_ts ≥ start_ts`,
clés étrangères actives. Convention : un intervalle est rattaché au **jour de son début**.

## Lacunes du schéma par rapport au cahier des charges

Pas de dimension produit ni de type de défaut (absents des données), pas de table de qualité
séparée (la qualité est portée par `fact_production_daily`), pas d'objectif de production.
