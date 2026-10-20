-- Schéma en étoile — Industrial Performance Analytics
-- Dialecte : SQLite 3.35+ (exécuté localement par src/transformations/warehouse.py).
-- Portabilité PostgreSQL : remplacer TEXT/REAL/INTEGER par VARCHAR/DOUBLE PRECISION/BIGINT,
-- DATE pour les dates ; les contraintes CHECK/FK et les requêtes de fenêtrage sont compatibles.
--
-- Granularité des faits :
--   fact_state_interval : 1 ligne = 1 intervalle d'état machine (grain le plus fin)
--   fact_production_daily : 1 ligne = 1 machine x 1 jour (agrégat dérivé, voir transformations.sql)
--   fact_downtime : 1 ligne = 1 événement d'arrêt non planifié (état 'downtime')
-- Convention : un intervalle est rattaché au JOUR DE SON DÉBUT (pas de découpage à minuit).

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_downtime;
DROP TABLE IF EXISTS fact_production_daily;
DROP TABLE IF EXISTS fact_state_interval;
DROP TABLE IF EXISTS dim_alarm;
DROP TABLE IF EXISTS dim_state;
DROP TABLE IF EXISTS dim_machine;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key     INTEGER PRIMARY KEY,           -- AAAAMMJJ
    full_date    TEXT    NOT NULL UNIQUE,       -- ISO AAAA-MM-JJ
    year         INTEGER NOT NULL,
    month        INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    year_month   TEXT    NOT NULL,              -- AAAA-MM
    iso_week     INTEGER NOT NULL CHECK (iso_week BETWEEN 1 AND 53),
    week_start   TEXT    NOT NULL,              -- lundi de la semaine
    weekday      INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),  -- 0 = lundi
    is_weekend   INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

CREATE TABLE dim_machine (
    machine_key   INTEGER PRIMARY KEY,
    machine_id    TEXT NOT NULL UNIQUE,
    nominal_speed REAL CHECK (nominal_speed > 0)  -- empirique : P95 vitesse en 'production' (paquets/h)
);

CREATE TABLE dim_state (
    state_key   INTEGER PRIMARY KEY,
    state_name  TEXT NOT NULL UNIQUE,
    is_run      INTEGER NOT NULL CHECK (is_run IN (0, 1)),      -- compte dans le temps de marche
    is_loading  INTEGER NOT NULL CHECK (is_loading IN (0, 1))   -- compte dans le temps de charge
);

CREATE TABLE dim_alarm (
    alarm_key  INTEGER PRIMARY KEY,
    alarm_code TEXT NOT NULL UNIQUE                              -- 'UNKNOWN' = alarme absente (règle R8)
);

CREATE TABLE fact_state_interval (
    interval_id  INTEGER PRIMARY KEY,
    machine_key  INTEGER NOT NULL REFERENCES dim_machine (machine_key),
    date_key     INTEGER NOT NULL REFERENCES dim_date (date_key),
    state_key    INTEGER NOT NULL REFERENCES dim_state (state_key),
    alarm_key    INTEGER REFERENCES dim_alarm (alarm_key),
    start_ts     TEXT NOT NULL,
    end_ts       TEXT NOT NULL,
    duration_s   REAL NOT NULL CHECK (duration_s >= 0),
    input_units  INTEGER NOT NULL CHECK (input_units >= 0),
    output_units INTEGER NOT NULL CHECK (output_units >= 0),  -- po <= pi vérifié au nettoyage (mode interval), pas ici
    speed        REAL CHECK (speed >= 0),
    flag_long_duration INTEGER NOT NULL DEFAULT 0 CHECK (flag_long_duration IN (0, 1)),
    CHECK (end_ts >= start_ts),
    UNIQUE (machine_key, start_ts, end_ts, state_key)
);
CREATE INDEX ix_fsi_machine_date ON fact_state_interval (machine_key, date_key);
CREATE INDEX ix_fsi_state ON fact_state_interval (state_key);

CREATE TABLE fact_production_daily (
    machine_key    INTEGER NOT NULL REFERENCES dim_machine (machine_key),
    date_key       INTEGER NOT NULL REFERENCES dim_date (date_key),
    production_h   REAL NOT NULL,
    perf_loss_h    REAL NOT NULL,
    downtime_h     REAL NOT NULL,
    scheduled_h    REAL NOT NULL,
    idle_h         REAL NOT NULL,
    input_units    INTEGER NOT NULL,
    output_units   INTEGER NOT NULL,
    defect_units   INTEGER NOT NULL,  -- signé : sur compteurs réels un jour peut avoir po > pi (décalage)
    downtime_events INTEGER NOT NULL,
    PRIMARY KEY (machine_key, date_key)
);

CREATE TABLE fact_downtime (
    interval_id  INTEGER PRIMARY KEY REFERENCES fact_state_interval (interval_id),
    machine_key  INTEGER NOT NULL REFERENCES dim_machine (machine_key),
    date_key     INTEGER NOT NULL REFERENCES dim_date (date_key),
    alarm_key    INTEGER NOT NULL REFERENCES dim_alarm (alarm_key),
    start_ts     TEXT NOT NULL,
    duration_min REAL NOT NULL CHECK (duration_min >= 0)
);
