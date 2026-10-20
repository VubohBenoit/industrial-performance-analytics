-- Transformations : faits dérivés à partir de fact_state_interval.
-- COALESCE : SUM(CASE ...) renvoie NULL s'il n'y a aucune ligne de l'état -> 0 heure.
-- Chaque INSERT agrège AVANT toute jointure de dimension, pour éviter de multiplier
-- les mesures (fan-out). Les dimensions sont des relations N-1 sur clés uniques.

INSERT INTO fact_production_daily (
    machine_key, date_key, production_h, perf_loss_h, downtime_h, scheduled_h, idle_h,
    input_units, output_units, defect_units, downtime_events
)
SELECT
    f.machine_key,
    f.date_key,
    COALESCE(SUM(CASE WHEN s.state_name = 'production' THEN f.duration_s END), 0) / 3600.0,
    COALESCE(SUM(CASE WHEN s.state_name = 'performance_loss' THEN f.duration_s END), 0) / 3600.0,
    COALESCE(SUM(CASE WHEN s.state_name = 'downtime' THEN f.duration_s END), 0) / 3600.0,
    COALESCE(SUM(CASE WHEN s.state_name = 'scheduled_downtime' THEN f.duration_s END), 0) / 3600.0,
    COALESCE(SUM(CASE WHEN s.state_name = 'idle' THEN f.duration_s END), 0) / 3600.0,
    SUM(f.input_units),
    SUM(f.output_units),
    SUM(f.input_units - f.output_units),
    SUM(CASE WHEN s.state_name = 'downtime' THEN 1 ELSE 0 END)
FROM fact_state_interval f
JOIN dim_state s ON s.state_key = f.state_key
GROUP BY f.machine_key, f.date_key;

INSERT INTO fact_downtime (interval_id, machine_key, date_key, alarm_key, start_ts, duration_min)
SELECT f.interval_id, f.machine_key, f.date_key, f.alarm_key, f.start_ts, f.duration_s / 60.0
FROM fact_state_interval f
JOIN dim_state s ON s.state_key = f.state_key
WHERE s.state_name = 'downtime' AND f.alarm_key IS NOT NULL;
