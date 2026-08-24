"""
unpacking.py — Explicação por ontological unpacking e validação por QCs.

Implementa as três etapas de Guizzardi e Guarino (2024) tal como operacionalizadas
no arcabouço:
    (1) recuperação dos truthmakers ativos por consulta SPARQL;
    (2) percurso da cadeia Vulnerability → Loss Event → Intention;
    (3) geração de afirmações contrafactuais com direção e magnitude.

E responde às três Questões de Competência da Seção 3.5 do artigo.
"""

from rdflib import Graph

from context import DecisionContext, RN_2025
from vuav import (evaluate, load_query, generate_counterfactuals,
                  write_counterfactuals_to_graph, ni_reversal_year, _short)

STRATEGY_LABEL = {
    "rn_h2v_strategy":  "H₂V",
    "rn_ni_strategy":   "NI",
    "rn_bess_strategy": "BESS",
}


def _fmt_musd(v: float) -> str:
    return f"{'+' if v >= 0 else '−'}USD {abs(v)/1e6:,.1f} M/ano"


# =============================================================================
# Etapa 1 — truthmakers ativos
# =============================================================================

def active_truthmakers(g: Graph) -> list:
    rows = g.query(load_query("q4_active_truthmakers.rq"))
    return [{
        "kind": _short(r["kind"]).replace("Truthmaker", ""),
        "symbol": str(r["symbol"]),
        "label": str(r["label"]),
        "value": float(r["value"]),
        "unit": str(r["unit"]),
        "derived": str(r["derived"]).lower() in ("true", "1"),
        "source": str(r["source"]),
    } for r in rows]


# =============================================================================
# Etapa 2 — cadeias causais
# =============================================================================

def gain_chains(g: Graph) -> dict:
    """Capability → Gain Event → Intention, com os truthmakers que fundamentam."""
    out = {}
    for r in g.query(load_query("q2_qc1_direct_explanation.rq")):
        key = (_short(r["capability"]), _short(r["gainEvent"]), _short(r["intention"]))
        out.setdefault(key, []).append(
            (str(r["symbol"]), float(r["value"]), str(r["unit"])))
    return out


def loss_chains(g: Graph) -> dict:
    """Vulnerability → Loss Event → Intention, apenas vulnerabilidades manifestas."""
    out = {}
    for r in g.query(load_query("q3_unpacking_chain.rq")):
        key = (_short(r["strategy"]), _short(r["vulnerability"]),
               _short(r["lossEvent"]), _short(r["intention"]))
        out.setdefault(key, []).append(
            (str(r["symbol"]), float(r["value"]), str(r["unit"])))
    return out


# =============================================================================
# Explicação completa
# =============================================================================

def explain(ctx: DecisionContext = RN_2025, t: int = 0,
            criterion: str = "parity") -> dict:
    g, res = evaluate(ctx, t=t)
    cfs = generate_counterfactuals(ctx, t=t, criterion=criterion)
    write_counterfactuals_to_graph(g, cfs, ctx)

    preferred = next(iter(res))
    ordering = " > ".join(f"VUAV({STRATEGY_LABEL[s]})" for s in res)

    lines = [f"{STRATEGY_LABEL[preferred]} é a Preferred Bearer porque:"]

    # (1) razão positiva da preferida
    pr = res[preferred]
    for term in pr.gains:
        lines.append(
            f"  ({len(lines)}) o {term.event} contribui {_fmt_musd(term.contribution(t))} "
            f"com L={term.likelihood:.2f}")

    # (2) razões de deprecação das demais
    for s, r in res.items():
        if s == preferred:
            continue
        worst = min(r.losses, key=lambda x: -x.magnitude, default=None)
        if worst is not None:
            lines.append(
                f"  ({len(lines)}) {STRATEGY_LABEL[s]}: {worst.event} impõe "
                f"{_fmt_musd(-worst.contribution(t))}, resultando em "
                f"VUAV = {_fmt_musd(r.value)}")

    return {
        "context": ctx.cid,
        "year": t,
        "ordering": ordering,
        "vuav": {STRATEGY_LABEL[s]: r.value for s, r in res.items()},
        "preferred_bearer": STRATEGY_LABEL[preferred],
        "deprecated_bearers": [STRATEGY_LABEL[s] for s in list(res)[1:]],
        "statement": "\n".join(lines),
        "counterfactuals": cfs,
        "counterfactual_criterion": criterion,
        "ni_reversal_year": ni_reversal_year(ctx),
        "graph": g,
    }


# =============================================================================
# Questões de Competência
# =============================================================================

def answer_qc1(ctx: DecisionContext = RN_2025) -> str:
    """QC1: Por que H₂V foi selecionado como Preferred Bearer no contexto RN_2025?"""
    g, res = evaluate(ctx)
    preferred = next(iter(res))
    chains = gain_chains(g)
    out = [f"Preferred Bearer: {STRATEGY_LABEL[preferred]} "
           f"(VUAV = {_fmt_musd(res[preferred].value)})", "Cadeia de fundamentação:"]
    for (cap, gev, intent), tms in chains.items():
        if not any(t.event == gev for t in res[preferred].terms):
            continue
        out.append(f"  {cap} → {gev} → {intent}")
        for sym, val, unit in sorted(set(tms)):
            out.append(f"      truthmaker {sym} = {val:g} {unit}")
    return "\n".join(out)


