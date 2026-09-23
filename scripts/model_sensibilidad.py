#!/usr/bin/env python3
"""model_sensibilidad.py — modelo de sensibilidad completo, v2 (2026-09-04).

Implementa los objetivos per cápita por municipio y los escenarios S0/S1/S2 del
prototipo a09_proto.py, con métricas REGIONALES corregidas (ponderadas por
población), barrido de sensibilidad completo y figuras.

Ampliaciones v2 (misma sesión 2026-09-04):
  * PARTE 0: fig1 con serie S2 ABIERTA y monótona (ordenada por p creciente, sin
    cerrar poligono) + verificacion numerica de monotonia en config base.
  * PARTE 1: EF5_NA (burden evitado de arido natural, placeholder 4 kg/t rango
    2-8) con contabilidad diferencial por rec_share_base (0,6) y
    rec_share_onsite (0,85): credito extra = (rec_onsite-rec_base)*p*EF5_NA por
    tonelada de generacion, solo sobre volumen realmente machacado on-site.
    Se aplica tras la seleccion (regla de dominancia conservadora sobre las
    emisiones directas). Si rec_share_onsite==rec_share_base el credito se
    cancela y el modelo reproduce v1.
  * PARTE 2: CAP_ANUAL_T (t/año procesables por la flota movil). Escenario
    S2_cap: si el volumen on-site seleccionado por S2 supera CAP, la capacidad
    se asigna a los municipios con mayor ahorro de coste por tonelada (orden
    descendente) hasta agotarla; el resto vuelve a planta. Default 200.000 t/año.
  * PARTE 3: S3 — unidades rotatorias por cluster (cuenca de planta): el coste
    fijo F se reparte a nivel de cluster, F_eff = F/(sum_m G_m*p) por tonelada,
    y se aplica la misma regla de dominancia selectiva que S2 (modelo
    simplificado de unidad rotatoria, documentado).
  * PARTE 4: barrido de p (0,05..1,00) en config base para S1/S2/S2_cap/S3,
    p_sensibilidad.csv, analisis (crossover de coste S1-S0, saturacion de
    capacidad, frontera eficiente) y fig4_p_sensibilidad.png.

Objetivos por municipio (igual que v1):
  LC_m (€/hab·año) = (C_trat + C_trans_planta + C_trans_obra) * dot
  CE_m (kg/hab·año) = (d_tot * EF1 + E_PLANT) * dot
con d_obra por cuenca = distancia media red real a la planta ponderada por
poblacion (tarifa 0,35 €/(t·km)); d_tot = d_planta + d_obra; dot = 0,5 t/hab·año.

Escenarios:
  S0  sin machaqueo on-site (todo a planta).
  S1  MANDATORIA: on-site en TODOS los municipios con share p.
  S2  SELECTIVA por dominancia: on-site solo donde mejora >=1 eje sin empeorar
      el otro (mismo share p sobre el flujo del municipio).
  S2_cap  S2 con restriccion de capacidad anual de la flota movil.
  S3  SELECTIVA por dominancia con coste fijo F compartido a nivel de cluster
      (cuenca de planta): F_eff = F/(sum_m en cluster G_m*p) €/t.

Metricas regionales (ponderadas por poblacion):
  Coste_regional (€/año) = Σ LC_m · pop_m
  CO2_regional (t/año)   = Σ CE_m · pop_m / 1000   (neto de credito EF5 cuando
                           rec_share_onsite > rec_share_base y hay on-site)

Barrido del grid (igual a v1): v_op x {8..18}, F x {1250..5000},
EF1 x {30..120} g/t·km, p x {0.1..0.7} -> 378 combinaciones en
resumen_grid_sensibilidad.csv (rec_share fijo 0,6/0,85; CAP=200.000;
EF5_NA=4). Dependencias: solo biblioteca estandar; matplotlib opcional.
"""
import csv
import json
import os
import sys
import unicodedata
import re
import difflib

# ----------------------------------------------------------------------------
# Configuración y rutas (relativas a este script / repo público)
# ----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)               # raiz de este repo público
RES = os.path.join(ROOT, "results")
os.makedirs(RES, exist_ok=True)

CSV_MUN = os.path.join(ROOT, "data", "datos_red_real_municipios.csv")
JSON_BLENDER = os.path.join(ROOT, "data", "blender_data.json")   # opcional

# Parámetros físicos (prototipo / MODELO_Y_SUPUESTOS.md)
DOT = 0.5          # t/hab·año (dotación)
TARIFA = 0.35      # €/(t·km) transporte
E_PLANT = 2.5      # kg CO2/t planta (mix UE/ES derivado; rango 1–6)
EF3 = 1.3          # kg CO2/t machaqueo on-site (0,4 L/t × 3,2 kgCO2/L)
EPS = 1e-9

# Parámetros nuevos v2 (PARTES 1 y 2)
EF5_NA = 4.0            # kg CO2/t arido natural evitado (PLACEHOLDER, rango 2–8;
                        # ver MODELO_Y_SUPUESTOS.md — sin cifra LCA unica clara
                        # accesible; base 4 kg/t documentada como placeholder)
EF5_NA_RANGE = (2.0, 8.0)
REC_SHARE_BASE = 0.6    # fraccion del CDW municipal que hoy acaba reciclada vía
                        # planta (sustituye arido natural en obra)
REC_SHARE_ONSITE = 0.85 # fraccion aprovechada cuando hay machaqueo on-site
                        # (mas material se usa y menos se desvia a vertido/uso
                        # de baja calidad)
CAP_ANUAL_T = 200_000   # t/año procesables por la flota movil (default grid)

# Parámetros base
V_OP_BASE = 12.0
F_BASE = 2500.0
EF1_BASE_G = 60        # g/t·km

# Barrido del grid principal
V_OPS = [8, 10, 12, 14, 16, 18]
FS = [1250, 2500, 5000]
EF1S_G = [30, 60, 120]
PS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
# Barridos solo para figuras / analisis (no alteran el grid CSV)
P_SWEEP = [0.05 * i for i in range(1, 21)]          # p = 0.05..1.00
FIG_PS = [0.1, 0.3, 0.5, 0.7]                       # p etiquetadas en fig2

# Barrido de capacidad (PARTE 2) y de EF5/rec_share (PARTE 1, apartado)
CAPS_SWEEP = [50_000, 100_000, 200_000, 400_000]
EF5_NA_SWEEP = [2.0, 4.0, 8.0]
REC_PAIRS_SWEEP = [(0.6, 0.85), (0.6, 0.6), (0.4, 0.85), (0.85, 0.85), (0.6, 1.0)]
REC_SENS_PS = [0.3, 0.5]

# matplotlib opcional
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    HAVE_MPL = True
except Exception:
    HAVE_MPL = False

LOG = []


def log(msg=""):
    print(msg)
    LOG.append(msg)


