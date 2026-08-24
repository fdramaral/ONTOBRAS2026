"""
fig5_mapa_decisao.py — Figura 5 do artigo ONTOBRAS, versão corrigida.

Alterações em relação à versão publicada:
  • curva LCOH(FC) = 141,78/(166,86×FC) + 0,52  (componente residual incluído)
  • limiar de FC:  34%  →  43%
  • limiar de PLD: 145  →  157 USD/MWh (ultrapassagem de VUAV, não paridade)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from pathlib import Path

# ------------------------------------------------- parâmetros (de context.py)
from context import RN_2025 as _c
from unpacking import dual_thresholds

_T = {d["symbol"]: d for d in dual_thresholds(_c)}

NUM = _c.custo_anualizado_usd_kw          # CAPEX×FCR + OPEX  = 141,78 USD/kW-ano
DEN = 8760.0 / _c.kappa                   # kgH₂ por kW-ano por unidade de FC
RESIDUAL = round(_c.lcoh_residual, 2)     # energia, reposição de stack, BOP
PARIDADE = _c.preco_h2_usd_kg             # paridade H₂ cinza (USD/kg)
FC_LIM = round(_T["FC"]["valor_a_reportar"] * 100, 0)     # limiar de viabilidade
PLD_LIM = round(_T["PLD"]["valor_a_reportar"], 0)         # limiar de reversão
RN_FC, RN_LCOH = _c.fc * 100, _c.lcoh_usd_kg

# eixos
X0, X1 = 5.0, 70.0
Y0, Y1 = 0.0, 4.5               # LCOH
P0, P1 = 0.0, 300.0             # PLD

# paleta aproximada da figura original
C_CURVA = "#1F3B73"
C_NI = "#F6D7DA"
C_H2V = "#DDF0DC"
C_BESS = "#D6E9F8"
C_PARID = "#C0392B"
C_PLD = "#2E86C1"
C_GRID = "#D8D8D8"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "DejaVu Serif"],
    "font.size": 9,
    "axes.edgecolor": "#666666",
    "axes.linewidth": 0.8,
})


def lcoh(fc_pct):
    return NUM / (DEN * fc_pct / 100.0) + RESIDUAL


fig, ax = plt.subplots(figsize=(7.6, 4.3), dpi=300)
ax2 = ax.twinx()

# ------------------------------------------------------------------ regiões
ax.axvspan(X0, FC_LIM, color=C_NI, zorder=0)
ax.add_patch(plt.Rectangle((FC_LIM, Y0), X1 - FC_LIM,
                           PLD_LIM / P1 * (Y1 - Y0),
                           color=C_H2V, zorder=0))
ax.add_patch(plt.Rectangle((FC_LIM, PLD_LIM / P1 * (Y1 - Y0)), X1 - FC_LIM,
                           Y1 - PLD_LIM / P1 * (Y1 - Y0),
                           color=C_BESS, zorder=0))

ax.text(14.5, 4.20, "Região NI dominante", fontsize=8.5,
        style="italic", color="#8E3B45", ha="center", zorder=5)
ax.text((FC_LIM + X1) / 2 + 2, 0.42, "Região H₂V dominante",
        fontsize=8.5, style="italic", color="#3B6B39", ha="center", zorder=5)
ax.text((FC_LIM + X1) / 2 + 3, 0.22, "(LCOH < paridade; PLD < 157)",
        fontsize=7.2, color="#3B6B39", ha="center", zorder=5)
ax.text((FC_LIM + X1) / 2 + 3, 3.55, "Região BESS dominante",
        fontsize=8.5, style="italic", color="#1B5D8E", ha="center", zorder=5)
ax.text((FC_LIM + X1) / 2 + 3, 3.35, "(PLD ≥ USD 157/MWh)",
        fontsize=7.2, color="#1B5D8E", ha="center", zorder=5)

# ------------------------------------------------------------------- curvas
fc = np.linspace(X0, X1, 900)
ax.plot(fc, lcoh(fc), color=C_CURVA, lw=2.0, zorder=6, label="Curva LCOH(FC)")

# assíntota do componente residual
ax.axhline(RESIDUAL, color=C_CURVA, lw=0.8, ls=(0, (1, 3)), alpha=0.75, zorder=4)
ax.text(X1 - 0.8, RESIDUAL + 0.11,
        "assíntota: componente residual = USD 0,52/kg",
        fontsize=6.8, color=C_CURVA, ha="right", zorder=7)

# paridade
ax.axhline(PARIDADE, color=C_PARID, lw=1.2, ls="--", zorder=5,
           label="Paridade H₂ cinza (USD 2,50/kg)")
ax.text(X0 + 0.6, PARIDADE + 0.10, "Paridade H₂ cinza = USD 2,50",
        fontsize=7.5, color=C_PARID, zorder=7)

# limiar PLD (eixo direito)
ax2.axhline(PLD_LIM, color=C_PLD, lw=1.2, ls="-.", zorder=5,
            label="Limiar BESS: PLD = USD 157/MWh")
ax2.text(X0 + 0.8, PLD_LIM - 15, "PLD = USD 157/MWh — limiar BESS",
         fontsize=7.5, color=C_PLD, ha="left", zorder=7)

# limiar de FC
ax.axvline(FC_LIM, color="#444444", lw=1.1, ls="--", zorder=6)
ax.plot([FC_LIM], [PARIDADE], "o", ms=5.5, color="#444444", zorder=8)
ax.annotate("FC = 43%\nLCOH = 2,50", xy=(FC_LIM, PARIDADE),
            xytext=(FC_LIM - 18.0, PARIDADE + 0.42), fontsize=8,
            color="#333333", zorder=9,
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.8))

# ponto RN
ax.plot([RN_FC], [RN_LCOH], "o", ms=7, color=C_CURVA,
        markeredgecolor="white", markeredgewidth=1.0, zorder=9)
ax.annotate("RN (59,5%; USD 1,95/kg)", xy=(RN_FC, RN_LCOH),
            xytext=(RN_FC - 9.5, RN_LCOH - 0.62), fontsize=8,
            color=C_CURVA, zorder=9,
            arrowprops=dict(arrowstyle="->", color=C_CURVA, lw=0.8))
ax.plot([X0, RN_FC], [RN_LCOH, RN_LCOH], color=C_CURVA, lw=0.7,
        ls=(0, (4, 3)), alpha=0.6, zorder=4)

# --------------------------------------------------------------------- eixos
ax.set_xlim(X0, X1)
ax.set_ylim(Y0, Y1)
ax2.set_ylim(P0, P1)
ax.set_xlabel("Fator de Capacidade FC (%)", fontsize=9.5)
ax.set_ylabel("LCOH\n(USD/kg)", fontsize=9.5, rotation=0, labelpad=26, va="center")
ax2.set_ylabel("PLD\n(USD/MWh)", fontsize=9.5, rotation=0, labelpad=30,
               va="center", color=C_PLD)
ax2.tick_params(axis="y", colors=C_PLD, labelsize=8)
ax.tick_params(labelsize=8)

ax.set_xticks([10, 20, 30, 40, 43, 50, 59.5, 70])
ax.set_xticklabels(["10", "20", "30", "40", "43", "50", "59,5", "70"], fontsize=8)
for lbl, pos in zip(ax.get_xticklabels(), ax.get_xticks()):
    if pos in (43, 59.5):
        lbl.set_fontweight("bold")

ax.set_yticks(np.arange(0.5, 4.6, 0.5))
ax.set_yticklabels([f"{v:.2f}".replace(".", ",") for v in np.arange(0.5, 4.6, 0.5)],
                   fontsize=8)
ax2.set_yticks([0, 50, 100, 157, 200, 250, 300])
ax2.set_yticklabels(["0", "50", "100", "157", "200", "250", "300"], fontsize=8)

ax.grid(True, color=C_GRID, lw=0.5, zorder=1)
ax.set_axisbelow(True)

# ------------------------------------------------------------------- legenda
handles = [
    Line2D([], [], color=C_CURVA, lw=2.0, label="Curva LCOH(FC)"),
    Line2D([], [], color=C_PARID, lw=1.2, ls="--",
           label="Paridade H₂ cinza (USD 2,50/kg)"),
    Line2D([], [], color=C_PLD, lw=1.2, ls="-.",
           label="Limiar BESS (PLD = USD 157/MWh)"),
    Patch(facecolor=C_NI, label="Região NI dominante"),
    Patch(facecolor=C_H2V, label="Região H₂V dominante"),
    Patch(facecolor=C_BESS, label="Região BESS dominante"),
]
ax.legend(handles=handles, loc="lower left", fontsize=7, frameon=True,
          framealpha=0.94, edgecolor="#BBBBBB", bbox_to_anchor=(0.015, 0.035),
          handlelength=1.9, borderpad=0.5, labelspacing=0.35)

fig.tight_layout()
out = Path(__file__).resolve().parents[1] / "out"
out.mkdir(exist_ok=True)
for ext in ("png", "pdf", "svg"):
    fig.savefig(out / f"Figura5_mapa_decisao_revisada.{ext}",
                dpi=300, bbox_inches="tight", facecolor="white")
print("Figura 5 gerada em", out)
print(f"  verificação: LCOH(59,5%) = {lcoh(59.5):.3f}   LCOH(43%) = {lcoh(43.0):.3f}")
