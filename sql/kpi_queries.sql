-- Requêtes KPI. Chaque requête est introduite par "-- name: <identifiant>" et est
-- exécutée par src/transformations/warehouse.py (export CSV dans reports/sql_results/).
-- Toutes agrègent depuis les faits au grain adéquat : aucune jointure ne multiplie les mesures.

-- name: q01_downtime_ranking
-- Classement des machines par temps d'arrêt non planifié (RANK) et part du total.
WITH per_machine AS (
    SELECT m.machine_id,
           SUM(p.downtime_h)      AS downtime_h,
           SUM(p.downtime_events) AS downtime_events
    FROM fact_production_daily p
    JOIN dim_machine m ON m.machine_key = p.machine_key
    GROUP BY m.machine_id
)
SELECT machine_id,
       ROUND(downtime_h, 2)                                    AS downtime_h,
       downtime_events,
       ROUND(downtime_h * 60.0 / downtime_events, 2)           AS avg_downtime_min,
       ROUND(100.0 * downtime_h / SUM(downtime_h) OVER (), 2)  AS share_pct,
       RANK() OVER (ORDER BY downtime_h DESC)                  AS downtime_rank
FROM per_machine
ORDER BY downtime_rank;

-- name: q02_alarm_pareto
-- Pareto des causes d'arrêt (durée), avec cumul — fenêtre cumulative.
WITH per_alarm AS (
    SELECT a.alarm_code,
           COUNT(*)              AS events,
           SUM(d.duration_min)   AS downtime_min
    FROM fact_downtime d
    JOIN dim_alarm a ON a.alarm_key = d.alarm_key
    GROUP BY a.alarm_code
)
SELECT alarm_code,
       events,
       ROUND(downtime_min / 60.0, 2) AS downtime_h,
       ROUND(100.0 * downtime_min / SUM(downtime_min) OVER (), 2) AS share_pct,
       ROUND(100.0 * SUM(downtime_min) OVER (ORDER BY downtime_min DESC, alarm_code
                                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                    / SUM(downtime_min) OVER (), 2)               AS cum_share_pct
FROM per_alarm
ORDER BY downtime_min DESC, alarm_code;

-- name: q03_top_alarm_per_machine
-- Cause d'arrêt dominante par machine (ROW_NUMBER partitionné).
WITH ranked AS (
    SELECT m.machine_id, a.alarm_code,
           COUNT(*) AS events,
           SUM(d.duration_min) AS downtime_min,
           ROW_NUMBER() OVER (PARTITION BY m.machine_id ORDER BY SUM(d.duration_min) DESC) AS rn
    FROM fact_downtime d
    JOIN dim_machine m ON m.machine_key = d.machine_key
    JOIN dim_alarm a   ON a.alarm_key   = d.alarm_key
    GROUP BY m.machine_id, a.alarm_code
)
SELECT machine_id, alarm_code, events, ROUND(downtime_min / 60.0, 2) AS downtime_h
FROM ranked WHERE rn <= 2
ORDER BY machine_id, rn;

-- name: q04_weekly_defect_rate_wow
-- Taux de défauts hebdomadaire par machine et variation vs semaine précédente (LAG).
WITH weekly AS (
    SELECT m.machine_id, d.week_start,
           SUM(p.input_units)  AS input_units,
           SUM(p.defect_units) AS defect_units
    FROM fact_production_daily p
    JOIN dim_machine m ON m.machine_key = p.machine_key
    JOIN dim_date d    ON d.date_key    = p.date_key
    GROUP BY m.machine_id, d.week_start
    HAVING SUM(p.input_units) > 0
)
SELECT machine_id, week_start,
       ROUND(100.0 * defect_units / input_units, 3) AS defect_rate_pct,
       ROUND(100.0 * defect_units / input_units
             - 100.0 * LAG(defect_units) OVER w / LAG(input_units) OVER w, 3) AS wow_change_pts
FROM weekly
WINDOW w AS (PARTITION BY machine_id ORDER BY week_start)
ORDER BY machine_id, week_start;

-- name: q05_monthly_availability
-- Disponibilité = marche / (marche + arrêt non planifié), agrégation conditionnelle mensuelle.
SELECT m.machine_id, d.year_month,
       ROUND(SUM(p.production_h + p.perf_loss_h), 2) AS run_h,
       ROUND(SUM(p.downtime_h), 2)                   AS downtime_h,
       ROUND(100.0 * SUM(p.production_h + p.perf_loss_h)
             / NULLIF(SUM(p.production_h + p.perf_loss_h + p.downtime_h), 0), 2) AS availability_pct
FROM fact_production_daily p
JOIN dim_machine m ON m.machine_key = p.machine_key
JOIN dim_date d    ON d.date_key    = p.date_key
GROUP BY m.machine_id, d.year_month
ORDER BY m.machine_id, d.year_month;

-- name: q06_rolling_7d_output
-- Production (sorties) par jour et moyenne glissante 7 jours par machine (fenêtre ROWS).
SELECT m.machine_id, d.full_date, p.output_units,
       ROUND(AVG(p.output_units) OVER (
            PARTITION BY p.machine_key ORDER BY p.date_key
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) AS output_7d_avg
FROM fact_production_daily p
JOIN dim_machine m ON m.machine_key = p.machine_key
JOIN dim_date d    ON d.date_key    = p.date_key
ORDER BY m.machine_id, d.full_date;

-- name: q07_defects_after_downtime
-- Taux de défauts des intervalles de production selon l'état PRÉCÉDENT (LAG sur l'historique machine).
-- Association observée, pas une relation causale démontrée.
WITH seq AS (
    SELECT f.machine_key, s.state_name, f.input_units, f.output_units,
           LAG(s.state_name) OVER (PARTITION BY f.machine_key ORDER BY f.start_ts, f.interval_id) AS prev_state
    FROM fact_state_interval f
    JOIN dim_state s ON s.state_key = f.state_key
)
SELECT prev_state,
       COUNT(*)                                                    AS production_intervals,
       SUM(input_units)                                            AS input_units,
       ROUND(100.0 * SUM(input_units - output_units) / SUM(input_units), 3) AS defect_rate_pct
FROM seq
WHERE state_name = 'production' AND input_units > 0 AND prev_state IS NOT NULL
GROUP BY prev_state
ORDER BY defect_rate_pct DESC;

-- name: q09_defects_after_downtime_by_machine
-- Même comparaison STRATIFIÉE par machine : neutralise l'effet de composition
-- (les arrêts sont concentrés sur les machines qui rebutent déjà le plus).
WITH seq AS (
    SELECT f.machine_key, s.state_name, f.input_units, f.output_units,
           LAG(s.state_name) OVER (PARTITION BY f.machine_key ORDER BY f.start_ts, f.interval_id) AS prev_state
    FROM fact_state_interval f
    JOIN dim_state s ON s.state_key = f.state_key
), rates AS (
    SELECT machine_key,
           SUM(CASE WHEN prev_state = 'downtime'   THEN input_units - output_units END) * 1.0
             / SUM(CASE WHEN prev_state = 'downtime'   THEN input_units END) AS rate_after_downtime,
           SUM(CASE WHEN prev_state = 'production' THEN input_units - output_units END) * 1.0
             / SUM(CASE WHEN prev_state = 'production' THEN input_units END) AS rate_after_production
    FROM seq
    WHERE state_name = 'production' AND input_units > 0
    GROUP BY machine_key
)
SELECT m.machine_id,
       ROUND(100 * rate_after_downtime, 3)   AS defect_pct_after_downtime,
       ROUND(100 * rate_after_production, 3) AS defect_pct_after_production,
       ROUND(rate_after_downtime / rate_after_production, 2) AS ratio
FROM rates r JOIN dim_machine m ON m.machine_key = r.machine_key
ORDER BY m.machine_id;

-- name: q08_fanout_control
-- Contrôle anti double-comptage : les totaux d'un grain à l'autre doivent coïncider (diff = 0).
SELECT
    (SELECT SUM(input_units)  FROM fact_state_interval)   AS input_fact_interval,
    (SELECT SUM(input_units)  FROM fact_production_daily) AS input_fact_daily,
    (SELECT SUM(input_units)  FROM fact_production_daily p
        JOIN dim_machine m ON m.machine_key = p.machine_key
        JOIN dim_date d    ON d.date_key    = p.date_key) AS input_after_dim_joins,
    (SELECT COUNT(*) FROM fact_downtime)                  AS downtime_events_fact,
    (SELECT COUNT(*) FROM fact_state_interval f JOIN dim_state s ON s.state_key = f.state_key
        WHERE s.state_name = 'downtime')                  AS downtime_events_interval;