# ----------------------------------------------------------------------------
# Carga de datos y variables por municipio (S0)
# ----------------------------------------------------------------------------
rows = []
with open(CSV_MUN, newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        rows.append({
            "mun": r["municipio"],
            "pop": float(r["poblacion"]),
            "planta": r["planta_id"],
            "d": float(r["distancia_km"]),
            "G": float(r["produccion_t"]),        # = dot * poblacion (verificado)
            "C_trat": float(r["C_trat"]),
            "C_trans": float(r["C_trans"]),
        })
N = len(rows)

# d_obra por cuenca: media de distancia (municipio->planta) ponderada por población
by_plant = {}
for r in rows:
    by_plant.setdefault(r["planta"], []).append(r)
d_obra_by_plant = {}
for pid, rs in by_plant.items():
    w = sum(r["pop"] for r in rs) or 1.0
    d_obra_by_plant[pid] = sum(r["pop"] * r["d"] for r in rs) / w

for r in rows:
    r["d_obra"] = d_obra_by_plant[r["planta"]]
    r["d_tot"] = r["d"] + r["d_obra"]
    r["C_loopA"] = (r["C_trat"] + r["C_trans"]
                    + r["d_obra"] * TARIFA)          # €/t ruta planta completa
    r["LC0"] = r["C_loopA"] * DOT                     # €/hab·año
    r["CE0"] = None  # depende de EF1, se rellena por escenario


def ce0(r, ef1_kg):
    """CE0 (kg/hab·año) para un EF1 dado (kg CO2/t·km)."""
    return (r["d_tot"] * ef1_kg + E_PLANT) * DOT


# ----------------------------------------------------------------------------
# Nucleo de escenarios (v2)
# ----------------------------------------------------------------------------
def credit_percap(p, rec_base, rec_onsite, ef5na=EF5_NA):
    """Credito EF5 per capita (kg CO2/hab·año) por tonelada de generacion
    realmente machacada on-site: (rec_onsite-rec_base)*p*ef5na*dot.

    Contabilidad diferencial: el credito de la fraccion ya reciclada via planta
    (rec_base) es identico en S0 y en los escenarios -> se cancela en el
    diferencial; solo se acredita el incremento de material efectivamente usado
    en obra que aporta el machaqueo on-site. Si rec_onsite==rec_base -> 0.
    """
    if rec_onsite <= rec_base or p <= 0 or ef5na <= 0:
        return 0.0
    return (rec_onsite - rec_base) * p * ef5na * DOT


def dec_municipio(r, p, F, v_op, ef1_kg, c_b, rec_base=REC_SHARE_BASE,
                  rec_onsite=REC_SHARE_ONSITE, ef5na=EF5_NA):
    """Decision a nivel de municipio con coste on-site c_b (€/t) dado.

    c_b lo fija el llamante: S1/S2 -> F/(G*p)+v_op; S3 -> F/V_cluster+v_op.
    Devuelve el dict de estado con LC/CE (CE neto de credito EF5 si on-site),
    la bandera de dominancia (regla identica a v1, sobre emisiones DIRECTAS,
    sin credito: conservadora) y volumen/save_t para la regla de capacidad.
    """
    ce0m = ce0(r, ef1_kg)
    lc_base, ce_base = r["LC0"], ce0m
    v = r["G"] * p
    if v <= 0:
        return {"LC": lc_base, "CE": ce_base, "mode": "plant",
                "lc_mix": lc_base, "ce_mix": ce_base,
                "better_c": False, "better_e": False, "pass": False,
                "vol_t": 0.0, "save_t": 0.0, "credit": 0.0}
    lc_mix = p * (c_b * DOT) + (1 - p) * lc_base
    ce_mix = p * (EF3 * DOT) + (1 - p) * ce_base     # directa (sin credito)
    better_c = lc_mix <= lc_base - EPS
    better_e = ce_mix <= ce_base - EPS
    no_worse_c = lc_mix <= lc_base + EPS
    no_worse_e = ce_mix <= ce_base + EPS
    passes = (better_c or better_e) and no_worse_c and no_worse_e
    cred = credit_percap(p, rec_base, rec_onsite, ef5na)
    return {"lc_mix": lc_mix, "ce_mix": ce_mix,
            "better_c": better_c, "better_e": better_e, "pass": passes,
            "vol_t": v, "save_t": r["C_loopA"] - c_b,   # €/t ahorro on-site
            "credit": cred}


def finalizar(ds, ef1_kg, rec_base=REC_SHARE_BASE, rec_onsite=REC_SHARE_ONSITE,
              ef5na=EF5_NA, rows_in=None):
    """Convierte decisiones en res municipales (LC/CE netos, mode) y metricas."""
    res, n_losers, n_impr = [], 0, 0
    for i, d in enumerate(ds):
        r = rows_in[i]
        if d["mode"] == "onsite":
            lc = d["lc_mix"]
            ce = d["ce_mix"] - d["credit"]
            cred = d["credit"]
        else:
            lc = r["LC0"]
            ce = ce0(r, ef1_kg)
            cred = 0.0
        res.append({"LC": lc, "CE": ce, "mode": d["mode"],
                    "vol_t": d["vol_t"], "save_t": d["save_t"],
                    "credit": cred})
        if lc > r["LC0"] + EPS:
            n_losers += 1
        if lc < r["LC0"] - EPS or ce < ce0(r, ef1_kg) - EPS:
            n_impr += 1
    cost = sum(x["LC"] * r["pop"] for x, r in zip(res, rows_in))
    co2_net = sum(x["CE"] * r["pop"] for x, r in zip(res, rows_in)) / 1e3
    vol = sum(x["vol_t"] for x in res if x["mode"] == "onsite")
    credit_t = sum(x["credit"] * r["pop"] for x, r in zip(res, rows_in)) / 1e3
    return {"res": res, "cost_reg": cost, "co2_t": co2_net, "credit_t": credit_t,
            "vol_onsite_t": vol,
            "n_onsite": sum(1 for x in res if x["mode"] == "onsite"),
            "n_losers": n_losers, "n_impr": n_impr}


def escenario_s12(rows_in, p, F, v_op, ef1_kg, mode, cap_t=None,
                  rec_base=REC_SHARE_BASE, rec_onsite=REC_SHARE_ONSITE,
                  ef5na=EF5_NA):
    """S1 (on-site en todos) / S2 (selectiva por dominancia) y S2_cap si cap_t.

    Si cap_t no es None y el volumen seleccionado por S2 supera la capacidad
    anual, se asigna la flota a los municipios con mayor ahorro de coste por
    tonelada (save_t, orden descendente) hasta agotarla; el resto vuelve a
    planta (todo-o-nada por municipio).
    """
    ds = []
    for r in rows_in:
        v = r["G"] * p
        if v <= 0:
            ds.append({"LC": r["LC0"], "CE": ce0(r, ef1_kg), "mode": "plant",
                       "lc_mix": r["LC0"], "ce_mix": ce0(r, ef1_kg),
                       "better_c": False, "better_e": False, "pass": False,
                       "vol_t": 0.0, "save_t": 0.0, "credit": 0.0})
            continue
        c_b = F / v + v_op
        d = dec_municipio(r, p, F, v_op, ef1_kg, c_b,
                          rec_base, rec_onsite, ef5na)
        if mode == "S1":
            d["mode"] = "onsite"
        else:
            d["mode"] = "onsite" if d["pass"] else "plant"
        ds.append(d)
    # Restriccion de capacidad (solo tiene sentido sobre la seleccion S2)
    if cap_t is not None and mode in ("S1", "S2"):
        total = sum(d["vol_t"] for d in ds if d["mode"] == "onsite")
        if total > cap_t + EPS:
            order = sorted((i for i, d in enumerate(ds) if d["mode"] == "onsite"),
                           key=lambda i: ds[i]["save_t"], reverse=True)
            used = 0.0
            for i in order:
                vi = rows_in[i]["G"] * p
                if used + vi <= cap_t + EPS:
                    used += vi
                else:
                    ds[i]["mode"] = "plant"
    return finalizar(ds, ef1_kg, rec_base, rec_onsite, ef5na, rows_in)


def escenario_s3(rows_in, p, F, v_op, ef1_kg,
                 rec_base=REC_SHARE_BASE, rec_onsite=REC_SHARE_ONSITE,
                 ef5na=EF5_NA):
    """S3 — unidades rotatorias por cluster (cuenca de planta).

    El coste fijo de campana F se reparte a nivel de cluster:
        F_eff = F / (Σ_{m en cluster} G_m·p)   (€/t)
    y cada municipio usa c_b = F_eff + v_op en la regla de dominancia selectiva
    identica a S2. Modelo SIMPLIFICADO de unidad rotatoria: la campana
    compartida atiende al pool de volumen p del cluster completo; si solo una
    parte del cluster resulta elegible, el coste fijo recaudado es proporcional
    al volumen realmente on-site (subestimacion del coste fijo en clusters
    parciales). Sin restriccion de capacidad (S3_cap fuera de alcance).
    """
    # volumen p del pool por cluster
    vc = {}
    for r in rows_in:
        vc[r["planta"]] = vc.get(r["planta"], 0.0) + r["G"] * p
    ds = []
    for r in rows_in:
        v = r["G"] * p
        if v <= 0 or vc.get(r["planta"], 0.0) <= 0:
            ds.append({"LC": r["LC0"], "CE": ce0(r, ef1_kg), "mode": "plant",
                       "lc_mix": r["LC0"], "ce_mix": ce0(r, ef1_kg),
                       "better_c": False, "better_e": False, "pass": False,
                       "vol_t": 0.0, "save_t": 0.0, "credit": 0.0})
            continue
        c_b = F / vc[r["planta"]] + v_op
        d = dec_municipio(r, p, F, v_op, ef1_kg, c_b,
                          rec_base, rec_onsite, ef5na)
        d["mode"] = "onsite" if d["pass"] else "plant"
        ds.append(d)
    return finalizar(ds, ef1_kg, rec_base, rec_onsite, ef5na, rows_in)


def run_combo(p, F, v_op, ef1_g, rec_base=REC_SHARE_BASE,
              rec_onsite=REC_SHARE_ONSITE, ef5na=EF5_NA,
              cap_t=CAP_ANUAL_T):
    """Metricas regionales S0/S1/S2/S2_cap/S3 para una combinacion."""
    ef1_kg = ef1_g / 1000.0
    cost0 = sum(r["LC0"] * r["pop"] for r in rows)
    co2_0 = sum(ce0(r, ef1_kg) * r["pop"] for r in rows) / 1e3
    s1 = escenario_s12(rows, p, F, v_op, ef1_kg, "S1",
                       rec_base=rec_base, rec_onsite=rec_onsite, ef5na=ef5na)
    s2 = escenario_s12(rows, p, F, v_op, ef1_kg, "S2",
                       rec_base=rec_base, rec_onsite=rec_onsite, ef5na=ef5na)
    s2c = escenario_s12(rows, p, F, v_op, ef1_kg, "S2", cap_t=cap_t,
                        rec_base=rec_base, rec_onsite=rec_onsite, ef5na=ef5na)
    s3 = escenario_s3(rows, p, F, v_op, ef1_kg,
                      rec_base=rec_base, rec_onsite=rec_onsite, ef5na=ef5na)
    return {
        "Coste_regional_S0": cost0, "Coste_S1": s1["cost_reg"],
        "Coste_S2": s2["cost_reg"], "Coste_S2_cap": s2c["cost_reg"],
        "Coste_S3": s3["cost_reg"],
        "CO2_S0_t": co2_0, "CO2_S1_t": s1["co2_t"], "CO2_S2_t": s2["co2_t"],
        "CO2_S2_cap_t": s2c["co2_t"], "CO2_S3_t": s3["co2_t"],
        "n_onsite_S1": s1["n_onsite"], "n_onsite_S2": s2["n_onsite"],
        "n_onsite_S2_cap": s2c["n_onsite"], "n_onsite_S3": s3["n_onsite"],
        "n_perdedores_S1": s1["n_losers"], "n_perdedores_S2": s2["n_losers"],
        "n_perdedores_S2_cap": s2c["n_losers"], "n_perdedores_S3": s3["n_losers"],
        "pct_mejorados_S2": 100.0 * s2["n_onsite"] / N,
        "_s2": s2, "_s2c": s2c, "_s3": s3, "_s1": s1,
    }


# ----------------------------------------------------------------------------
# 1) Barrido de sensibilidad completo -> CSV (grid conservado y extendido)
# ----------------------------------------------------------------------------
GRID_COLS = ["v_op", "F", "EF1", "p", "Coste_regional_S0", "Coste_S1",
             "Coste_S2", "CO2_S0_t", "CO2_S1_t", "CO2_S2_t", "n_onsite_S1",
             "n_onsite_S2", "n_perdedores_S1", "pct_mejorados_S2",
             "rec_share_base", "rec_share_onsite", "EF5_NA", "CAP_ANUAL_T",
             "Coste_S2_cap", "CO2_S2_cap_t", "n_onsite_S2_cap",
             "n_perdedores_S2_cap", "Coste_S3", "CO2_S3_t", "n_onsite_S3",
             "n_perdedores_S3"]
grid_rows = []
for v_op in V_OPS:
    for F in FS:
        for ef1_g in EF1S_G:
            for p in PS:
                c = run_combo(p, F, v_op, ef1_g)
                grid_rows.append({
                    "v_op": v_op, "F": F, "EF1": ef1_g, "p": p,
                    "rec_share_base": REC_SHARE_BASE,
                    "rec_share_onsite": REC_SHARE_ONSITE,
                    "EF5_NA": EF5_NA, "CAP_ANUAL_T": CAP_ANUAL_T,
                    **{k: v for k, v in c.items() if not k.startswith("_")},
                })
csv_grid = os.path.join(RES, "resumen_grid_sensibilidad.csv")
with open(csv_grid, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=GRID_COLS, extrasaction="ignore")
    w.writeheader()
    for row in grid_rows:
        w.writerow(row)
log(f"[ok] grid {len(grid_rows)} combos -> {os.path.relpath(csv_grid, ROOT)}")

# ----------------------------------------------------------------------------
# 2) Resultados base (v_op=12, F=2500, EF1=60) para p en PS
# ----------------------------------------------------------------------------
def fmt_m(v):
    return f"{v / 1e6:10.2f} M€/año"


def base_table(p):
    ef1_kg = EF1_BASE_G / 1000.0
    cost0 = sum(r["LC0"] * r["pop"] for r in rows)
    co2_0 = sum(ce0(r, ef1_kg) * r["pop"] for r in rows) / 1e3
    s1 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S1")
    s2 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2")
    s2c = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2",
                        cap_t=CAP_ANUAL_T)
    s3 = escenario_s3(rows, p, F_BASE, V_OP_BASE, ef1_kg)
    return cost0, co2_0, s1, s2, s2c, s3


