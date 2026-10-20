# Architecture

```mermaid
flowchart LR
    A[data/raw<br/>CSV brut, jamais modifié] --> B[src/ingestion/load.py]
    G[generate_synthetic.py<br/>données simulées] --> A
    B --> C[src/cleaning/clean.py<br/>règles R1-R10]
    C --> D[(data/processed<br/>clean_intervals.csv<br/>rejected_rows.csv)]
    C --> Q[reports/data_quality_report.json]
    D --> E[src/transformations/warehouse.py<br/>SQLite étoile + sql/*.sql]
    D --> K[src/transformations/kpi.py]
    E --> R[reports/sql_results/*.csv]
    E --> P[dashboard/powerbi_data/*.csv]
    K --> F[src/analytics/eda.py<br/>figures + eda_summary.md]
    P --> PBI[Power BI Desktop<br/>mesures DAX, à construire]
    T[tests/ pytest] -. valide .-> C & K & E
```

Orchestration : `python -m src.pipeline` (≈ 5 s sur 18 000 lignes).

## Modèle en étoile

```mermaid
erDiagram
    dim_date ||--o{ fact_state_interval : date_key
    dim_machine ||--o{ fact_state_interval : machine_key
    dim_state ||--o{ fact_state_interval : state_key
    dim_alarm ||--o{ fact_state_interval : alarm_key
    dim_date ||--o{ fact_production_daily : date_key
    dim_machine ||--o{ fact_production_daily : machine_key
    dim_date ||--o{ fact_downtime : date_key
    dim_machine ||--o{ fact_downtime : machine_key
    dim_alarm ||--o{ fact_downtime : alarm_key
    fact_state_interval ||--o| fact_downtime : interval_id
```

`fact_production_daily` et `fact_downtime` sont dérivés de `fact_state_interval` par `sql/transformations.sql`.

## Choix techniques

* **SQLite** plutôt que PostgreSQL : zéro installation, reproductible en CI ; schéma portable (voir en-tête de `sql/schema.sql`). PostgreSQL non exécuté.
* **Pas de Docker** : une seule dépendance runtime (Python + 3 bibliothèques), Docker n'apporterait pas de reproductibilité supplémentaire ici.
* **CSV** plutôt que Parquet : évite une dépendance (`pyarrow`) pour 3 Mo de données.
