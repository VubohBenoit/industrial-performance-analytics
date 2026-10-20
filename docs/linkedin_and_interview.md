# Contenu de présentation (LinkedIn / entretiens)

> À relire et adapter. Projet personnel sur données publiques (PIADE, CC BY 4.0) : aucune expérience professionnelle ni
> gain financier n'est revendiqué, et aucune intervention n'a été réalisée.

## 1. Description courte (section Projets)

Pipeline de data analysis industrielle de bout en bout sur le dataset public PIADE (5 machines d'emballage, 429 000 intervalles) :
normalisation d'un format brut piégeux (compteurs cumulés, sauts de capteur), nettoyage traçable (aucune ligne supprimée en
silence), entrepôt SQL en étoile, KPI documentés avec leurs limites, 41 tests pytest et spécification de dashboard Power BI.
Python · pandas · SQL · pytest · Power BI (DAX).

## 2. Post LinkedIn (FR)

J'ai analysé 2 ans de données d'une ligne d'emballage industrielle (dataset public PIADE, 5 machines, 429 000 intervalles
d'état), et ce qui m'a le plus appris, c'est le nettoyage.

🎯 Question : quelles machines s'arrêtent le plus, pour quelles causes, et que faut-il investiguer en premier ?

🧪 Le piège : les compteurs de production sont cumulés, pas par intervalle. Traités naïvement, un saut de compteur sur une
machine donnait 201 000 unités par heure de marche, contre ~4 000 pour les autres. J'ai ajouté des règles de plausibilité :
les valeurs douteuses sont neutralisées et signalées, jamais supprimées en silence.

🔍 Ce que montrent les données (descriptif, sans intervention) :
• 2 machines sur 5 concentrent 62 % des 3 147 h d'arrêt
• une seule alarme pèse 27 % du temps d'arrêt du parc, sur une seule machine
• les pertes sont surtout des micro-arrêts (durée médiane ≈ 1 min) avec une queue longue : les 5 % d'arrêts les plus longs pèsent 43 % du temps perdu
• le classement des 3 dernières machines change quand on retire les arrêts atypiques : je ne l'ai pas retenu comme constat

🛠️ 41 tests automatisés, entrepôt SQL en étoile avec contrôles anti double-comptage, KPI documentés avec leurs limites.

⚠️ Limites assumées : pas d'OEE normatif (aucun cycle idéal dans les données), « écart entrées/sorties » non validé comme taux de rebut, aucun gain revendiqué. Le dashboard Power BI est spécifié (DAX, modèle) mais pas encore construit.

Code : github.com/VubohBenoit/industrial-performance-analytics
Données : PIADE, Univ. Padoue (CC BY 4.0)

#DataAnalysis #Python #SQL #PowerBI #Industrie40 #DataQuality

## 3. English summary

**Industrial Performance Analytics** — an end-to-end pipeline (Python, SQL, Power BI spec) on the public PIADE dataset (Univ. of Padua, CC BY 4.0: 5 packaging machines, 429k state intervals, 2020–2022). The raw file uses cumulative counters, millisecond durations and Unix timestamps; a normaliser differences the counters per machine and neutralises resets, data gaps and implausible jumps (flagged, never silently dropped). A star schema (SQLite) feeds documented KPIs (availability, aggregated input/output gap, relative performance index). 41 pytest tests cover the normaliser, cleaning rules, hand-checked KPIs, SQL-vs-Python reconciliation and fan-out controls. Findings are descriptive: two machines carry 62% of 3,147 h of unplanned downtime, one alarm on one machine accounts for 27% of fleet downtime, and losses are dominated by micro-stops with a heavy tail. Limits: no normative OEE (no ideal cycle), input/output gap not validated as a scrap rate, no intervention or measured gain. The Power BI report is specified (DAX, model, acceptance checklist) but not built.

## 4. Compétences démontrées

Python (pandas, NumPy, matplotlib) · ingestion et normalisation de données industrielles brutes · détection d'anomalies de capteurs · nettoyage traçable · modélisation dimensionnelle · SQL (CTE, fenêtrage LAG/RANK/ROWS, agrégations conditionnelles) · conception de KPI industriels (disponibilité, OEE) · tests de robustesse et sensibilité · distinction corrélation / causalité · pytest et reproductibilité · DAX et conception de dashboard · documentation des limites.

## 5. Questions d'entretien probables

1. Comment avez-vous découvert que `pi` et `po` étaient des compteurs cumulés, et comment les avez-vous traités ?
2. Comment avez-vous détecté et traité le saut de compteur de s_2 ? Pourquoi le neutraliser plutôt que supprimer la ligne ?
3. Pourquoi mettre à 0 les variations suspectes plutôt que les interpoler ?
4. Pourquoi ne pas annoncer un OEE ? Que faudrait-il pour le calculer ?
5. Pourquoi avoir retiré l'analyse « rebut après arrêt » du mode réel ?
6. Vos classements 3 à 5 changent sans les arrêts atypiques : comment l'avez-vous traité dans vos conclusions ?
7. Comment définissez-vous la disponibilité, et pourquoi `idle` est-il exclu ? Quel biais cela peut-il créer ?
8. Qu'est-ce qui différencie le classement par heures d'arrêt (s_1) de celui par disponibilité (s_2) ? Lequel prioriseriez-vous ?
9. Comment avez-vous évité les doubles comptages entre faits et dimensions ? Montrez le test.
10. Quel est le grain de chaque table de faits et pourquoi ?
11. Comment mesureriez-vous réellement le gain d'une action sur l'alarme A_065 (avant/après, contrôles) ?
12. Comment valideriez-vous vos mesures DAX sans Power BI exécuté ici ?
13. SQLite vs PostgreSQL : quelles adaptations seraient nécessaires ?
