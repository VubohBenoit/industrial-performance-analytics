"""Scénarios « what-if » (ESTIMATIONS, pas des gains mesurés). Sortie : reports/scenarios.json.

S1  Réduire de 50 % le temps d'arrêt de l'alarme dominante de la machine la plus arrêtée.
    Heures récupérées x production conforme par heure de marche de la machine.
    Hypothèses : les heures récupérées sont reconverties en marche à la cadence observée ;
    la demande absorbe la production supplémentaire ; aucun effet de bord.
S2  Ramener le rebut des intervalles de production consécutifs à un arrêt au niveau
    des intervalles consécutifs à une production (même machine).
    Hypothèse : l'écart observé serait entièrement évitable (borne haute, association non causale).
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODE = json.loads((ROOT / "reports/data_quality_report.json").read_text()).get("quantities_mode", "interval")
c = pd.read_csv(ROOT / "data/processed/clean_intervals.csv", parse_dates=["start", "end"])
c = c.sort_values(["equipment_ID", "start", "end"])

dt = c[c["type"] == "downtime"]
m = dt.groupby("equipment_ID")["hours"].sum().idxmax()
a = dt[dt["equipment_ID"] == m].groupby("alarm")["hours"].sum().idxmax()
alarm_h = float(dt[(dt["equipment_ID"] == m) & (dt["alarm"] == a)]["hours"].sum())
mm = c[c["equipment_ID"] == m]
run_h = float(mm[mm["type"].isin(["production", "performance_loss"])]["hours"].sum())
out_per_run_h = float(mm["po"].sum()) / run_h
gain_h = 0.5 * alarm_h
s1 = dict(machine=m, alarm=a, alarm_downtime_h=round(alarm_h, 1), hours_recovered=round(gain_h, 1),
          output_per_run_hour=round(out_per_run_h, 1), extra_output_units=round(gain_h * out_per_run_h),
          pct_of_machine_output=round(100 * gain_h * out_per_run_h / float(mm["po"].sum()), 2),
          pct_of_fleet_output=round(100 * gain_h * out_per_run_h / float(c["po"].sum()), 2))

if MODE == "interval":
    c["prev_state"] = c.groupby("equipment_ID")["type"].shift(1)
    p = c[(c["type"] == "production") & (c["pi"] > 0) & c["prev_state"].notna()]
    rows, excess = [], 0.0
    for mach, g in p.groupby("equipment_ID"):
        d, b = g[g["prev_state"] == "downtime"], g[g["prev_state"] == "production"]
        r_d, r_b = d["rejects"].sum() / d["pi"].sum(), b["rejects"].sum() / b["pi"].sum()
        e = (r_d - r_b) * d["pi"].sum()
        excess += e
        rows.append(dict(machine=mach, rate_after_downtime=round(r_d, 4), rate_after_production=round(r_b, 4), excess_defects=round(e)))
    s2 = dict(excess_defects_total=round(excess), pct_of_all_defects=round(100 * excess / c["rejects"].sum(), 1), by_machine=rows)

else:
    s2 = {"status": "non calculé : analyse par état précédent non fiable sur compteurs cumulés (mode increments)"}
(ROOT / "reports/scenarios.json").write_text(json.dumps({"mode": MODE, "S1_halve_top_alarm": s1, "S2_remove_post_downtime_excess_defects": s2}, indent=2))
print(json.dumps({"mode": MODE, "S1": s1, "S2": s2 if MODE != "interval" else {"total": s2["excess_defects_total"], "pct": s2["pct_of_all_defects"]}}, indent=2))

# ---- Sensibilité : classement des arrêts avec / sans les événements signalés par R10 ----
d_all = c[c["type"] == "downtime"]
d_ok = d_all[~d_all["flag_long_duration"]]
sens = dict(
    flagged_events=int(d_all["flag_long_duration"].sum()),
    flagged_hours=round(float(d_all.loc[d_all["flag_long_duration"], "hours"].sum()), 1),
    flagged_share_of_downtime_pct=round(100 * float(d_all.loc[d_all["flag_long_duration"], "hours"].sum() / d_all["hours"].sum()), 1),
    machine_ranking_all=d_all.groupby("equipment_ID")["hours"].sum().sort_values(ascending=False).round(1).to_dict(),
    machine_ranking_without_flagged=d_ok.groupby("equipment_ID")["hours"].sum().sort_values(ascending=False).round(1).to_dict(),
    top3_alarms_all=d_all.groupby("alarm")["hours"].sum().sort_values(ascending=False).head(3).round(1).to_dict(),
    top3_alarms_without_flagged=d_ok.groupby("alarm")["hours"].sum().sort_values(ascending=False).head(3).round(1).to_dict(),
)
out = json.loads((ROOT / "reports/scenarios.json").read_text())
sens["top2_alarms_per_machine"] = {m: g.groupby("alarm")["hours"].sum().sort_values(ascending=False).head(2).round(1).to_dict() for m, g in d_all.groupby("equipment_ID")}
sens["downtime_events_per_machine"] = d_all.groupby("equipment_ID").size().to_dict()
sens["downtime_share_top5pct_longest"] = round(float(d_all["hours"].sort_values(ascending=False).head(int(len(d_all) * 0.05)).sum() / d_all["hours"].sum()), 3)
sens["counter_flags"] = {k: int(c[k].sum()) for k in ("flag_counter_reset", "flag_counter_gap", "flag_counter_jump") if k in c.columns}
out["sensitivity_long_downtime"] = sens
(ROOT / "reports/scenarios.json").write_text(json.dumps(out, indent=2))
print(json.dumps(sens, indent=2))
