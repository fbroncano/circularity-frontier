"""Figure 3: municipal maps of the CDW loop under S0 and of the selective policy S2.

Run from the repository root or from this directory:
    python scripts/fig3_mapas.py

Requires data/blender_data.json (municipal polygons) and matplotlib.
Writes results/fig3_mapas_S0_y_S2.pdf and .png
"""
import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import Normalize
from matplotlib.patches import Patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import model_sensibilidad as M  # noqa: E402  (ejecuta el modelo al importar)

plt.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "sans-serif", "font.size": 8,
    "axes.titlesize": 8, "axes.labelsize": 7.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
})

P = 0.5
GREY = "#dcdcdc"
EPS = 1e-9

geo, _ = M.load_geometry()
if geo is None:
    sys.exit("falta data/blender_data.json: no hay geometria municipal")

s2 = M.escenario_s12(M.rows, P, M.F_BASE, M.V_OP_BASE, M.ef1_kg, "S2")
lc = [M.rows[i]["LC0"] for i, _ in geo]
dc = [s2["res"][i]["LC"] - M.rows[i]["LC0"] for i, _ in geo]
de = [s2["res"][i]["CE"] - M.ce0(M.rows[i], M.ef1_kg) for i, _ in geo]
n_grey = sum(1 for v in dc if abs(v) <= EPS)

with open(M.JSON_BLENDER, encoding="utf-8") as fh:
    bnd = json.load(fh)["boundary"]

panels = [
    dict(vals=lc, cmap=plt.get_cmap("YlOrRd"), vmin=5.0, vmax=20.0,
         ext="max", ticks=[5, 10, 15, 20], grey=False,
         title="(a) Loop cost, S0", cbl="€ per inhabitant and year"),
    dict(vals=dc, cmap=plt.get_cmap("Greens_r"), vmin=min(dc), vmax=0.0,
         grey=True, title="(b) Cost change, S2 − S0",
         cbl="€ per inhabitant and year"),
    dict(vals=de, cmap=plt.get_cmap("Blues_r"), vmin=min(de), vmax=0.0,
         grey=True, title="(c) CO$_2$ change, S2 − S0",
         cbl="kg per inhabitant and year"),
]

fig = plt.figure(figsize=(6.48, 3.15))
gs = gridspec.GridSpec(2, 3, figure=fig, height_ratios=[1, 0.05],
                       hspace=0.08, wspace=0.05,
                       left=0.02, right=0.98, top=0.945, bottom=0.135)

xs = [pt[0] for _, ps in geo for pg in ps for pt in pg]
ys = [pt[1] for _, ps in geo for pg in ps for pt in pg]
pad = 0.02 * (max(xs) - min(xs))

for j, cfg in enumerate(panels):
    ax = fig.add_subplot(gs[0, j])
    norm = Normalize(cfg["vmin"], cfg["vmax"])
    for (i, polys), val in zip(geo, cfg["vals"]):
        col = GREY if (cfg["grey"] and abs(val) <= EPS) else cfg["cmap"](norm(val))
        for poly in polys:
            ax.fill([q[0] for q in poly], [q[1] for q in poly],
                    color=col, edgecolor="white", linewidth=0.12, zorder=2)
    ax.plot([q[0] for q in bnd], [q[1] for q in bnd],
            color="#444444", linewidth=0.45, zorder=3)
    ax.set_title(cfg["title"], pad=3)
    ax.set_aspect("equal")
    ax.set_anchor("S")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)

    cax = fig.add_subplot(gs[1, j])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=cfg["cmap"], norm=norm),
                      cax=cax, orientation="horizontal",
                      extend=cfg.get("ext", "neither"))
    if cfg.get("ticks"):
        cb.set_ticks(cfg["ticks"])
    cb.set_label(cfg["cbl"], labelpad=1.5)
    cb.outline.set_linewidth(0.4)
    cb.ax.tick_params(length=2, width=0.4, pad=1.5)

fig.legend(handles=[Patch(
    facecolor=GREY, edgecolor="white",
    label="Unchanged: on-site recycling not selected "
          "(%d of %d municipalities)" % (n_grey, len(geo)))],
    loc="lower center", bbox_to_anchor=(0.5, -0.012),
    frameon=False, handlelength=1.1, handleheight=0.8)

os.makedirs(M.RES, exist_ok=True)
out = os.path.join(M.RES, "fig3_mapas_S0_y_S2.pdf")
fig.savefig(out)
fig.savefig(out.replace(".pdf", ".png"), dpi=200)
plt.close(fig)
print("[ok]", out)