print()
log("=" * 100)
log(f"RESULTADOS BASE  (v_op={V_OP_BASE:.0f} €/t, F={F_BASE:.0f} €, EF1={EF1_BASE_G} g/t·km, "
    f"E_PLANT={E_PLANT:.0f} kg/t, EF3={EF3:.2f} kg/t, dot={DOT} t/hab·año)")
log(f"PARAMETROS v2: EF5_NA={EF5_NA:g} kg/t (placeholder, rango {EF5_NA_RANGE[0]:g}-"
    f"{EF5_NA_RANGE[1]:g}), rec_share_base={REC_SHARE_BASE:g}, "
    f"rec_share_onsite={REC_SHARE_ONSITE:g}, CAP_ANUAL_T={CAP_ANUAL_T:,.0f} t/año")
log("Métricas regionales ponderadas por población: Coste_regional = Σ LC_m·pop_m (€/año); "
    "CO2_regional = Σ CE_m·pop_m/1000 (t/año), NETO de credito EF5 (diferencial).")
log(f"Municipios: {N}; población total: {sum(r['pop'] for r in rows):,.0f} hab; "
    f"plantas/cuencas (clusters S3): {len(by_plant)}.")
for p in PS:
    cost0, co2_0, s1, s2, s2c, s3 = base_table(p)
    log()
    log(f"--- p = {p:.0%} ---")
    log(f"{'Escenario':<9} | {'Coste regional':>16} | {'CO2 regional':>13} | {'n on-site':>9} | "
        f"{'mejoran ≥1 eje':>14} | {'perdedores':>10} | {'vol on-site t':>13}")
    log(f"{'S0':<9} | {fmt_m(cost0)} | {co2_0:10,.0f} t/año | {'—':>9} | {'—':>13} | {'—':>10} | {'—':>13}")
    for name, s in (("S1", s1), ("S2", s2), ("S2_cap", s2c), ("S3", s3)):
        log(f"{name:<9} | {fmt_m(s['cost_reg'])} | {s['co2_t']:10,.0f} t/año | "
            f"{s['n_onsite']:>4}/{N} | {s['n_impr']:>11,} | {s['n_losers']:>10,} | "
            f"{s['vol_onsite_t']:>11,.0f}")
    s1, s2, s2c, s3 = base_table(p)[2:]
    log(f"  -> S2: on-site en {s2['n_onsite']} municipios ({100*s2['n_onsite']/N:.1f} %), "
        f"volumen {s2['vol_onsite_t']:,.0f} t/año; perdedores S2 = {s2['n_losers']}; "
        f"perdedores S1 = {s1['n_losers']}")
    log(f"  -> S2_cap (CAP={CAP_ANUAL_T:,.0f} t): on-site {s2c['n_onsite']}, volumen "
        f"{s2c['vol_onsite_t']:,.0f} t/año, perdedores {s2c['n_losers']} — "
        f"{'NO VINCULA' if abs(s2c['cost_reg']-s2['cost_reg']) < 1 else 'VINCULA la capacidad'}")
    log(f"  -> S3 (F compartido por cluster): on-site {s3['n_onsite']} "
        f"(+{s3['n_onsite']-s2['n_onsite']} municipios vs S2), perdedores {s3['n_losers']}")
    log(f"  -> Delta coste S2−S0 = {s2['cost_reg']-cost0:+,.0f} €/año; "
        f"S3−S0 = {s3['cost_reg']-cost0:+,.0f}; S1−S0 = {s1['cost_reg']-cost0:+,.0f}; "
        f"S2_cap−S0 = {s2c['cost_reg']-cost0:+,.0f}")
    log(f"  -> Delta CO2 S2−S0 = {s2['co2_t']-co2_0:+,.0f} t/año; "
        f"S3−S0 = {s3['co2_t']-co2_0:+,.0f}; S1−S0 = {s1['co2_t']-co2_0:+,.0f}; "
        f"S2_cap−S0 = {s2c['co2_t']-co2_0:+,.0f}")

