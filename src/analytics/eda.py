"""Analyse exploratoire reproductible : figures + commentaire structuré.

Pour chaque figure : question métier, méthode, résultat observé (chiffres calculés
sur les données, jamais saisis à la main) et limites d'interprétation.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.transformations.kpi import compute_kpis, nominal_speed, pareto

PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2", "#9D755D", "#BAB0AC"]
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 140, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.prop_cycle": plt.cycler(color=PALETTE),
})


def _save(fig, out: Path, name: str) -> str:
    out.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out / name, bbox_inches="tight")
    plt.close(fig)
    return name


def _bootstrap_ci(values_in: np.ndarray, values_def: np.ndarray, n: int = 1000, seed: int = 7):
    """IC 95 % bootstrap du taux de défauts, ré-échantillonnage au niveau INTERVALLE."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values_in), size=(n, len(values_in)))
    rates = values_def[idx].sum(axis=1) / values_in[idx].sum(axis=1)
    return np.percentile(rates, [2.5, 97.5])


def run_eda(clean: pd.DataFrame, fig_dir: Path | str, summary_path: Path | str, quantities: str = "interval") -> dict:
    fig_dir, summary_path = Path(fig_dir), Path(summary_path)
    nom = nominal_speed(clean)
    sections: list[dict] = []
    findings: dict = {}

    daily = compute_kpis(clean, ["equipment_ID", "date"], nom)
    daily["date"] = pd.to_datetime(daily["date"])

    # ---- Fig 1 : production par jour et par semaine -----------------------
    tot = daily.groupby("date", as_index=False)["output_units"].sum()
    wk = tot.set_index("date")["output_units"].resample("W-MON", label="left", closed="left").sum()
    fig, ax = plt.subplots(1, 2, figsize=(13, 4))
    ax[0].plot(tot["date"], tot["output_units"] / 1e3, lw=0.8, color=PALETTE[0])
    ax[0].set(title="Production quotidienne (toutes machines)", ylabel="Paquets conformes (milliers)")
    full_weeks = wk.iloc[1:-1]
    ax[1].plot(full_weeks.index, full_weeks / 1e3, marker="o", ms=3, color=PALETTE[1])
    ax[1].set(title="Production hebdomadaire (semaines complètes)", ylabel="Paquets conformes (milliers)")
    n1 = _save(fig, fig_dir, "fig01_production_daily_weekly.png")
    cv = float(full_weeks.std() / full_weeks.mean())
    findings["weekly_cv"] = cv
    sections.append(dict(
        file=n1, title="Évolution de la production (jour / semaine)",
        question="La production totale est-elle stable dans le temps ? Y a-t-il des ruptures ?",
        method="Somme des paquets de sortie (po) par jour de début d'intervalle, puis par semaine (lundi). Semaines partielles exclues du panneau de droite.",
        result=f"Production hebdomadaire moyenne : {full_weeks.mean():,.0f} paquets (min {full_weeks.min():,.0f}, max {full_weeks.max():,.0f}) ; coefficient de variation {cv:.1%}.",
        limits="Somme des 5 machines (vitesses nominales différentes) ; un intervalle à cheval sur minuit est rattaché à son jour de début ; aucune notion de commande ou de demande.",
    ))

    # ---- Fig 2 : arrêts par machine et par cause --------------------------
    dt = clean[clean["type"] == "downtime"]
    top_alarms = pareto(dt, "alarm", "hours")["alarm"].head(6).tolist()
    dt = dt.assign(alarm_grp=np.where(dt["alarm"].isin(top_alarms), dt["alarm"], "Autres"))
    pv = dt.pivot_table(index="equipment_ID", columns="alarm_grp", values="hours", aggfunc="sum", fill_value=0)
    pv = pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    bottom = np.zeros(len(pv))
    for i, c in enumerate(pv.columns):
        ax[0].bar(pv.index, pv[c], bottom=bottom, label=c, color=PALETTE[i % len(PALETTE)])
        bottom += pv[c].values
    ax[0].set(title="Temps d'arrêt non planifié par machine et cause", ylabel="Heures d'arrêt")
    ax[0].legend(title="Alarme", fontsize=8, ncol=2)
    pa = pareto(clean[clean["type"] == "downtime"], "alarm", "hours")
    ax[1].bar(pa["alarm"], pa["share"] * 100, color=PALETTE[0])
    ax2 = ax[1].twinx()
    ax2.plot(pa["alarm"], pa["cum_share"] * 100, color=PALETTE[3], marker="o", ms=4)
    ax2.set_ylim(0, 105)
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax[1].set(title="Pareto des alarmes (durée d'arrêt)", ylabel="% du temps d'arrêt")
    ax2.set_ylabel("% cumulé")
    ax[1].tick_params(axis="x", rotation=60)
    n2 = _save(fig, fig_dir, "fig02_downtime_machine_cause.png")
    by_m = clean[clean["type"] == "downtime"].groupby("equipment_ID")["hours"].sum().sort_values(ascending=False)
    n80 = int((pa["cum_share"] < 0.8).sum() + 1)
    findings.update(top_machine=by_m.index[0], top_machine_share=float(by_m.iloc[0] / by_m.sum()),
                    top_alarm=pa.loc[0, "alarm"], top_alarm_share=float(pa.loc[0, "share"]), n_alarms_80=n80,
                    n_alarms=int(len(pa)))
    sections.append(dict(
        file=n2, title="Arrêts par machine et par cause",
        question="Quelles machines et quelles alarmes concentrent le temps d'arrêt non planifié ?",
        method="Somme des durées des intervalles d'état 'downtime' par machine x alarme ; Pareto sur la durée totale par alarme.",
        result=f"{by_m.index[0]} concentre {by_m.iloc[0] / by_m.sum():.1%} des heures d'arrêt ({by_m.iloc[0]:,.0f} h). L'alarme {pa.loc[0, 'alarm']} pèse {pa.loc[0, 'share']:.1%} du temps d'arrêt ; {n80} alarmes sur {len(pa)} cumulent au moins 80 %.",
        limits="La durée dépend du codage des alarmes (une alarme = cause déclarée, pas forcément cause racine). Les arrêts 'UNKNOWN' sont des alarmes manquantes imputées par la règle R8.",
    ))

    # ---- Fig 3 : taux de défauts par machine et par état précédent --------
    if quantities == "increments":
        k_m = compute_kpis(clean, ["equipment_ID"], nom).sort_values("defect_rate", ascending=False)
        fig, ax = plt.subplots(figsize=(7, 4.2))
        ax.bar(k_m["equipment_ID"], k_m["defect_rate"] * 100, color=PALETTE[0])
        ax.set(title="Écart entrées/sorties par machine (agrégé)", ylabel="% (Σ pi - Σ po) / Σ pi")
        n3 = _save(fig, fig_dir, "fig03_defect_rate.png")
        findings.update(worst_defect_machine=k_m.iloc[0]["equipment_ID"], worst_defect_rate=float(k_m.iloc[0]["defect_rate"]))
        sections.append(dict(
            file=n3, title="Écart entrées/sorties par machine",
            question="Quelles machines affichent le plus grand écart entre paquets entrés et sortis ?",
            method="Sur compteurs cumulés différenciés (convention : variation attribuée à la ligne courante), écart = Σ max(pi - po) agrégé par machine / Σ pi. Calculé UNIQUEMENT à l'agrégat.",
            result="Écart par machine : " + ", ".join(f"{r.equipment_ID} {r.defect_rate:.2%}" for r in k_m.itertuples()) + ".",
            limits="⚠️ Ce n'est PAS un taux de rebut démontré : po dépasse pi sur ~15 % des lignes (décalage de comptage), les arrêts reçoivent un résidu d'environ 50 paquets, et la définition exacte de pi/po n'est pas vérifiée. Les unités de comptage ne sont pas forcément comparables entre machines. L'analyse « après un arrêt » est volontairement absente : non fiable sur ces compteurs.",
        ))
    else:
        k_m = compute_kpis(clean, ["equipment_ID"], nom).sort_values("defect_rate", ascending=False)
        c = clean.sort_values(["equipment_ID", "start", "end"]).copy()
        c["prev_state"] = c.groupby("equipment_ID")["type"].shift(1)
        prod = c[(c["type"] == "production") & (c["pi"] > 0) & c["prev_state"].notna()]
        g = prod.groupby("prev_state").agg(inp=("pi", "sum"), dfc=("rejects", "sum"), n=("pi", "size"))
        g["rate"] = g["dfc"] / g["inp"]
        g = g.sort_values("rate", ascending=False)
        cis = {s: _bootstrap_ci(prod.loc[prod["prev_state"] == s, "pi"].to_numpy(float),
                                prod.loc[prod["prev_state"] == s, "rejects"].to_numpy(float)) for s in g.index}
        fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
        ax[0].bar(k_m["equipment_ID"], k_m["defect_rate"] * 100, color=PALETTE[0])
        ax[0].set(title="Taux de défauts par machine", ylabel="% de paquets rejetés (pi - po)/pi")
        err = np.array([[g.loc[s, "rate"] - cis[s][0], cis[s][1] - g.loc[s, "rate"]] for s in g.index]).T
        ax[1].bar(g.index, g["rate"] * 100, yerr=err * 100, capsize=4, color=PALETTE[1])
        ax[1].set(title="Taux de défauts selon l'état précédent (IC 95 % bootstrap)", ylabel="% de paquets rejetés")
        ax[1].tick_params(axis="x", rotation=25)
        n3 = _save(fig, fig_dir, "fig03_defect_rate.png")
        strat = prod[prod["prev_state"].isin(["downtime", "production"])].groupby(["equipment_ID", "prev_state"]).agg(
            inp=("pi", "sum"), dfc=("rejects", "sum"))
        strat["rate"] = strat["dfc"] / strat["inp"]
        ratios = (strat["rate"].unstack("prev_state")["downtime"] / strat["rate"].unstack("prev_state")["production"])
        findings["defect_ratio_by_machine"] = ratios.round(3).to_dict()
        after_dt = g.loc["downtime", "rate"] if "downtime" in g.index else np.nan
        after_prod = g.loc["production", "rate"] if "production" in g.index else np.nan
        findings.update(worst_defect_machine=k_m.iloc[0]["equipment_ID"], worst_defect_rate=float(k_m.iloc[0]["defect_rate"]),
                        defect_after_downtime=float(after_dt), defect_after_production=float(after_prod))
        sections.append(dict(
            file=n3, title="Taux de défauts par machine et selon l'état précédent",
            question="Quelles machines rejettent le plus ? Le taux de rebut est-il plus élevé juste après un arrêt ?",
            method="Défauts = pi - po (paquets entrés non sortis), taux = défauts / pi, sur les intervalles 'production'. Comparaison par état précédent de la même machine (décalage d'un intervalle) ; IC 95 % par bootstrap au niveau intervalle (1000 tirages).",
            result=f"{k_m.iloc[0]['equipment_ID']} a le taux le plus élevé ({k_m.iloc[0]['defect_rate']:.2%}). Après un arrêt : {after_dt:.2%} contre {after_prod:.2%} après un intervalle de production (global). Rapport DANS chaque machine : " + ", ".join(f"{m} x{v:.2f}" for m, v in ratios.items()) + " — l'écart global (x" + f"{after_dt / after_prod:.2f}" + ") est partiellement un effet de composition entre machines.",
            limits="Association observée, non causale : l'état précédent n'est pas randomisé. 'pi - po' est une approximation des rebuts (l'interprétation exacte dépend du capteur). Pas de type de défaut ni de produit dans les données.",
        ))

    # ---- Fig 4 : réel vs capacité de référence ---------------------------
    wm = daily.copy()
    wm["month"] = wm["date"].dt.to_period("M").dt.to_timestamp()
    mm = wm.groupby(["equipment_ID", "month"], as_index=False).agg(
        out=("output_units", "sum"), cap=("reference_capacity", "sum"))
    mm["att"] = mm["out"] / mm["cap"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for i, (m, g2) in enumerate(mm.groupby("equipment_ID")):
        ax.plot(g2["month"], g2["att"] * 100, marker="o", ms=3, label=m, color=PALETTE[i])
    ax.axhline(100, ls="--", color="grey", lw=1)
    ax.set(title="Production conforme vs capacité de référence (mensuel)", ylabel="% de la capacité de référence")
    ax.legend(ncol=5, fontsize=8)
    n4 = _save(fig, fig_dir, "fig04_output_vs_reference.png")
    att = clean.pipe(lambda d: compute_kpis(d, ["equipment_ID"], nom))
    findings["attainment"] = att.set_index("equipment_ID")["reference_attainment"].to_dict()
    sections.append(dict(
        file=n4, title="Production réelle vs capacité de référence",
        question="Quel écart entre la production conforme et ce que la machine produirait à sa vitesse nominale pendant son temps de charge ?",
        method="Capacité de référence = vitesse nominale (P95 empirique de la vitesse en production) x heures de charge (marche + arrêts non planifiés). Rapport = po / capacité.",
        result="Taux de réalisation moyen par machine : " + ", ".join(f"{m} {v:.1%}" for m, v in findings["attainment"].items()) + ".",
        limits="⚠️ La capacité de référence est DÉRIVÉE des données, ce n'est PAS un objectif de production fourni : le dataset ne contient aucune cible. Un taux < 100 % est attendu par construction (P95).",
    ))

    # ---- Fig 5 : distribution des durées d'arrêt -------------------------
    d = clean[clean["type"] == "downtime"].copy()
    d["minutes"] = d["elapsed"] / 60
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    bins = np.logspace(np.log10(max(d["minutes"].min(), 0.5)), np.log10(d["minutes"].max()), 40)
    for i, (m, g2) in enumerate(d.groupby("equipment_ID")):
        ax[0].hist(g2["minutes"], bins=bins, histtype="step", lw=1.4, label=m, color=PALETTE[i])
    ax[0].set(xscale="log", title="Distribution des durées d'arrêt (échelle log)", xlabel="Minutes", ylabel="Nombre d'arrêts")
    ax[0].legend(fontsize=8)
    d.boxplot(column="minutes", by="equipment_ID", ax=ax[1], grid=False, showfliers=True, flierprops=dict(markersize=2))
    ax[1].set(yscale="log", title="Durée d'arrêt par machine", xlabel="", ylabel="Minutes (log)")
    fig.suptitle("")
    n5 = _save(fig, fig_dir, "fig05_downtime_duration_dist.png")
    med = d.groupby("equipment_ID")["minutes"].median()
    p95 = d["minutes"].quantile(0.95)
    top5 = d["minutes"].sort_values(ascending=False).head(max(int(len(d) * 0.05), 1)).sum() / d["minutes"].sum()
    findings.update(downtime_median_min=float(d["minutes"].median()), downtime_p95_min=float(p95), top5pct_share=float(top5))
    sections.append(dict(
        file=n5, title="Distribution des durées d'arrêt",
        question="Les pertes viennent-elles de nombreux micro-arrêts ou de quelques arrêts très longs ?",
        method="Histogramme en échelle logarithmique par machine et boîtes à moustaches.",
        result=f"Durée médiane {d['minutes'].median():.1f} min, P95 {p95:.0f} min ; les 5 % d'arrêts les plus longs représentent {top5:.1%} du temps d'arrêt total. Médiane par machine : " + ", ".join(f"{m} {v:.0f} min" for m, v in med.items()) + ".",
        limits="Distribution très asymétrique : privilégier médiane/quantiles à la moyenne. Les arrêts signalés par la règle R10 sont conservés et pèsent dans la queue.",
    ))

    # ---- Fig 6 : disponibilité par mois x machine -------------------------
    mk = compute_kpis(clean.assign(month=clean["start"].dt.to_period("M").astype(str)), ["equipment_ID", "month"], nom)
    hm = mk.pivot(index="equipment_ID", columns="month", values="availability") * 100
    fig, ax = plt.subplots(figsize=(9, 3.6))
    im = ax.imshow(hm.values, aspect="auto", cmap="YlGnBu", vmin=max(hm.min().min() - 2, 0), vmax=100)
    ax.set_xticks(range(len(hm.columns)), hm.columns, rotation=45)
    ax.set_yticks(range(len(hm.index)), hm.index)
    for i in range(hm.shape[0]):
        for j in range(hm.shape[1]):
            ax.text(j, i, f"{hm.values[i, j]:.0f}", ha="center", va="center", fontsize=8)
    ax.grid(False)
    ax.set_title("Disponibilité mensuelle par machine (%)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    n6 = _save(fig, fig_dir, "fig06_availability_heatmap.png")
    worst = np.unravel_index(np.nanargmin(hm.values), hm.shape)
    findings.update(worst_avail_machine=hm.index[worst[0]], worst_avail_month=hm.columns[worst[1]], worst_avail=float(hm.values[worst]))
    sections.append(dict(
        file=n6, title="Disponibilité par mois et machine",
        question="Quelles machines et quelles périodes affichent une disponibilité dégradée ?",
        method="Disponibilité = heures de marche / (heures de marche + heures d'arrêt non planifié). Idle et arrêts programmés exclus du temps de charge.",
        result=f"Valeur la plus basse : {hm.index[worst[0]]} en {hm.columns[worst[1]]} ({hm.values[worst]:.1f} %).",
        limits="Dépend de la convention : idle = manque de charge (exclu). Si l'idle masquait des pannes non déclarées, la disponibilité serait surestimée. Mois partiel de début/fin à interpréter avec prudence.",
    ))

    # ---- Fig 7 : profil par jour de semaine et heure ----------------------
    dtime = clean[clean["type"] == "downtime"].copy()
    dtime["hour"] = dtime["start"].dt.hour
    dtime["weekday"] = dtime["start"].dt.weekday
    fig, ax = plt.subplots(1, 2, figsize=(13, 4))
    byh = dtime.groupby("hour")["hours"].sum().reindex(range(24), fill_value=0)
    ax[0].bar(byh.index, byh.values, color=PALETTE[0])
    ax[0].set(title="Heures d'arrêt par heure de début", xlabel="Heure", ylabel="Heures d'arrêt")
    byd = dtime.groupby("weekday")["hours"].sum().reindex(range(7), fill_value=0)
    ax[1].bar(["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"], byd.values, color=PALETTE[1])
    ax[1].set(title="Heures d'arrêt par jour de semaine", ylabel="Heures d'arrêt")
    n7 = _save(fig, fig_dir, "fig07_downtime_hour_weekday.png")
    spread_h = float(byh.max() / byh.mean())
    findings.update(peak_hour=int(byh.idxmax()), peak_hour_ratio=spread_h, peak_weekday=int(byd.idxmax()))
    sections.append(dict(
        file=n7, title="Profil horaire et hebdomadaire des arrêts",
        question="Existe-t-il des créneaux (équipe, jour) qui concentrent les arrêts ?",
        method="Somme des heures d'arrêt selon l'heure et le jour de la semaine du début de l'arrêt.",
        result=f"Pic à {int(byh.idxmax())} h ({spread_h:.2f} x la moyenne horaire) ; jour le plus chargé : {['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'][int(byd.idxmax())]}.",
        limits="Les équipes ne figurent pas dans les données : l'heure n'est qu'un proxy d'équipe. Un écart faible peut être du bruit d'échantillonnage ; pas de test statistique d'hétérogénéité ici.",
    ))

    # ---- Synthèse markdown -----------------------------------------------
    lines = ["# Analyse exploratoire — résultats commentés", "",
             "> Chiffres générés automatiquement par `src/analytics/eda.py` à partir des données nettoyées.", ""]
    for s in sections:
        lines += [f"## {s['title']}", f"![{s['title']}](figures/{s['file']})", "",
                  f"- **Question métier** : {s['question']}", f"- **Méthode** : {s['method']}",
                  f"- **Résultat observé** : {s['result']}", f"- **Limites** : {s['limits']}", ""]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return {"sections": sections, "findings": findings}
