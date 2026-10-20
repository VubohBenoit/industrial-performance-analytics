# Règles de nettoyage

Implémentation : `src/cleaning/clean.py` (testée dans `tests/test_cleaning.py`).

**Principes** : le brut n'est jamais modifié ; aucune ligne n'est supprimée silencieusement
(`data/processed/rejected_rows.csv` + `reject_reason`) ; une valeur atypique mais plausible est
conservée et signalée ; équation de conservation vérifiée : `brut = propre + rejeté + doublons`.

| ID | Condition | Action | Justification |
|---|---|---|---|
| R1 | Ligne strictement identique | Supprimée (1 copie gardée), comptée | Une double extraction n'est pas deux événements |
| R2 | `type` absent des 5 états connus | Quarantaine | État non interprétable |
| R3 | Date non parsable / machine absente | Quarantaine | Ligne non rattachable |
| R4 | `end < start` | Quarantaine | Durée négative impossible ; correction arbitraire non justifiable |
| R5 | `elapsed` ≠ `end − start` (> 2 s) | `elapsed` recalculé, ligne signalée | Les horodatages font foi |
| R6 | `pi` ou `po` < 0 | Quarantaine | Quantité impossible |
| R7 | `po > pi` | Quarantaine | Sorties supérieures aux entrées, défaut négatif sans sens |
| R8 | `downtime` sans alarme | `alarm = 'UNKNOWN'`, signalé | Conserve la durée d'arrêt ; cause explicitement inconnue |
| R9 | Chevauchement avec l'intervalle précédent de la machine | Signalé seulement | À investiguer, non corrigé |
| R10 | Durée extrême (Tukey 1,5×IQR sur log-durée, par type) | Signalé seulement, **conservé** | Un arrêt très long est peut-être réel et important |

Rapport chiffré : `reports/data_quality_report.json`.
Sur les données synthétiques, les anomalies injectées sont listées dans
`data/raw/synthetic_injected_faults.json` et toutes retrouvées (`test_synthetic_injected_faults_are_all_caught`).

**Limite** : sur données réelles, R7 pourrait supprimer des lignes légitimes si `po` et `pi` sont
mesurés par des capteurs désynchronisés ; examiner `rejected_rows.csv` avant de conclure.