# CSVs municipales base (columnas v1 conservadas + S2_cap/S3/credito)
for p in PS:
    ef1_kg = EF1_BASE_G / 1000.0
    cost0, co2_0, s1, s2, s2c, s3 = base_table(p)
    base_csv = os.path.join(RES, f"base_municipios_p{int(p*100):03d}.csv")
    with open(base_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["municipio", "planta_id", "poblacion", "produccion_t", "d_km",
                    "d_obra_km", "C_loopA_euro_t", "LC0_euro_hab", "CE0_kg_hab",
                    "LC_S1_euro_hab", "CE_S1_kg_hab", "LC_S2_euro_hab",
                    "CE_S2_kg_hab", "onsite_S2",
                    "LC_S2cap_euro_hab", "CE_S2cap_kg_hab", "onsite_S2cap",
                    "LC_S3_euro_hab", "CE_S3_kg_hab", "onsite_S3",
                    "credito_EF5_kg_hab"])
        for r, x1, x2, x2c, x3 in zip(rows, s1["res"], s2["res"], s2c["res"], s3["res"]):
            cred = max(x1["credit"], x2["credit"], x2c["credit"], x3["credit"])
            w.writerow([r["mun"], r["planta"], f"{r['pop']:.0f}", f"{r['G']:.1f}",
                        f"{r['d']:.2f}", f"{r['d_obra']:.2f}", f"{r['C_loopA']:.2f}",
                        f"{r['LC0']:.4f}", f"{ce0(r, ef1_kg):.4f}",
                        f"{x1['LC']:.4f}", f"{x1['CE']:.4f}",
                        f"{x2['LC']:.4f}", f"{x2['CE']:.4f}",
                        1 if x2["mode"] == "onsite" else 0,
                        f"{x2c['LC']:.4f}", f"{x2c['CE']:.4f}",
                        1 if x2c["mode"] == "onsite" else 0,
                        f"{x3['LC']:.4f}", f"{x3['CE']:.4f}",
                        1 if x3["mode"] == "onsite" else 0,
                        f"{cred:.4f}"])
    log(f"[ok] base municipal p={p:.0%} -> {os.path.relpath(base_csv, ROOT)}")

# ----------------------------------------------------------------------------
# 3) Robustez sobre el grid completo (incluye escenarios nuevos)
# ----------------------------------------------------------------------------
print()
log("=" * 100)
log(f"ROBUSTEZ (grid completo: {len(grid_rows)} combinaciones; "
    f"rec_share {REC_SHARE_BASE:g}/{REC_SHARE_ONSITE:g}, CAP {CAP_ANUAL_T:,.0f}, "
    f"EF5_NA {EF5_NA:g})")
ahorro_s2 = [g["Coste_regional_S0"] - g["Coste_S2"] for g in grid_rows]
aum_s1 = [g["Coste_S1"] - g["Coste_regional_S0"] for g in grid_rows]
perd_s1 = [g["n_perdedores_S1"] for g in grid_rows]
ahorro_co2_s1 = [g["CO2_S0_t"] - g["CO2_S1_t"] for g in grid_rows]
ahorro_co2_s2 = [g["CO2_S0_t"] - g["CO2_S2_t"] for g in grid_rows]
ahorro_co2_s3 = [g["CO2_S0_t"] - g["CO2_S3_t"] for g in grid_rows]

def rng(vals):
    return f"{min(vals):,.0f} – {max(vals):,.0f}"

log(f"Ahorro de coste S2 vs S0 : {rng(ahorro_s2)} €/año "
    f"({min(ahorro_s2)/1e6:.2f}–{max(ahorro_s2)/1e6:.2f} M€/año)")
log(f"Aumento de coste S1 vs S0 : {rng(aum_s1)} €/año "
    f"(min {min(aum_s1)/1e6:+.2f} M€/año, max {max(aum_s1)/1e6:+.2f} M€/año)")
log(f"Perdedores de coste en S1 : {min(perd_s1)} – {max(perd_s1)} municipios")
log(f"Ahorro CO2 S1 vs S0 : {rng(ahorro_co2_s1)} t/año;  S2 vs S0: {rng(ahorro_co2_s2)} t/año; "
    f"S3 vs S0: {rng(ahorro_co2_s3)} t/año")

# Chequeo de las afirmaciones cualitativas (v1 + escenarios nuevos)
claims = {
    "S2 más barato que S1 (Coste_S2 <= Coste_S1)": [],
    "S2 sin perdedores de coste": [],
    "S1 logra el menor CO2 (CO2_S1 <= CO2_S2)": [],
    "S1 tiene perdedores (n_perdedores_S1 > 0)": [],
    "S2 mejora coste regional (Coste_S2 < Coste_S0)": [],
    "S1 encarece regionalmente (Coste_S1 > Coste_S0)": [],
    "S2_cap sin perdedores de coste": [],
    "S2_cap no encarece vs S2 (Coste_S2_cap >= Coste_S2 − tol)": [],
    "S2_cap no reduce el recorte de CO2 por debajo del directo de S2 (CO2_S2_cap >= CO2_S2 − tol)": [],
    "S3 sin perdedores de coste": [],
    "S3 cubre al menos a S2 (n_onsite_S3 >= n_onsite_S2)": [],
    "S3 no encarece vs S2 (Coste_S3 <= Coste_S2 + tol)": [],
    "S3 reduce CO2 al menos como S2 (CO2_S3 <= CO2_S2 + tol)": [],
}
weak = {k: [] for k in claims}
for g in grid_rows:
    tag = f"v_op={g['v_op']}, F={g['F']}, EF1={g['EF1']}, p={g['p']}"
    if not (g["Coste_S2"] <= g["Coste_S1"] + 1.0):
        weak["S2 más barato que S1 (Coste_S2 <= Coste_S1)"].append(tag)
    if g["Coste_S2"] > g["Coste_regional_S0"] + 1.0:
        weak["S2 mejora coste regional (Coste_S2 < Coste_S0)"].append(tag)
    if not (g["CO2_S1_t"] <= g["CO2_S2_t"] + 1e-6):
        weak["S1 logra el menor CO2 (CO2_S1 <= CO2_S2)"].append(tag)
    if g["n_perdedores_S1"] == 0:
        weak["S1 tiene perdedores (n_perdedores_S1 > 0)"].append(tag)
    if g["Coste_S1"] <= g["Coste_regional_S0"]:
        weak["S1 encarece regionalmente (Coste_S1 > Coste_S0)"].append(tag)
    if g["n_perdedores_S2_cap"] != 0:
        weak["S2_cap sin perdedores de coste"].append(tag)
    if g["Coste_S2_cap"] < g["Coste_S2"] - 1.0:
        weak["S2_cap no encarece vs S2 (Coste_S2_cap >= Coste_S2 − tol)"].append(tag)
    if g["CO2_S2_cap_t"] < g["CO2_S2_t"] - 1e-6:
        weak["S2_cap no reduce el recorte de CO2 por debajo del directo de S2 (CO2_S2_cap >= CO2_S2 − tol)"].append(tag)
    if g["n_perdedores_S3"] != 0:
        weak["S3 sin perdedores de coste"].append(tag)
    if g["n_onsite_S3"] < g["n_onsite_S2"]:
        weak["S3 cubre al menos a S2 (n_onsite_S3 >= n_onsite_S2)"].append(tag)
    if g["Coste_S3"] > g["Coste_S2"] + 1.0:
        weak["S3 no encarece vs S2 (Coste_S3 <= Coste_S2 + tol)"].append(tag)
    if g["CO2_S3_t"] > g["CO2_S2_t"] + 1e-6:
        weak["S3 reduce CO2 al menos como S2 (CO2_S3 <= CO2_S2 + tol)"].append(tag)