def answer_qc2(ctx: DecisionContext = RN_2025, criterion: str = "vuav_ranking") -> str:
    """QC2: Quais alterações nos truthmakers tornariam H₂V Deprecated?"""
    g, res = evaluate(ctx)
    preferred = next(iter(res))
    cfs = [c for c in generate_counterfactuals(ctx, criterion=criterion)
           if c.new_preferred != preferred or criterion == "parity"]
    out = [f"Limiares de reversão da preferência sobre "
           f"{STRATEGY_LABEL[preferred]} (critério: {criterion}):"]
    for c in cfs:
        if c.symbol in ("CAPEX_AWE", "FC", "c_log", "LCOH"):
            out.append(f"  • {c.statement()}")
            out.append(f"      mecanismo: {c.mechanism}")
    return "\n".join(out)


def answer_qc3(ctx: DecisionContext = RN_2025, criterion: str = "vuav_ranking") -> str:
    """QC3: Sob quais condições BESS torna-se Preferred Bearer?"""
    cfs = generate_counterfactuals(ctx, criterion=criterion)
    out = [f"Condições de ativação plena da EnergyArbitrageCapability "
           f"(critério: {criterion}):"]
    for c in cfs:
        if c.symbol in ("PLD", "LCOS"):
            out.append(f"  • {c.statement()}")
            out.append(f"      mecanismo: {c.mechanism}")
    g, _ = evaluate(ctx)
    out.append("Estado das vulnerabilidades do BESS no contexto-base:")
    for r in g.query(load_query("q5_qc3_bess_condition.rq")):
        out.append(f"  {_short(r['vulnerability']):42s} ativa={str(r['isActive']):5s} "
                   f"| {r['symbol']} = {float(r['value']):g} {r['unit']}")
    return "\n".join(out)


# =============================================================================
# Política de critério: viabilidade vs. reversão
# =============================================================================

# Cada afirmação de limiar pertence a uma de duas famílias, e usar o critério
# errado produz um número certo para a pergunta errada:
#
#   viabilidade — "o Gain Event converte-se em Loss", "a margem é eliminada".
#       Limiar em que VUAV(s) cruza zero. Não depende das demais alternativas.
#
#   reversão    — "torna-se Preferred Bearer", "torna-se Deprecated".
#       Limiar em que outra estratégia ultrapassa. Depende do VUAV das demais
#       alternativas e, portanto, da calibração de NI.
#
# As QCs 2 e 3 são perguntas de reversão (falam em DEPRECATED e PREFERRED
# BEARER) e usam 'vuav_ranking'. A Tabela de sensibilidade reporta limiares de
# viabilidade, mais robustos porque independem da calibração de NI.

CRITERION_OF_CLAIM = {
    "CAPEX_AWE": ("reversão",   "QC2, §4.5(a): 'tornariam H₂V Deprecated'"),
    "FC":        ("viabilidade", "§3.2: 'o Gain Event converte-se em Loss Event'"),
    "c_log":     ("viabilidade", "§4.4: 'elimina integralmente a margem de H₂V'"),
    "PLD":       ("reversão",   "§3.2, §4.3, Fig. 5: 'BESS torna-se Preferred Bearer'"),
    "LCOS":      ("viabilidade", "§4.4: 'margem → USD 0/MWh'"),
}


def dual_thresholds(ctx: DecisionContext = RN_2025) -> list:
    """Os dois limiares de cada truthmaker, com o critério que cada afirmação exige."""
    from vuav import generate_counterfactuals as _g
    par = {x.symbol: x for x in _g(ctx, criterion="parity")}
    cmp_ = {x.symbol: x for x in _g(ctx, criterion="vuav_ranking")}
    out = []
    for sym, (crit, where) in CRITERION_OF_CLAIM.items():
        if sym not in par or sym not in cmp_:
            continue
        out.append({
            "symbol": sym,
            "unit": par[sym].unit,
            "viabilidade": par[sym].threshold,
            "reversao": cmp_[sym].threshold,
            "criterio_exigido": crit,
            "valor_a_reportar": par[sym].threshold if crit == "viabilidade"
                                else cmp_[sym].threshold,
            "onde": where,
        })
    return out


# =============================================================================
# Análise de sensibilidade ontológica (Tabela 5)
# =============================================================================

SCENARIOS = [
    ("Base (RN 2025)", {}),
    ("CAPEX AWE alto", {"capex_awe_usd_kw": 1190.0}),
    ("LCOH com logística", {"custo_logistico_usd_kg": 0.55}),
    ("LCOS BESS cai (~2030)", {"lcos_usd_mwh": 92.0}),
    ("FC reduzido (PDE 2035)", {"fc": 0.34}),
    ("PLD alto (escassez hídrica)", {"pld_arbitragem_usd_mwh": 200.0}),
]


def sensitivity_table(ctx: DecisionContext = RN_2025, t: int = 0) -> list:
    rows = []
    for name, delta in SCENARIOS:
        c = ctx.with_(**delta) if delta else ctx
        _, res = evaluate(c, t=t)
        pref = next(iter(res))
        rows.append({
            "cenario": name,
            "alteracao": ", ".join(f"{k}={v}" for k, v in delta.items()) or "—",
            "lcoh": round(c.lcoh_total, 3),
            "preferred": STRATEGY_LABEL[pref],
            "vuav": {STRATEGY_LABEL[s]: round(r.value / 1e6, 1) for s, r in res.items()},
        })
    return rows
