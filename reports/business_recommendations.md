# Rapport d'analyse — constats et recommandations

> **Source** : PIADE (Université de Padoue, CC BY 4.0), 5 machines d'emballage, 429 394 intervalles d'état,
> 2020-01-01 → 2022-01-02. Chiffres issus de `reports/eda_summary.md`, `reports/scenarios.json`,
> `data/processed/kpi_by_machine.csv`.
>
> **Lecture obligatoire.** Ce sont des constats **descriptifs** : aucune intervention n'a eu lieu, aucun gain n'est
> mesuré. Les « bénéfices » ci-dessous sont des **estimations sous hypothèses**. Les compteurs `pi`/`po` sont cumulés
> et leur définition n'est pas vérifiée : l'écart entrées/sorties n'est pas un taux de rebut démontré, et l'indice de
> performance est relatif.

## 1. Périmètre et qualité des données

| | |
|---|---|
| Lignes brutes / propres / rejetées | 429 394 / 429 394 / 0 (aucune ligne supprimée ; tout est signalé) |
| Remises à zéro de compteur | 86 (variations mises à 0) |
| Trous de données > 1 h (et 1res lignes) | 1 371 : les agrégats portent sur le temps **observé** |
| Sauts de compteur implausibles | 185 (variations mises à 0), ex. compteur de s_2 passant de ~0 à ~3·10⁸ |
| `po` > `pi` | 65 636 lignes (15,3 %) : décalage de comptage, conservé |
| Chevauchements d'intervalles | 6 (signalés) |
| Arrêts non planifiés | 92 084 événements, **3 147 h** |

Sans la neutralisation des sauts de compteur, s_2 aurait affiché 201 000 unités par heure de marche (contre 3 600 à 5 100
pour les autres) : un exemple de ce qu'une analyse naïve de ce fichier aurait conclu.

## 2. Cinq constats

**C1 — Deux machines concentrent 62 % des heures d'arrêt.** s_1 : 1 393 h (44 %), s_2 : 574 h (18 %) ; puis s_3 466 h,
s_4 358 h, s_5 356 h. *Robustesse* : en écartant les 648 arrêts atypiques (20 % du temps d'arrêt), s_1 et s_2 restent
1re et 2e ; les rangs 3 à 5 **ne sont pas robustes** (s_5 passe 3e, s_4 dernière).

**C2 — Une seule alarme pèse 27 % du temps d'arrêt du parc : A_065, uniquement sur s_1** (858 h, soit 62 % des arrêts de
s_1). Quatre alarmes sur 132 (A_065, A_101, A_006, A_001) expliquent environ 69 % des heures. Sans les arrêts atypiques,
A_065 reste en tête (688 h). Le profil des causes est propre à chaque machine : s_5 est dominée par A_101 (285 h, 80 % de
ses arrêts), s_3 par A_006 (234 h, 50 %), s_2 par A_001 (181 h, 32 %) ; s_4 est diffuse (la 1re alarme ne pèse que 20 %).

**C3 — Les pertes viennent surtout de micro-arrêts.** Durée médiane d'un arrêt 0,9 min, P95 7 min, moyenne par machine
1,2 à 3,6 min. s_1 cumule 32 614 arrêts (35 % des événements). Pourtant les 5 % d'arrêts les plus longs pèsent
43 % du temps d'arrêt : fréquence et queue longue sont deux leviers distincts.

**C4 — s_2 a la pire disponibilité (75 %) alors que s_1 a le plus d'heures d'arrêt.** Disponibilité (temps observé) :
s_1 86,9 %, s_2 75,0 %, s_3 87,7 %, s_4 92,2 %, s_5 94,1 % ; creux de s_2 à 53 % en août 2020. Le classement diffère selon
qu'on regarde les heures perdues (s_1) ou la part du temps de charge perdue (s_2) : les deux lectures sont nécessaires.