log()
log(f"Chequeo de la conclusión cualitativa en el grid ({len(grid_rows)} combos):")
for k, v in weak.items():
    estado = "SE MANTIENE en todo el grid" if not v else f"se DEBILITA en {len(v)} combos"
    log(f"  [{estado}] {k}")
    for tag in v[:8]:
        log(f"      -> {tag}")

log()
log("CONCLUSIÓN DE ROBUSTEZ:")
if not any(weak.values()):
    log("  Todas las afirmaciones se mantienen en TODAS las combinaciones del grid.")
else:
    log("  Estructuralmente se mantiene: S2/S2_cap/S3 sin perdedores y S2/S3 <= S1 en coste; "
        "S1 único mínimo de CO2 a costa de perdedores locales. Matices:")
    w54 = weak["S1 encarece regionalmente (Coste_S1 > Coste_S0)"]
    if w54:
        pairs = sorted({(t.split(", ")[0], t.split(", ")[1]) for t in w54})
        log(f"  - 'S1 encarece regionalmente' falla en {len(w54)}/{len(grid_rows)} combos "
            f"(on-site barato con F/v_op bajos): S1 más barato que S0 en agregado, pero con "
            f"{min(perd_s1)}–{max(perd_s1)} municipios perdedores que subvencionan el ahorro. "
            f"Pares (v_op,F): {pairs}")

# ----------------------------------------------------------------------------
# 3b) PARTE 0 — Verificación numérica de monotonía (config base, serie fig1)
# ----------------------------------------------------------------------------
print()
log("=" * 100)
log("PARTE 0 — VERIFICACION NUMERICA DE MONOTONIA (config base, barrido p 0.05..1.00)")
ef1_kg = EF1_BASE_G / 1000.0
cost0 = sum(r["LC0"] * r["pop"] for r in rows)
co2_0 = sum(ce0(r, ef1_kg) * r["pop"] for r in rows) / 1e3
mono = {}
for name, fn in (
        ("S1", lambda p: escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S1")),
        ("S2", lambda p: escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2")),
        ("S2_cap", lambda p: escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg,
                                           "S2", cap_t=CAP_ANUAL_T)),
        ("S3", lambda p: escenario_s3(rows, p, F_BASE, V_OP_BASE, ef1_kg))):
    cs, es = [], []
    for p in P_SWEEP:
        s = fn(p)
        cs.append(s["cost_reg"])
        es.append(s["co2_t"])
    dc = [cs[i] - cs[i - 1] for i in range(1, len(cs))]
    de = [es[i] - es[i - 1] for i in range(1, len(es))]
    ok_c = all(x <= EPS for x in dc)
    ok_e = all(x <= 1e-6 for x in de)
    mono[name] = (ok_c, ok_e)
    log(f"  {name}: coste no creciente = {ok_c} (min delta {min(dc)/1e3:+.1f} k€/paso, "
        f"max {max(dc)/1e3:+.1f} k€/paso); CO2 no creciente = {ok_e} "
        f"(min {min(de):+.2f} t/paso, max {max(de):+.2f} t/paso)")
    if not (ok_c and ok_e):
        for i in range(1, len(cs)):
            if dc[i - 1] > EPS or de[i - 1] > 1e-6:
                log(f"      -> violacion en paso p={P_SWEEP[i-1]:.2f}->{P_SWEEP[i]:.2f}: "
                    f"dcost={dc[i-1]/1e3:+.1f} k€, dco2={de[i-1]:+.2f} t")
if mono["S2"][0] and mono["S2"][1]:
    log("  RESULTADO: la serie S2 (fig1) es ABIERTA y MONOTONA (coste y CO2 decrecientes "
        "con p) en la config base. El 'bucle' era un artefacto de dibujo (flecha anotada "
        "superpuesta a la serie + textos), no de los datos: se traza S2 ordenada por p "
        "creciente sin cerrar poligono y sin la flecha gruesa.")
else:
    log("  ATENCION: la serie S2 NO es monotona en la config base — revisar modelo.")

# ----------------------------------------------------------------------------
# 3c) PARTE 2 — Barrido de capacidad (S2 vs S2_cap)  + CSV
# ----------------------------------------------------------------------------
print()
log("=" * 100)
log(f"PARTE 2 — RESTRICCION DE CAPACIDAD ANUAL (S2 vs S2_cap), config base, p=0.5:")
cap_rows = []
for cap in CAPS_SWEEP:
    for p in PS:
        s2 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2")
        s2c = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2", cap_t=cap)
        cap_rows.append({
            "CAP_ANUAL_T": cap, "p": p,
            "vol_onsite_S2_t": s2["vol_onsite_t"],
            "n_onsite_S2": s2["n_onsite"], "Coste_S2": s2["cost_reg"],
            "CO2_S2_t": s2["co2_t"],
            "n_onsite_S2_cap": s2c["n_onsite"], "Coste_S2_cap": s2c["cost_reg"],
            "CO2_S2_cap_t": s2c["co2_t"],
            "delta_cost_S2cap_S2": s2c["cost_reg"] - s2["cost_reg"],
            "delta_co2_S2cap_S2": s2c["co2_t"] - s2["co2_t"],
            "perdedores_S2_cap": s2c["n_losers"],
        })
    if 0.5 in PS:
        s2 = escenario_s12(rows, 0.5, F_BASE, V_OP_BASE, ef1_kg, "S2")
        s2c = escenario_s12(rows, 0.5, F_BASE, V_OP_BASE, ef1_kg, "S2", cap_t=cap)
        bind = "NO" if abs(s2c["cost_reg"] - s2["cost_reg"]) < 1 else "SI"
        log(f"  CAP={cap:>9,.0f} t/año | p=0,5: S2 on-site {s2['n_onsite']:>3} "
            f"(vol {s2['vol_onsite_t']:>10,.0f} t) -> S2_cap on-site {s2c['n_onsite']:>3} "
            f"(vol {s2c['vol_onsite_t']:>10,.0f} t) | coste {s2c['cost_reg']/1e6:7.3f} vs "
            f"{s2['cost_reg']/1e6:7.3f} M€ (Δ {(s2c['cost_reg']-s2['cost_reg'])/1e6:+.3f}) | "
            f"CO2 {s2c['co2_t']:6,.0f} vs {s2['co2_t']:6,.0f} t (Δ {s2c['co2_t']-s2['co2_t']:+,.0f}) "
            f"| perdedores {s2c['n_losers']} | capacidad VINCULA: {bind}")
cap_csv = os.path.join(RES, "sensibilidad_capacidad.csv")
with open(cap_csv, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(cap_rows[0].keys()))
    w.writeheader()
    for row in cap_rows:
        w.writerow(row)
log(f"[ok] sensibilidad de capacidad -> {os.path.relpath(cap_csv, ROOT)}")

# ----------------------------------------------------------------------------
# 3d) PARTE 1 — Apartado de sensibilidad EF5_NA x rec_share  + CSV
# ----------------------------------------------------------------------------
print()
log("=" * 100)
log("PARTE 1 — APARTADO EF5_NA x rec_share (config base; credito solo si "
    "rec_onsite > rec_base; S0 no recibe credito: termino diferencial)")
ef_rows = []
for p in REC_SENS_PS:
    for ef5 in EF5_NA_SWEEP:
        for rb, ro in REC_PAIRS_SWEEP:
            s1 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S1",
                               rec_base=rb, rec_onsite=ro, ef5na=ef5)
            s2 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2",
                               rec_base=rb, rec_onsite=ro, ef5na=ef5)
            ef_rows.append({
                "p": p, "EF5_NA": ef5, "rec_share_base": rb,
                "rec_share_onsite": ro, "delta_rec": ro - rb,
                "CO2_S0_t": co2_0, "CO2_S1_t": s1["co2_t"],
                "credito_S1_t": s1["credit_t"], "CO2_S2_t": s2["co2_t"],
                "credito_S2_t": s2["credit_t"],
            })
