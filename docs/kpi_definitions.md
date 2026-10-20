# Définitions des KPI

Implémentation de référence : `src/transformations/kpi.py` (testée dans `tests/test_kpi.py`).
Équivalents SQL : `sql/kpi_queries.sql`. Équivalents DAX : `dashboard/measures.dax` (non exécutés).

## Temps de référence

| Terme | Définition | Unité |
|---|---|---|
| `run_h` | Heures en états `production` + `performance_loss` | h |
| `downtime_h` | Heures en état `downtime` (arrêt non planifié) | h |
| `scheduled_h` | Heures en `scheduled_downtime` | h |
| `idle_h` | Heures en `idle` (machine disponible, non chargée) | h |
| `loading_h` | `run_h + downtime_h` (temps de charge) | h |

**Choix de modélisation** : `idle` et `scheduled_downtime` sont exclus du temps de charge
(pas de demande / arrêt prévu). Si `idle` masque des pannes non déclarées, la disponibilité
est surestimée. La convention est discutable et doit être validée avec le métier.

## Indicateurs

| KPI | Formule | Unité | Dénominateur | Limites |
|---|---|---|---|---|
| Volume produit | Σ `po` (sorties) | paquets | — | Dépend de la définition de `po` |
| Volume entrant | Σ `pi` | paquets | — | |
| Volume défectueux | Σ max(`pi` − `po`, 0) | paquets | — | **Approximation** des rebuts : `pi − po` est supposé = paquets rejetés |
| Taux de défauts | défauts / `pi` | % | Σ `pi` | NaN si `pi` = 0 |
| Qualité | 1 − taux de défauts | % | idem | |
| Temps d'arrêt | `downtime_h` | h | — | Arrêts non planifiés uniquement |
| Durée moyenne d'arrêt | `downtime_h × 60 / n_arrêts` | min | nb d'événements `downtime` | Moyenne sensible aux arrêts longs : lire aussi médiane/P95 |
| Production / heure de marche | Σ `po` / `run_h` | paquets/h | `run_h` | |
| Disponibilité | `run_h / loading_h` | % | `loading_h` | Voir choix idle ci-dessus |
| Capacité de référence | vitesse nominale × `loading_h` | paquets | — | **Pas un objectif** : nominal = P95 empirique |
| Taux de réalisation de la référence | Σ `po` / capacité de référence | % | capacité de référence | Inférieur à 100 % par construction |
| Indice de performance (relatif) | Σ `pi` / (vitesse nominale × `run_h`) | ratio | vitesse nominale × `run_h` | **Pas la Performance OEE normative** : aucun cycle idéal validé |
| OEE proxy | Disponibilité × min(Indice perf ; 1) × Qualité | % | — | Proxy indicatif, non comparable à un TRS publié |

## Vitesse nominale

P95 de la colonne `speed` sur les intervalles `production`, par machine. C'est un choix
empirique : le jeu de données ne contient ni cadence théorique ni objectif de production.

## Redondance à connaître

Quand l'indice de performance est ≤ 1 : `OEE proxy = Disponibilité × Performance × Qualité
= (run/load) × (pi/(nom×run)) × (po/pi) = po / (nom × load)` = **taux de réalisation de la
référence**. Les deux indicateurs sont donc identiques par construction (vérifié dans
`tests/test_kpi.py::test_oee_proxy_equals_reference_attainment_when_performance_not_capped`) ;
ils ne constituent pas deux mesures indépendantes.

## Non calculés

* **OEE/TRS normatif** : exigerait temps planifié fiable et cycle idéal de référence.
* **Taux de réalisation d'un objectif** : aucune cible dans les données.
* **Défauts par produit ou par type** : ni produit ni type de défaut dans les données.

## Spécificités sur données réelles PIADE (compteurs cumulés)

* **« Taux de défauts » = écart entrées/sorties agrégé** (Σ pi − Σ po) / Σ pi sur variations de compteurs. Ce n'est **pas** un
  taux de rebut démontré : `po > pi` sur ~15 % des lignes, résidu d'environ 50 paquets sur les arrêts, définition de pi/po non vérifiée.
  À lire comme un indicateur relatif entre machines, à confirmer avec la documentation du jeu.
* **Indice de performance / OEE proxy** : la vitesse nominale est le P95 de la colonne `speed` par machine (4 500 à 6 500 paquets/h).
  Valeurs 0,59 à 0,82 sur ces données ; reste un indice **relatif**, pas un OEE normatif.
* **Disponibilité** : calculée sur le temps observé uniquement (trous de données exclus) ; `idle` et `scheduled_downtime` hors temps de charge.
* **Durées d'arrêt** : arrêts très courts (médiane ~1 min) ; la moyenne est tirée par une queue d'arrêts longs.