**C5 — s_4 perd moins par arrêts que par régime : à confirmer.** Disponibilité correcte (92 %) mais indice de performance
relatif le plus bas (0,59 contre 0,75 à 0,82) et écart entrées/sorties le plus élevé (0,69 %). *Hypothèse* : pertes de vitesse
ou réglage plutôt que pannes. Fragile : l'indice dépend de la vitesse nominale (P95 de `speed`), qui n'est pas un cycle idéal validé.

*Non retenu comme constat* : le profil horaire (pic à 8 h, ×1,5 la moyenne) et le jour le plus chargé (vendredi) ne sont pas
interprétés : aucune équipe dans les données. La production hebdomadaire varie de 41 % : reflet de la couverture irrégulière
(trous de données), pas d'un phénomène de production.

## 3. Priorités d'investigation

1. **s_1 / A_065** : premier gisement (858 h).
2. **s_2** : disponibilité à 75 % ; alarmes A_001 et A_101 ; creux d'août 2020.
3. **s_5 / A_101** et **s_3 / A_006** : une alarme concentre 50 à 80 % des arrêts de la machine.
4. **s_4** : vérifier si les pertes sont de vitesse (hypothèse C5).
5. **Données** : confirmer la définition de `pi`/`po` et l'origine des sauts de compteur auprès des auteurs du jeu.

## 4. Indicateurs à surveiller

Heures d'arrêt hebdomadaires par alarme (A_065 sur s_1 en premier) ; nombre de micro-arrêts par heure de marche et par machine ;
durée médiane et P95 des arrêts ; disponibilité mensuelle par machine ; part de lignes de compteur signalées (sauts, trous).

## 5. Actions recommandées, bénéfices et mesure

| Action | Statut du bénéfice | Estimation | Comment le mesurer |
|---|---|---|---|
| Analyse de cause racine sur A_065 (s_1) | **Estimation** sous hypothèses | Réduire de moitié : ≈ +430 h de marche, ≈ +1,6 M de paquets (+4,6 % de s_1, +1,6 % du parc) ; borne basse ≈ +1,3 M (en écartant les arrêts atypiques) | Heures hebdomadaires d'A_065 avant/après, à production par heure de marche constante |
| Revue des alarmes dominantes de s_5 (A_101), s_3 (A_006), s_2 (A_001) | **Hypothèse** (non chiffrée) | — | Part de ces alarmes dans les heures d'arrêt de la machine |
| Mesure des pertes de vitesse sur s_4 | **Hypothèse** | — | Cadence réelle vs cadence réglée, hors arrêts |
| Confirmer pi/po et traiter les sauts de compteur à la source | **Hypothèse** | Fiabilise les volumes et le rebut | Nombre de sauts/trous de compteur par mois |

L'estimation suppose que les heures récupérées sont reconverties en marche à la production horaire observée (3 735 paquets/h
sur s_1) et absorbées par la demande, que A_065 peut réellement être réduite de moitié, et qu'aucun effet de bord n'apparaît.
Rien de cela n'est démontré. Voir `scripts/scenarios.py`.

## 6. Limites des données

Définition de `pi`/`po` non vérifiée ; résidu d'environ 50 paquets sur les lignes d'arrêt (toute analyse par état est
biaisée, l'analyse « rebut après arrêt » est donc volontairement absente) ; unités de comptage possiblement différentes entre
machines ; couverture temporelle irrégulière ; vitesse nominale empirique (pas de cycle idéal) ; pas de produit, d'équipe,
de type de défaut ni d'objectif de production ; `idle` exclu du temps de charge (convention à valider) ; données historiques
2020-2022 d'un seul site, non généralisables.

## 7. Analyses supplémentaires nécessaires

Confirmation de `pi`/`po` et de `speed` avec les auteurs ; regroupement des 132 alarmes actives par famille ; analyse de survie
ou de récurrence des arrêts d'A_065 ; test statistique d'hétérogénéité horaire ; vrai OEE avec cycle idéal et temps planifié ;
étude avant/après contrôlée une fois une action déployée.
