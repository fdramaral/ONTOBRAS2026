#!/usr/bin/env python3
"""
run_all.py — Pipeline operacional do arcabouço (Figura 3 do artigo).

Etapas:
  1. modelagem ontológica e declaração dos truthmakers candidatos
  2. instanciação do grafo RDF para o contexto RN_2025
  3. recuperação dos parâmetros do VUAV por consulta SPARQL
  4. cálculo determinístico do VUAV e atribuição de Preferred/Deprecated Bearer
  5. ontological unpacking: cadeias causais e contrafactuais
  6. respostas às três Questões de Competência
  7. análise de sensibilidade ontológica
  8. verificação de consistência sob HermiT
  9. validação contra os valores publicados
 10. exportação (OWL/XML, Turtle, JSON)

Uso:  python3 run_all.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from context import RN_2025                                    # noqa: E402
from vuav import evaluate, generate_counterfactuals            # noqa: E402
from unpacking import (explain, answer_qc1, answer_qc2, answer_qc3,   # noqa: E402
                       sensitivity_table, active_truthmakers,
                       loss_chains, STRATEGY_LABEL)
from build_owl import export, reason, check_ni_satisfiable     # noqa: E402

OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

BAR = "=" * 78


def head(n, title):
    print(f"\n{BAR}\n{n}. {title}\n{BAR}")


# =============================================================================
# Valores publicados, para validação automática
# =============================================================================

PUBLICADO = {
    "horas_ativas_ano":        (5212.0,     1.0,   "h/ano"),
    "ciclos_ano":              (1303.0,     1.0,   "ciclos/ano"),
    "producao_h2_t":           (99300.0,    100.0, "tH2/ano"),
    "energia_bess_mwh":        (4690800.0,  500.0, "MWh/ano"),
    "eta_impl":                (0.75,       0.005, "—"),
    "receita_h2_musd":         (248.2,      0.2,   "USD M/ano"),
    "custo_h2_musd":           (193.6,      0.2,   "USD M/ano"),
    "receita_bess_musd":       (431.6,      0.3,   "USD M/ano"),
    "custo_bess_musd":         (680.2,      0.5,   "USD M/ano"),
    "vuav_h2v_musd":           (54.6,       0.2,   "USD M/ano"),
    "vuav_bess_musd":          (-248.6,     0.3,   "USD M/ano"),
    "limiar_capex_usd_kw":     (1190.0,     20.0,  "USD/kW"),
    "limiar_clog_usd_kg":      (0.55,       0.02,  "USD/kgH2"),
    "limiar_pld_usd_mwh":      (145.0,      1.0,   "USD/MWh"),
    "limiar_lcos_usd_mwh":     (92.0,       1.0,   "USD/MWh"),
    "limiar_fc":               (0.34,       0.01,  "—"),
}


def main():
    c = RN_2025

    # ---- 1–2 ------------------------------------------------------------
    head(1, "TRUTHMAKERS INSTANCIADOS (Tabela 2)")
    g, results = evaluate(c)
    tms = active_truthmakers(g)
    for kind in ("Technical", "Economic", "Spatial"):
        print(f"\n  [{kind}]")
        for t in [x for x in tms if x["kind"] == kind]:
            flag = " (derivado)" if t["derived"] else ""
            print(f"    {t['symbol']:>10s} = {t['value']:>12,.4f} {t['unit']:<14s}"
                  f" {t['label']}{flag}")

    # ---- 3–4 ------------------------------------------------------------
    head(2, "CÁLCULO DO VUAV (Tabela 4)")
    print("  VUAV(s,ctx) = Σᵢ [L(GEᵢ|ctx) × I(GEᵢ)] − Σⱼ [L(LEⱼ|s,ctx) × S(LEⱼ)]\n")
    for s, r in results.items():
        print(f"  {STRATEGY_LABEL[s]:<5s} {r.bearer_status}")
        for term in r.terms:
            sign = "+" if term.kind == "gain" else "−"
            print(f"      {sign} L={term.likelihood:.2f} × "
                  f"{term.magnitude/1e6:>9,.1f} M = {term.contribution()/1e6:>9,.1f} M"
                  f"   [{term.event}]")
        print(f"      VUAV = USD {r.value/1e6:,.1f} M/ano\n")
    print("  Ordenação: " + " > ".join(f"VUAV({STRATEGY_LABEL[s]})" for s in results))

    # ---- 5 --------------------------------------------------------------
    head(3, "ONTOLOGICAL UNPACKING — cadeia Vulnerability → Loss Event → Intention")
    for (strat, vul, le, intent), tmlist in loss_chains(g).items():
        print(f"  {STRATEGY_LABEL.get(strat, strat)}: {vul}")
        print(f"      → {le} → {intent}")
        for sym, val, unit in sorted(set(tmlist)):
            print(f"          fundamentado em {sym} = {val:g} {unit}")

    exp = explain(c, criterion="parity")
    print(f"\n  Explicação gerada:\n")
    for line in exp["statement"].splitlines():
        print("    " + line)
    print(f"\n  Ano em que VUAV(NI) se torna negativo: {exp['ni_reversal_year']}")

    # ---- 6 --------------------------------------------------------------
    head(4, "QUESTÕES DE COMPETÊNCIA")
    for label, fn in (("QC1", answer_qc1), ("QC2", answer_qc2), ("QC3", answer_qc3)):
        print(f"\n  --- {label} ---")
        for line in fn(c).splitlines():
            print("  " + line)

    # ---- 7 --------------------------------------------------------------
    head(5, "ANÁLISE DE SENSIBILIDADE ONTOLÓGICA (Tabela 5)")
    print(f"  {'Cenário':<30s}{'LCOH':>7s}  {'Preferred':<10s} VUAV (USD M/ano)")
    for row in sensitivity_table(c):
        v = "  ".join(f"{k}={x:+.1f}" for k, x in row["vuav"].items())
        print(f"  {row['cenario']:<30s}{row['lcoh']:>7.2f}  {row['preferred']:<10s} {v}")

    # ---- 8 --------------------------------------------------------------
    head(6, "CONSISTÊNCIA LÓGICA (HermiT)")
    _, _, owl_path, ttl_path = export(c)
    rep, onto, world = reason(owl_path)
    for k, v in rep.items():
        print(f"  {k:16s}: {v}")
    print("\n  Refinamento de NoInvestmentStrategy (Seção 3.2):")
    ni = check_ni_satisfiable(world)
    for k, v in ni.items():
        if k == "restricoes":
            for r in v:
                print(f"      {r}")
        else:
            print(f"    {k:28s}: {v}")

    # ---- 9 --------------------------------------------------------------
    head(7, "VALIDAÇÃO CONTRA OS VALORES PUBLICADOS")
    cf_par = {x.symbol: x.threshold for x in generate_counterfactuals(c, criterion="parity")}
    obtido = {
        "horas_ativas_ano":    c.horas_ativas,
        "ciclos_ano":          c.ciclos_ano,
        "producao_h2_t":       c.producao_h2_kg / 1000.0,
        "energia_bess_mwh":    c.energia_bess_mwh,
        "eta_impl":            c.eta_impl,
        "receita_h2_musd":     c.producao_h2_kg * c.preco_h2_usd_kg / 1e6,
        "custo_h2_musd":       c.producao_h2_kg * c.lcoh_efetivo() / 1e6,
        "receita_bess_musd":   c.energia_bess_mwh * c.pld_arbitragem_usd_mwh / 1e6,
        "custo_bess_musd":     c.energia_bess_mwh * c.lcos_usd_mwh / 1e6,
        "vuav_h2v_musd":       results["rn_h2v_strategy"].value / 1e6,
        "vuav_bess_musd":      results["rn_bess_strategy"].value / 1e6,
        "limiar_capex_usd_kw": cf_par.get("CAPEX_AWE"),
        "limiar_clog_usd_kg":  cf_par.get("c_log"),
        "limiar_pld_usd_mwh":  cf_par.get("PLD"),
        "limiar_lcos_usd_mwh": cf_par.get("LCOS"),
        "limiar_fc":           cf_par.get("FC"),
    }
    ok = div = 0
    print(f"  {'Grandeza':<24s}{'publicado':>14s}{'obtido':>14s}{'Δ':>12s}   status")
    for k, (pub, tol, unit) in PUBLICADO.items():
        got = obtido[k]
        if got is None:
            print(f"  {k:<24s}{pub:>14,.4g}{'—':>14s}{'—':>12s}   NÃO AVALIADO")
            continue
        d = got - pub
        good = abs(d) <= tol
        ok += good
        div += (not good)
        print(f"  {k:<24s}{pub:>14,.4g}{got:>14,.4g}{d:>12,.3g}   "
              f"{'OK' if good else '*** DIVERGE'}")
    print(f"\n  {ok} reproduzidos dentro da tolerância, {div} divergentes.")

    # ---- 10 -------------------------------------------------------------
    head(8, "DIAGNÓSTICO DAS INCONSISTÊNCIAS DO ARTIGO")
    diag = c.diagnostico_lcoh()
    print(json.dumps(diag, indent=4, ensure_ascii=False))
    print("""
  Leitura:
  • O LCOH da Tabela 2 (1,95) e a curva da Figura 10 avaliada no mesmo FC (1,43)
    diferem em 0,52 USD/kg. A diferença é o componente residual não decomposto no
    artigo (energia, reposição de stack, BOP), presente no LCOH do Monte Carlo do
    SBPO e ausente da curva analítica CAPEX+OPEX.
  • Em consequência, o limiar de FC é 34,0% pela curva publicada, 43,0% pelo
    modelo analítico com residual e 46,4% pelo modelo proporcional. Os limiares de
    CAPEX (1.190), c_log (0,55), PLD (145) e LCOS (92) da Tabela 5 são coerentes
    com os dois últimos, não com o primeiro.
  • Recomendação: adotar um único modelo de LCOH e recalcular a Figura 10 e a
    Tabela 5 a partir dele.""")

    head(9, "CRITÉRIO DE REVERSÃO — comparação")
    print("  Os limiares publicados usam o critério de PARIDADE (VUAV da estratégia")
    print("  cruza zero). O critério coerente com a definição de Preferred Bearer")
    print("  adotada no artigo é a COMPARAÇÃO entre VUAV. Os dois só coincidem se o")
    print("  VUAV das demais alternativas for aproximadamente nulo — o que depende")
    print("  da calibração de NI, não publicada.\n")
    print(f"  {'Truthmaker':<12s}{'paridade':>14s}{'comparação VUAV':>20s}")
    cf_cmp = {x.symbol: x.threshold for x in generate_counterfactuals(c, criterion="vuav_ranking")}
    for sym in ("CAPEX_AWE", "FC", "c_log", "PLD", "LCOS"):
        a, b = cf_par.get(sym), cf_cmp.get(sym)
        print(f"  {sym:<12s}{a if a is not None else '—':>14}{b if b is not None else '—':>20}")

    # ---- exportação -----------------------------------------------------
    head(10, "EXPORTAÇÃO")
    payload = {
        "contexto": c.cid,
        "vuav_usd_ano": {STRATEGY_LABEL[s]: r.value for s, r in results.items()},
        "preferred_bearer": exp["preferred_bearer"],
        "deprecated_bearers": exp["deprecated_bearers"],
        "ni_reversal_year": exp["ni_reversal_year"],
        "contrafactuais_paridade": [vars(x) for x in
                                    generate_counterfactuals(c, criterion="parity")],
        "contrafactuais_comparacao": [vars(x) for x in
                                      generate_counterfactuals(c, criterion="vuav_ranking")],
        "sensibilidade": sensitivity_table(c),
        "diagnostico_lcoh": diag,
        "consistencia": rep,
        "refinamento_ni": ni,
        "validacao": {k: {"publicado": v[0], "obtido": obtido[k], "unidade": v[2]}
                      for k, v in PUBLICADO.items()},
    }
    (OUT / "resultados.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    for f in (owl_path, ttl_path, OUT / "resultados.json"):
        print(f"  {f.relative_to(ROOT)}  ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