ef_csv = os.path.join(RES, "sensibilidad_EF5_recshare.csv")
with open(ef_csv, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(ef_rows[0].keys()))
    w.writeheader()
    for row in ef_rows:
        w.writerow(row)
for ef5 in EF5_NA_SWEEP:
    for rb, ro in REC_PAIRS_SWEEP:
        s2 = escenario_s12(rows, 0.5, F_BASE, V_OP_BASE, ef1_kg, "S2",
                           rec_base=rb, rec_onsite=ro, ef5na=ef5)
        log(f"  p=0,5 | EF5_NA={ef5:g} | rec {rb:g}/{ro:g} (Δrec={ro-rb:+.2f}): "
            f"CO2_S2 = {s2['co2_t']:7,.0f} t (credito {s2['credit_t']:6,.1f} t) | "
            f"perdedores {s2['n_losers']}")
log("  [nota] con rec_onsite=rec_base (0,6/0,6) el credito es 0: el modelo reproduce v1. "
    f"Base v2 (0,6/0,85, EF5_NA=4) resta ~{escenario_s12(rows,0.5,F_BASE,V_OP_BASE,ef1_kg,'S2')['credit_t']:,.0f} t CO2/año a S2 (p=0,5).")
log(f"[ok] sensibilidad EF5/rec_share -> {os.path.relpath(ef_csv, ROOT)}")

# ----------------------------------------------------------------------------
# 4) PARTE 4 — Barrido de p en config base (S0/S1/S2/S2_cap/S3) + analisis
# ----------------------------------------------------------------------------
print()
log("=" * 100)
log("PARTE 4 — SENSIBILIDAD A p (config base; p = 0.05..1.00) -> p_sensibilidad.csv")
ps_cols = ["p", "Coste_regional_S0", "Coste_S1", "Coste_S2", "Coste_S2_cap",
           "Coste_S3", "CO2_S0_t", "CO2_S1_t", "CO2_S2_t", "CO2_S2_cap_t",
           "CO2_S3_t", "n_onsite_S1", "n_onsite_S2", "n_onsite_S2_cap",
           "n_onsite_S3", "n_perdedores_S1", "n_perdedores_S2",
           "n_perdedores_S2_cap", "n_perdedores_S3"]
ps_rows = []
for p in P_SWEEP:
    c = run_combo(p, F_BASE, V_OP_BASE, EF1_BASE_G)
    ps_rows.append({"p": p, **{k: v for k, v in c.items() if not k.startswith("_")}})
ps_csv = os.path.join(RES, "p_sensibilidad.csv")
with open(ps_csv, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=ps_cols, extrasaction="ignore")
    w.writeheader()
    for row in ps_rows:
        w.writerow(row)
log(f"[ok] p_sensibilidad -> {os.path.relpath(ps_csv, ROOT)}")

# --- analisis: crossover de coste S1 vs S0 ---
def first_cross(vals_x, vals_y, target=0.0):
    """Primer cruce de vals_y (yendo en x creciente) con target."""
    prev = None
    for x, y in zip(vals_x, vals_y):
        if prev is not None and (prev - target) * (y - target) <= 0:
            if abs(y - prev) < 1e-12:
                return x
            t = (target - prev) / (y - prev)
            return x * t + prev_x * (1 - t)
        prev, prev_x = y, x
    return None

ps_p = [r["p"] for r in ps_rows]
d_s1 = [r["Coste_S1"] - r["Coste_regional_S0"] for r in ps_rows]
cross = first_cross(ps_p, d_s1)
if cross is None:
    log(f"  Crossover S1−S0 (coste): NO hay cruce en p∈[0.05,1] (S1 siempre encarece "
        f"o siempre abarata; min Δ = {min(d_s1)/1e6:+.3f} M€)")
else:
    log(f"  Crossover S1−S0 (coste): p* ≈ {cross:.3f} (S1 deja de encarecer frente a S0 a "
        f"partir de p≈{cross:.2f}; Δ(p=1,0) = {d_s1[-1]/1e6:+.3f} M€/año)")

# --- analisis: saturacion de capacidad S2_cap ---
vol_s2 = [escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2")["vol_onsite_t"]
          for p in ps_p]
sat = first_cross(ps_p, vol_s2, target=CAP_ANUAL_T)
if sat is None:
    log(f"  Saturacion CAP={CAP_ANUAL_T:,.0f} t: la demanda S2 no supera la capacidad en "
        f"p∈[0.05,1] (vol max {max(vol_s2):,.0f} t)")
else:
    log(f"  Saturacion CAP={CAP_ANUAL_T:,.0f} t: demanda S2 > CAP a partir de p ≈ {sat:.3f} "
        f"(vol S2 en p=1,0: {vol_s2[-1]:,.0f} t)")
    # n_onsite S2_cap en p=1 y cuantos vuelven a planta
    s2c1 = escenario_s12(rows, 1.0, F_BASE, V_OP_BASE, ef1_kg, "S2", cap_t=CAP_ANUAL_T)
    log(f"    En p=1,0: S2_cap on-site en {s2c1['n_onsite']} municipios "
        f"(S2 sin cap: {escenario_s12(rows,1.0,F_BASE,V_OP_BASE,ef1_kg,'S2')['n_onsite']}); "
        f"volumen {s2c1['vol_onsite_t']:,.0f} t ≈ CAP")

# --- analisis: frontera eficiente (no dominados entre S1/S2/S2_cap/S3 x p + S0) ---
fron = [(r["p"], "S0", r["Coste_regional_S0"], r["CO2_S0_t"]) for r in ps_rows[:1]]
for r in ps_rows:
    for esc in ("S1", "S2", "S2_cap", "S3"):
        fron.append((r["p"], esc, r[f"Coste_{esc}"], r[f"CO2_{esc}_t"]))
nd = []
for i, (p, esc, c, e) in enumerate(fron):
    dom = False
    for j, (p2, esc2, c2, e2) in enumerate(fron):
        if i == j:
            continue
        if c2 <= c - 1.0 and e2 <= e - 1e-6:
            dom = True
            break
    if not dom:
        nd.append((p, esc, c, e))
nd.sort(key=lambda t: t[2])
log(f"  Frontera eficiente (puntos no dominados, tol 1 € / 1e-6 t): {len(nd)} de {len(fron)}")
for p, esc, c, e in nd:
    log(f"    p={p:4.2f} {esc:<7} coste {c/1e6:7.3f} M€/año  CO2 {e:7,.0f} t/año")
c_min = min(nd, key=lambda t: t[2])
e_min = min(nd, key=lambda t: t[3])
log(f"  Extremos: menor coste = {c_min[1]} p={c_min[0]:.2f} ({c_min[2]/1e6:.3f} M€/año); "
    f"menor CO2 = {e_min[1]} p={e_min[0]:.2f} ({e_min[3]:,.0f} t/año)")

