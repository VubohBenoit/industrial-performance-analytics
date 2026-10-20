# Sources de données et licences

## 1. Jeu principal : PIADE (réel)

* *PIADE — Packaging Industry Anomaly DEtection dataset*, D. Tosato, E. Convento, C. Masiero,
  G. A. Susto, A. Beghi, Université de Padoue (2022).
* DOI : 10.5281/zenodo.7071746 — https://researchdata.cab.unipd.it/1459/
* Licence : **CC BY 4.0** (attribution obligatoire).
* Fichier utilisé : `raw_data.csv` (429 394 lignes, 5 machines d'emballage `s_1`…`s_5`, 133 codes d'alarme,
  2020-01-01 → 2022-01-02). **Non versionné dans Git** (ignoré, 47 Mo) : à télécharger depuis la source.
* Citation à reprendre dans toute publication : Tosato et al., PIADE, Univ. Padoue, 2022, CC BY 4.0.

### Particularités du format (constatées sur le fichier réel, voir `src/ingestion/normalize_piade.py`)

| Colonne | Contenu réel |
|---|---|
| `start`, `end` | timestamps Unix en secondes (flottants) |
| `elapsed` | millisecondes |
| `pi`, `po` | **compteurs cumulés** (dizaines de millions), pas des quantités par intervalle |
| `alarm` | `A_000` hors arrêt ; code d'alarme sur les lignes `downtime` |
| `speed` | cadence (paquets/h), 0 sur ~4 % des lignes |

Traitements : dates converties (UTC), `elapsed` / 1000, `pi`/`po` différenciés par machine (variation attribuée à la
ligne courante). Variations mises à 0 et **signalées, jamais supprimées** : remises à zéro de compteur
(86), premières lignes et trous de données > 1 h (1 371), **sauts implausibles** (185, ex. compteur de s_2 passant de ~0 à ~3·10⁸).

### Limites établies sur ces données

* `po` > `pi` sur ~15 % des lignes (décalage de comptage) : `pi − po` n'a de sens qu'**agrégé**, jamais ligne à ligne.
* Les lignes d'arrêt reçoivent environ 50 paquets chacune (résidu supposé) : **toute analyse par état est biaisée**.
  L'analyse « rebut après arrêt » a donc été retirée du mode réel.
* La définition exacte de `pi`/`po` (et donc le sens de « défaut ») n'a pas été vérifiée dans la documentation du jeu.
* Couverture temporelle irrégulière (1 371 trous > 1 h) : les agrégats portent sur le temps **observé**.
* Pas de produit, d'équipe ni d'objectif de production.

## 2. Jeu synthétique (démonstration et tests uniquement)

* Généré par `src/ingestion/generate_synthetic.py` (graine fixe), même schéma que PIADE, quantités par intervalle.
* **Aucune donnée d'entreprise réelle.** Anomalies injectées (`synthetic_injected_faults.json`) pour tester les règles de nettoyage.
* Sert aux tests automatisés et à une démonstration sans téléchargement (`--source synthetic`).
* Licence : MIT. **Ne jamais présenter ses résultats comme réels.**

## Reproduire avec les données réelles

```bash
curl -L -o data/raw/raw_data.csv https://researchdata.cab.unipd.it/1459/1/raw_data.csv
python -m src.pipeline --source real
```