# ----------------------------------------------------------------------------
# 5) Figuras (solo si matplotlib está disponible)
# ----------------------------------------------------------------------------
def fig_frontera():
    """Frontera regional coste-CO2 barriendo p (0.05..1.00) sobre la config base.

    v2 (PARTE 0): S2 se traza como polilinea ABIERTA ordenada por p creciente
    (sin cerrar poligono, sin flecha superpuesta). S2 es monotona en ambos ejes
    (verificado numericamente en el log). S1 = puntos dominados en coste (rojos,
    huecos). S0 = punto de referencia. El grid CSV no se toca.
    """
    cost0 = sum(r["LC0"] * r["pop"] for r in rows)
    x0, y0 = co2_0 / 1e3, cost0 / 1e6                            # kt/año, M€/año
    pts1, pts2 = [], []
    for p in P_SWEEP:
        s1 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S1")
        s2 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2")
        pts1.append((s1["co2_t"] / 1e3, s1["cost_reg"] / 1e6))
        pts2.append((s2["co2_t"] / 1e3, s2["cost_reg"] / 1e6))
    # garantia: ordenar por p creciente y NO cerrar el poligono
    pts1 = [p for _, p in sorted(zip(P_SWEEP, pts1))]
    pts2 = [p for _, p in sorted(zip(P_SWEEP, pts2))]
    xs1 = [p[0] for p in pts1]; ys1 = [p[1] for p in pts1]
    xs2 = [p[0] for p in pts2]; ys2 = [p[1] for p in pts2]

    fig, ax = plt.subplots(figsize=(8.6, 6.3))
    # S1: puntos rojos huecos (dominados en coste), guia punteada tenue
    ax.plot(xs1, ys1, ls=":", color="#c0392b", lw=1.0, alpha=0.45, zorder=2)
    ax.scatter(xs1, ys1, s=40, marker="^", facecolor="white",
               edgecolor="#c0392b", lw=1.3, zorder=3)
    # S2: frontera eficiente verde, polilinea ABIERTA (p creciente -> abajo-izq.)
    ax.plot(xs2, ys2, ls="-", color="#1a9850", lw=2.4, zorder=4)
    ax.scatter(xs2, ys2, s=26, marker="o", facecolor="#1a9850",
               edgecolor="none", zorder=5)
    # S0: unico punto de referencia
    ax.scatter([x0], [y0], marker="s", s=130, color="#333333", zorder=6)
    ax.annotate("S0 — baseline (no on-site)", (x0, y0),
                xytext=(-150, 8), textcoords="offset points",
                fontsize=9.5, fontweight="bold", color="#333333",
                arrowprops=dict(arrowstyle="-", color="#333333", lw=0.8))

    # etiquetas de las series y extremos de p (sin leyenda sobrecargada)
    ax.annotate("S2 — selective on-site\n(open, monotone in p)",
                (xs2[-1], ys2[-1]), xytext=(-16, -30),
                textcoords="offset points", fontsize=9.5, color="#1a9850",
                fontweight="bold", ha="right")
    ax.annotate("S1 — indiscriminate on-site\n(all municipalities)",
                (xs1[0], ys1[0]), xytext=(10, 4),
                textcoords="offset points", fontsize=9.5, color="#c0392b",
                fontweight="bold")
    for (px, py, lab, col) in (
            (xs1[0], ys1[0], "p=0.05", "#c0392b"), (xs1[-1], ys1[-1], "p=1.0", "#c0392b"),
            (xs2[0], ys2[0], "p=0.05", "#1a9850"), (xs2[-1], ys2[-1], "p=1.0", "#1a9850")):
        ax.annotate(lab, (px, py), xytext=(5, -8), textcoords="offset points",
                    fontsize=8, color=col, ha="left", va="top")

    ax.set_xlabel("Regional CO2 (kt/yr)")
    ax.set_ylabel("Regional cost (M€/yr)")
    ax.set_title(
        "Efficient frontier — selective on-site (S2) vs indiscriminate on-site (S1)\n"
        "Baseline: v_op = 12 €/t, F = 2500 €, EF1 = 60 g/t·km; "
        "share p swept from 0.05 to 1.0 — S2 open monotone curve (one marker per p)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = os.path.join(RES, "fig1_frontera_costes_CO2.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def fig_panel_perdedores():
    """S1 cost losers (red, left axis) and cost gap S2-S0 (green, right axis).

    Left panel: vs v_op (F=2500); right panel: vs F (v_op=12).
    Lines labelled with p at the end of each curve; no legend.
    """
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 5))
    for ax, xvar, xvals, xlab in (
            (axL, "v_op", V_OPS,
             "v_op (€/t) — operating cost   [F=2500 €, EF1=60 g/t·km]"),
            (axR, "F", FS,
             "F (€/campaign) — on-site capex   [v_op=12 €/t, EF1=60 g/t·km]")):
        axb = ax.twinx()
        for p in FIG_PS:
            xs, los, dcost = [], [], []
            for xv in xvals:
                kw = dict(v_op=V_OP_BASE, F=F_BASE, ef1=EF1_BASE_G)
                kw[xvar] = xv
                g = run_combo(p, kw["F"], kw["v_op"], kw["ef1"])
                xs.append(xv)
                los.append(g["n_perdedores_S1"])
                dcost.append((g["Coste_S2"] - g["Coste_regional_S0"]) / 1e6)
            ax.plot(xs, los, marker="o", ls="-", lw=1.9, color="#c0392b", alpha=0.9)
            axb.plot(xs, dcost, marker="s", ls="--", lw=1.9, color="#1a6e34", alpha=0.85)
            ax.annotate(f"p={p:g}", xy=(xs[-1], los[-1]), xytext=(6, 3),
                        textcoords="offset points", ha="left", va="bottom",
                        fontsize=9, fontweight="bold", color="#c0392b")
            axb.annotate(f"p={p:g}", xy=(xs[-1], dcost[-1]), xytext=(6, -3),
                         textcoords="offset points", ha="left", va="top",
                         fontsize=9, fontweight="bold", color="#1a6e34")
        ax.set_xlabel(xlab)
        ax.set_ylabel("Municipalities with cost S1 > S0", color="#c0392b")
        axb.set_ylabel("Δ cost S2 − S0 (M€/yr)", color="#1a6e34")
        ax.grid(alpha=0.3)
        x0, x1 = ax.get_xlim()
        ax.set_xlim(x0, x1 + 0.16 * (x1 - x0))
    fig.suptitle("Sensitivity: S1 cost losers (red) vs S2 savings over S0 (green) — EF1 = 60 g/t·km")
    fig.tight_layout()
    out = os.path.join(RES, "fig2_perdedores_S1_y_ahorro_S2.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def load_geometry():
    """Polígonos por municipio (blender_data.json) unidos a las filas del CSV."""
    if not os.path.exists(JSON_BLENDER):
        return None, None
    with open(JSON_BLENDER, encoding="utf-8") as fh:
        jd = json.load(fh)
    FIX = {"\xa0": "á", "¡": "í", "¤": "ñ", "‚": "é"}

    def fix(s):
        for k, v in FIX.items():
            s = s.replace(k, v)
        s = re.sub(r"^(.+)\. (El|La|Los|Las)$", lambda m: m.group(2) + " " + m.group(1),
                   s.strip())
        return s

    def norm(s):
        s = unicodedata.normalize("NFC", s)
        out = []
        for c in s.lower():
            out.append({"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                        "ñ": "n"}.get(c, c))
        return "".join(out)

    # agrupar polígonos por nombre fijo (puede haber varias entradas)
    poly_by_name = {}
    for m in jd["municipalities"]:
        nm = m["name"]
        try:
            nm = nm.encode("latin-1").decode("utf-8")
        except Exception:
            pass
        nm = fix(nm)
        poly_by_name.setdefault(nm, []).extend(m["polygons"])
    csv_by_norm = {}
    for i, r in enumerate(rows):
        csv_by_norm.setdefault(norm(fix(r["mun"])), []).append(i)
    used = set()
    geo = []  # (idx_csv, [[x,y],...]) por municipio con geometría
    for nm, polys in poly_by_name.items():
        cand = csv_by_norm.get(norm(nm))
        if not cand:
            # sufijo corto tipo "Higuera" vs "Higuera de Albalat"
            pref = [ids for n, ids in csv_by_norm.items() if norm(nm).startswith(n) and n]
            cand = pref[0] if pref else None
        if cand:
            idx = cand[0] if cand[0] not in used else (cand[1] if len(cand) > 1 else None)
            if idx is not None and idx not in used:
                used.add(idx)
                geo.append((idx, polys))
    return geo, norm


def fig_mapas():
    geo, _ = load_geometry()
    if geo is None:
        return None, None
    p = 0.5
    s1 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S1")
    s2 = escenario_s12(rows, p, F_BASE, V_OP_BASE, ef1_kg, "S2")
    cm_div = LinearSegmentedColormap.from_list(
        "rdylgn", ["#b2182b", "#f8f8f8", "#1a9850"])
    cm_vir = plt.get_cmap("viridis")
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
    titles = ["S0 cost (€/capita·yr)",
              "Δ cost S2 − S0 (€/capita·yr)",
              "Δ CO2 S2 − S0 (kg/capita·yr)"]
    for ax, title in zip(axes, titles):
        ax.set_title(title, fontsize=10)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    # recopilar valores
    v_lc = [rows[i]["LC0"] for i, _ in geo]
    v_dc = [s2["res"][i]["LC"] - rows[i]["LC0"] for i, _ in geo]
    v_de = [s2["res"][i]["CE"] - ce0(rows[i], ef1_kg) for i, _ in geo]
    n0, n1 = min(v_lc), max(v_lc)
    dc_max = max(abs(x) for x in v_dc) or 1
    de_max = max(abs(x) for x in v_de) or 1
    for (i, polys), lc, dc, de in zip(geo, v_lc, v_dc, v_de):
        for poly in polys:
            xs = [pt[0] for pt in poly]
            ys = [pt[1] for pt in poly]
            for ax, val, vmin, vmax, cmap in (
                    (axes[0], lc, n0, n1, cm_vir),
                    (axes[1], dc, -dc_max, dc_max, cm_div),
                    (axes[2], de, -de_max, 0, cm_div)):
                ax.fill(xs, ys,
                        color=cmap((val - vmin) / (vmax - vmin) if vmax > vmin else 0.5),
                        edgecolor="none", zorder=2)
    axes[0].set_xlim(min(pt[0] for _, ps in geo for pgn in ps for pt in pgn),
                     max(pt[0] for _, ps in geo for pgn in ps for pt in pgn))
    axes[0].set_ylim(min(pt[1] for _, ps in geo for pgn in ps for pt in pgn),
                     max(pt[1] for _, ps in geo for pgn in ps for pt in pgn))
    for ax in axes[1:]:
        ax.set_xlim(axes[0].get_xlim())
        ax.set_ylim(axes[0].get_ylim())
    for ax, cmap, vmin, vmax, lab in (
            (axes[0], cm_vir, n0, n1, "€/capita·yr"),
            (axes[1], cm_div, -dc_max, dc_max, "€/capita·yr"),
            (axes[2], cm_div, -de_max, 0, "kg/capita·yr")):
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=Normalize(vmin, vmax))
        fig.colorbar(sm, ax=ax, shrink=0.8, label=lab)
    fig.suptitle(f"Municipal maps — baseline (v_op=12 €/t, F=2500 €, EF1=60 g/t·km, p={p:.0%}). "
                 f"Normalized coordinates from blender_data.json; {len(geo)}/{N} municipalities with polygon",
                 fontsize=10)
    fig.tight_layout()
    out = os.path.join(RES, "fig3_mapas_S0_y_S2.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out, len(geo)


def fig_p_sensibilidad():
    """PARTE 4: Δ coste y Δ CO2 vs p (config base) para S1/S2/S2_cap/S3.

    Tres paneles: (izq) Δ coste regional (M€/yr); (centro) Δ CO2 (t/yr);
    (der) perdedores de S1 (eje derecho, rojo) y nº on-site de S2/S2_cap/S3.
    Sin leyenda: colores + etiquetas de serie al final de cada curva.
    """
    xs = [r["p"] for r in ps_rows]
    escs = ["S1", "S2", "S2_cap", "S3"]
    cols = {"S1": "#c0392b", "S2": "#1a9850", "S2_cap": "#006d2c",
            "S3": "#2c7bb6"}
    lss = {"S1": "-", "S2": "-", "S2_cap": "--", "S3": "-"}
    fig, (axC, axE, axN) = plt.subplots(1, 3, figsize=(16.5, 5.2))
    # Panel 1: Δ coste regional vs p (M€/yr)
    for esc in escs:
        ys = [(r[f"Coste_{esc}"] - r["Coste_regional_S0"]) / 1e6 for r in ps_rows]
        axC.plot(xs, ys, color=cols[esc], ls=lss[esc], lw=2.2, marker="o", ms=3.5)
        axC.annotate(esc, xy=(xs[-1], ys[-1]), xytext=(4, 0),
                     textcoords="offset points", ha="left", va="center",
                     fontsize=9.5, fontweight="bold", color=cols[esc])
    axC.axhline(0.0, color="#555555", lw=0.8, zorder=1)
    axC.set_xlabel("Recycling share p (fraction of CDW crushed on-site)")
    axC.set_ylabel("Δ regional cost vs S0 (M€/yr)")
    axC.set_title("Cost gap vs baseline")
    # Panel 2: Δ CO2 vs p (t/yr)
    for esc in escs:
        ys = [(r[f"CO2_{esc}_t"] - r["CO2_S0_t"]) for r in ps_rows]
        axE.plot(xs, ys, color=cols[esc], ls=lss[esc], lw=2.2, marker="o", ms=3.5)
        axE.annotate(esc, xy=(xs[-1], ys[-1]), xytext=(4, 0),
                     textcoords="offset points", ha="left", va="center",
                     fontsize=9.5, fontweight="bold", color=cols[esc])
    axE.axhline(0.0, color="#555555", lw=0.8, zorder=1)
    axE.set_xlabel("Recycling share p (fraction of CDW crushed on-site)")
    axE.set_ylabel("Δ CO2 vs S0 (t/yr, net of EF5 credit)")
    axE.set_title("CO2 gap vs baseline")
    # Panel 3: perdedores S1 (eje der) + on-site S2/S2_cap/S3 (eje izq)
    for esc in ("S2", "S2_cap", "S3"):
        ys = [r[f"n_onsite_{esc}"] for r in ps_rows]
        axN.plot(xs, ys, color=cols[esc], ls=lss[esc], lw=2.0, marker="o", ms=3.5)
        axN.annotate(f"{esc} on-site", xy=(xs[-1], ys[-1]), xytext=(4, 0),
                     textcoords="offset points", ha="left", va="center",
                     fontsize=9, fontweight="bold", color=cols[esc])
    axN.set_xlabel("Recycling share p (fraction of CDW crushed on-site)")
    axN.set_ylabel("Municipalities on-site (S2 / S2_cap / S3)")
    axNb = axN.twinx()
    los = [r["n_perdedores_S1"] for r in ps_rows]
    axNb.plot(xs, los, color="#c0392b", ls=":", lw=2.0, marker="^", ms=4,
              markerfacecolor="white")
    axNb.annotate("S1 losers", xy=(xs[-1], los[-1]), xytext=(4, 2),
                  textcoords="offset points", ha="left", va="bottom",
                  fontsize=9, fontweight="bold", color="#c0392b")
    axNb.set_ylabel("Municipalities with cost S1 > S0", color="#c0392b")
    axNb.tick_params(axis="y", labelcolor="#c0392b")
    axN.set_title("Policy reach: on-site adoption vs S1 losers")
    for ax in (axC, axE, axN):
        ax.grid(alpha=0.3)
        ax.set_xlim(0.0, 1.0)
    fig.suptitle("p-sensitivity at baseline (v_op=12 €/t, F=2500 €, EF1=60 g/t·km, "
                 "EF5_NA=4 kg/t, rec_share 0.6/0.85, CAP=200 kt/yr)", fontsize=11)
    fig.tight_layout()
    out = os.path.join(RES, "fig4_p_sensibilidad.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


if HAVE_MPL:
    outs = [fig_frontera()]
    outs.append(fig_panel_perdedores())
    m = fig_mapas()
    if m[0]:
        outs.append(m[0])
        log(f"\n[ok] figuras PNG en {RES}")
        for o in outs:
            log(f"  - {os.path.basename(o)}")
    else:
        log("\n[ok] figuras 1-2 PNG (sin geometría: no existe blender_data.json)")
    outs.append(fig_p_sensibilidad())
    log(f"  - {os.path.basename(outs[-1])}")
else:
    log("\n[aviso] matplotlib NO está disponible: solo CSV + tablas de texto (sin PNG).")

# ----------------------------------------------------------------------------
# 6) Volcado del log (reproducibilidad)
# ----------------------------------------------------------------------------
with open(os.path.join(RES, "resumen_modelo.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG) + "\n")
log(f"[ok] log -> {os.path.relpath(os.path.join(RES, 'resumen_modelo.txt'), ROOT)}")
