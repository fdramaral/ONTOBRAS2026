"""
abox.py — Instanciação do grafo RDF a partir de um DecisionContext.

Popula: truthmakers, EnergyInvestor e suas Intentions, CurtailmentWindow,
FeasibilityStudy, as três EnergyStrategy, as EnergyInvestmentDecision e as
cadeias Capability → Gain Event → Intention e Vulnerability → Loss Event →
Intention, com os parâmetros L(·), I(·) e S(·) da função VUAV.

Referência: ONTOBRAS/WTDO 2026, Seções 3.1–3.3 e 5.1–5.3; Figura 5.
"""

from rdflib import Graph, Namespace, Literal, RDF, RDFS, XSD, URIRef, OWL
from rdflib.namespace import SKOS
from pathlib import Path

from context import DecisionContext, RN_2025

UFO   = Namespace("http://purl.org/side/ufo#")
COVER = Namespace("http://purl.org/side/cover#")
SIDE  = Namespace("http://purl.org/side/energy#")

TM_KIND = {
    "technical": SIDE.TechnicalTruthmaker,
    "economic":  SIDE.EconomicTruthmaker,
    "spatial":   SIDE.SpatialTruthmaker,
}


def _f(x):
    return Literal(float(x), datatype=XSD.float)


def build_abox(ctx: DecisionContext = RN_2025) -> Graph:
    g = Graph()
    g.bind("ufo", UFO); g.bind("cover", COVER); g.bind("side", SIDE)
    g.bind("skos", SKOS)

    ctx_uri = SIDE[ctx.cid]
    g.add((ctx_uri, RDF.type, SIDE.DecisionContext))
    g.add((ctx_uri, RDFS.label, Literal(ctx.label, lang="pt")))

    # ---------------------------------------------------------------- #
    # 1. Truthmakers e o TruthmakerSet
    # ---------------------------------------------------------------- #
    tmset = SIDE["rn_2025_tmset"]
    g.add((tmset, RDF.type, COVER.TruthmakerSet))
    g.add((tmset, SIDE.hasContext, ctx_uri))

    tm_uri = {}
    for tm in ctx.truthmakers():
        u = SIDE[tm.tid]
        tm_uri[tm.tid] = u
        g.add((u, RDF.type, TM_KIND[tm.kind]))
        g.add((u, RDFS.label, Literal(tm.label, lang="pt")))
        g.add((u, SIDE.hasSymbol, Literal(tm.symbol)))
        g.add((u, COVER.hasValue, _f(tm.value)))
        g.add((u, COVER.hasUnit, Literal(tm.unit)))
        g.add((u, SIDE.hasSourceCitation, Literal(tm.source)))
        g.add((u, SIDE.isDerived, Literal(tm.derived, datatype=XSD.boolean)))
        if tm.formula:
            g.add((u, SIDE.derivationFormula, Literal(tm.formula)))
        g.add((tmset, COVER.hasMember, u))

    # FeasibilityStudy — artefato informacional que qualifica os truthmakers
    fs = SIDE["rn_2025_feasibility_study"]
    g.add((fs, RDF.type, SIDE.FeasibilityStudy))
    g.add((fs, RDFS.label, Literal("Estudo de viabilidade RN 2025", lang="pt")))
    g.add((fs, SIDE.hasContext, ctx_uri))
    for u in tm_uri.values():
        g.add((fs, SIDE.qualifies, u))

    # ---------------------------------------------------------------- #
    # 2. Investidor e Intentions
    # ---------------------------------------------------------------- #
    inv = SIDE["rn_industrial_investor"]
    g.add((inv, RDF.type, SIDE.IndustrialInvestor))
    g.add((inv, RDFS.label, Literal("Investidor industrial (RN)", lang="pt")))
    intentions = {
        "int_high_revenue":  SIDE.HighRevenueIntention,
        "int_high_profit":   SIDE.HighProfitIntention,
        "int_low_cost":      SIDE.LowCostIntention,
        "int_fin_flex":      SIDE.FinancialFlexibilityIntention,
        "int_strat_flex":    SIDE.StrategicFlexibilityIntention,
        "int_compliance":    SIDE.ComplianceCertaintyIntention,
    }
    int_uri = {}
    for k, cls in intentions.items():
        u = SIDE[k]; int_uri[k] = u
        g.add((u, RDF.type, cls))
        g.add((inv, COVER.hasIntention, u))

    # ---------------------------------------------------------------- #
    # 3. CurtailmentWindow — Value Enabler e Risk Enabler simultaneamente
    # ---------------------------------------------------------------- #
    win = SIDE["rn_curtailment_window"]
    g.add((win, RDF.type, SIDE.CurtailmentWindow))
    g.add((win, RDFS.label, Literal("Janela de constrained-off RN 2024–2026", lang="pt")))
    g.add((win, SIDE.hasContext, ctx_uri))
    g.add((win, SIDE.groundedInTruthmaker, tm_uri["tm_fc_595"]))
    g.add((win, SIDE.groundedInTruthmaker, tm_uri["tm_horas_ativas"]))

    # ---------------------------------------------------------------- #
    # 4. Helpers
    # ---------------------------------------------------------------- #
    def gain(gid, cls, likelihood, impact, intention_key, grounded, label):
        u = SIDE[gid]
        g.add((u, RDF.type, cls))
        g.add((u, RDF.type, COVER.GainEvent))
        g.add((u, RDFS.label, Literal(label, lang="pt")))
        g.add((u, COVER.hasLikelihood, _f(likelihood)))
        g.add((u, COVER.hasImpact, _f(impact)))
        g.add((u, COVER.impactsPositively, int_uri[intention_key]))
        g.add((u, SIDE.occursIn, win))
        for t in grounded:
            g.add((u, SIDE.groundedInTruthmaker, tm_uri[t]))
        return u

    def loss(lid, cls, likelihood, severity, intention_key, grounded, label,
             growth=0.0):
        u = SIDE[lid]
        g.add((u, RDF.type, cls))
        g.add((u, RDF.type, COVER.LossEvent))
        g.add((u, RDFS.label, Literal(label, lang="pt")))
        g.add((u, COVER.hasLikelihood, _f(likelihood)))
        g.add((u, COVER.hasSeverity, _f(severity)))
        g.add((u, COVER.impactsNegatively, int_uri[intention_key]))
        g.add((u, SIDE.occursIn, win))
        if growth:
            g.add((u, SIDE.hasLikelihoodGrowthRate, _f(growth)))
        for t in grounded:
            g.add((u, SIDE.groundedInTruthmaker, tm_uri[t]))
        return u

    def capability(cid_, cls, strategy, manifests, label):
        u = SIDE[cid_]
        g.add((u, RDF.type, cls)); g.add((u, RDF.type, COVER.Capability))
        g.add((u, RDFS.label, Literal(label, lang="pt")))
        g.add((u, COVER.inheresIn, strategy))
        g.add((strategy, COVER.hasCapability, u))
        for m in manifests:
            g.add((u, COVER.manifestsAs, m))
        return u

    def vulnerability(vid, cls, strategy, produces, label, active=True,
                      threat_situation=None, threatens=()):
        u = SIDE[vid]
        g.add((u, RDF.type, cls)); g.add((u, RDF.type, COVER.Vulnerability))
        g.add((u, RDFS.label, Literal(label, lang="pt")))
        g.add((u, COVER.inheresIn, strategy))
        g.add((strategy, COVER.hasVulnerability, u))
        g.add((u, SIDE.isActive, Literal(active, datatype=XSD.boolean)))
        for p in produces:
            g.add((u, COVER.produces, p))
        for gev in threatens:
            g.add((u, SIDE.threatens, gev))
        if threat_situation is not None:
            ts = SIDE[f"{vid}_situation"]
            g.add((ts, RDF.type, threat_situation))
            g.add((u, COVER.isActivatedBy, ts))
        return u

    def decision(did, strategy, vuav_value, trigger_cls, trigger_label):
        d = SIDE[did]
        g.add((d, RDF.type, SIDE.EnergyInvestmentDecision))
        g.add((d, COVER.mediates, inv))
        g.add((d, COVER.mediates, strategy))
        g.add((d, COVER.isGroundedIn, tmset))
        nuv = SIDE[f"{did}_netusevalue"]
        g.add((nuv, RDF.type, COVER.NetUseValue))
        g.add((nuv, COVER.hasValue, _f(vuav_value)))
        g.add((nuv, COVER.hasUnit, Literal("USD/ano")))
        g.add((d, SIDE.hasVUAV, nuv))
        trg = SIDE[f"{did}_trigger"]
        g.add((trg, RDF.type, trigger_cls)); g.add((trg, RDF.type, COVER.TriggerEvent))
        g.add((trg, RDFS.label, Literal(trigger_label, lang="pt")))
        g.add((trg, SIDE.occursIn, win))
        g.add((d, COVER.triggeredBy, trg))
        return d

    # ---------------------------------------------------------------- #
    # 5. Estratégia NI
    # ---------------------------------------------------------------- #
    s_ni = SIDE["rn_ni_strategy"]
    g.add((s_ni, RDF.type, SIDE.NoInvestmentStrategy))
    g.add((s_ni, RDFS.label, Literal("Não investir (RN 2025)", lang="pt")))

    ge_capex = gain("ge_capex_preservation", SIDE.CapexPreservationGain,
                    ctx.ni_l_capex_preservation,
                    ctx.capex_awe_total * ctx.wacc,
                    "int_fin_flex", ["tm_capex_awe_850", "tm_wacc_012"],
                    "Preservação de CAPEX — custo de oportunidade do capital não imobilizado")
    ge_lockin = gain("ge_techlockin_avoidance", SIDE.TechLockInAvoidanceGain,
                     ctx.ni_l_techlockin, ctx.ni_i_techlockin_usd,
                     "int_strat_flex", ["tm_capex_awe_850", "tm_capex_bess_320"],
                     "Evitação de lock-in tecnológico")
    ge_reg = gain("ge_regulatory_avoidance", SIDE.RegulatoryRiskAvoidanceGain,
                  ctx.ni_l_regulatory, ctx.ni_i_regulatory_usd,
                  "int_compliance", [],
                  "Evitação de exposição a marco regulatório incipiente")

    le_oport = loss("le_revenue_opportunity", SIDE.RevenueOpportunityLoss,
                    ctx.ni_l_oportunidade_t0,
                    ctx.producao_h2_kg * ctx.preco_h2_usd_kg,
                    "int_high_revenue",
                    ["tm_fc_595", "tm_horas_ativas", "tm_coff_eolico"],
                    "Receita não capturada nas janelas de constrained-off",
                    growth=ctx.ni_l_oportunidade_growth)

    capability("cap_financial_flexibility", SIDE.FinancialFlexibilityCapability,
               s_ni, [ge_capex], "Preservação de flexibilidade financeira")
    capability("cap_techlockin_avoidance", SIDE.TechLockInAvoidanceCapability,
               s_ni, [ge_lockin], "Evitação de lock-in tecnológico")
    capability("cap_regulatory_avoidance", SIDE.RegulatoryRiskAvoidanceCapability,
               s_ni, [ge_reg], "Evitação de risco regulatório")
    v_oport = vulnerability("vul_opportunity_cost", SIDE.OpportunityCostVulnerability,
                            s_ni, [le_oport],
                            "Custo de oportunidade das janelas não aproveitadas",
                            active=True,
                            threat_situation=SIDE.GenerationCapacityConstrainedByCurtailment)
    # A OpportunityCostVulnerability inere na própria CurtailmentWindow (Seção 3.2)
    g.add((v_oport, COVER.inheresIn, win))

    decision("rn_ni_decision", s_ni, 0.0, SIDE.CurtailmentWithNoInvestment,
             "Constrained-off sem investimento")

    # ---------------------------------------------------------------- #
    # 6. Estratégia H2V
    # ---------------------------------------------------------------- #
    s_h2 = SIDE["rn_h2v_strategy"]
    g.add((s_h2, RDF.type, SIDE.H2VStrategy))
    g.add((s_h2, RDFS.label, Literal("Hidrogênio verde 1.000 MW (AWE)", lang="pt")))

    ge_h2 = gain("ge_h2_production", SIDE.H2ProductionGain, 1.0,
                 ctx.producao_h2_kg * ctx.preco_h2_usd_kg,
                 "int_high_revenue",
                 ["tm_fc_595", "tm_kappa_525", "tm_potencia_1000",
                  "tm_horas_ativas", "tm_paridade_h2_250"],
                 "Receita bruta de venda de H2 à paridade com o H2 cinza")
    le_h2 = loss("le_electrolyzer_cost", SIDE.ElectrolyzerInvestmentCost, 1.0,
                 ctx.producao_h2_kg * ctx.lcoh_efetivo(),
                 "int_low_cost",
                 ["tm_lcoh_195", "tm_capex_awe_850", "tm_kappa_525"],
                 "Custo nivelado de produção de H2 (LCOH × produção)")

    capability("cap_h2_production", SIDE.H2ProductionCapability, s_h2, [ge_h2],
               "Conversão de energia excedente em H2 durante a CurtailmentWindow")
    # A IntermittentCurtailmentVulnerability não produz Loss Event próprio: sua
    # manifestação converte o H2ProductionGain em Loss ao elevar o LCOH acima da
    # paridade. Representada por side:threatens.
    vulnerability("vul_intermittent_curtailment", SIDE.IntermittentCurtailmentVulnerability,
                  s_h2, [], "Dependência do FC para a viabilidade econômica",
                  active=(ctx.fc <= ctx.fc_de_paridade()),
                  threat_situation=SIDE.ElectrolyzerInvestmentNeed,
                  threatens=[ge_h2])
    # O custo nivelado de produção é incorrido em todo exercício: a
    # CapexIntensityVulnerability está sempre manifesta.
    vulnerability("vul_capex_intensity", SIDE.CapexIntensityVulnerability,
                  s_h2, [le_h2], "Imobilização de capital em ativo específico",
                  active=True, threat_situation=SIDE.H2PriceInstability)

    le_log = loss("le_logistics", SIDE.LogisticsLoss,
                  1.0 if ctx.custo_logistico_usd_kg > 0 else 0.0,
                  ctx.producao_h2_kg * ctx.custo_logistico_usd_kg,
                  "int_low_cost", ["tm_custo_logistico", "tm_distancia_pecem"],
                  "Custo de escoamento do H2 ao porto de exportação")
    vulnerability("vul_logistics_distance", SIDE.LogisticsDistanceVulnerability,
                  s_h2, [le_log], "Distância e ausência de infraestrutura portuária de H2",
                  active=(ctx.custo_logistico_usd_kg > 0.0))

    decision("rn_h2v_decision", s_h2, 0.0, SIDE.CurtailmentWithElectrolyzerInvestment,
             "Constrained-off com investimento em eletrolisador")

    # ---------------------------------------------------------------- #
    # 7. Estratégia BESS
    # ---------------------------------------------------------------- #
    s_bess = SIDE["rn_bess_strategy"]
    g.add((s_bess, RDF.type, SIDE.BESSStrategy))
    g.add((s_bess, RDFS.label, Literal("BESS 4.000 MWh (1.000 MW × 4 h)", lang="pt")))

    ge_arb = gain("ge_arbitrage", SIDE.ArbitrageGain, 1.0,
                  ctx.energia_bess_mwh * ctx.pld_arbitragem_usd_mwh,
                  "int_high_profit",
                  ["tm_eta_rt_090", "tm_pld_arbitragem_92", "tm_horas_ativas"],
                  "Receita de arbitragem de energia armazenada")
    le_bess = loss("le_battery_degradation", SIDE.BatteryDegradationLoss, 1.0,
                   ctx.energia_bess_mwh * ctx.lcos_usd_mwh,
                   "int_low_cost",
                   ["tm_lcos_145", "tm_ciclos_ano", "tm_capex_bess_320"],
                   "Custo nivelado de armazenamento sob alta ciclagem (LCOS × energia)")

    capability("cap_energy_arbitrage", SIDE.EnergyArbitrageCapability, s_bess, [ge_arb],
               "Absorção do excedente e reinjeção em períodos de escassez")
    vulnerability("vul_high_cycling", SIDE.HighCyclingDegradationVulnerability,
                  s_bess, [le_bess],
                  "Degradação acelerada por alta ciclagem",
                  active=True,
                  threat_situation=SIDE.BatteryInvestmentNeed)
    vulnerability("vul_low_pld_arbitrage", SIDE.LowPLDArbitrageVulnerability,
                  s_bess, [],
                  "PLD de despacho insuficiente para cobrir o LCOS",
                  active=(ctx.pld_arbitragem_usd_mwh < ctx.lcos_usd_mwh),
                  threatens=[ge_arb])

    decision("rn_bess_decision", s_bess, 0.0, SIDE.CurtailmentWithBatteryInvestment,
             "Constrained-off com investimento em baterias")

    # Tipagem explícita como owl:NamedIndividual — exigida pelo Protégé e pelos
    # reasoners OWL 2 DL para distinguir indivíduos de classes.
    for subj in set(g.subjects(RDF.type, None)):
        if isinstance(subj, URIRef) and str(subj).startswith(str(SIDE)):
            if (None, RDFS.subClassOf, subj) in g or (subj, RDFS.subClassOf, None) in g:
                continue
            g.add((subj, RDF.type, OWL.NamedIndividual))

    return g


DECISIONS = {
    "rn_ni_decision":   "rn_ni_strategy",
    "rn_h2v_decision":  "rn_h2v_strategy",
    "rn_bess_decision": "rn_bess_strategy",
}


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "ontology" / "rn_2025_abox.ttl"
    g = build_abox()
    g.serialize(destination=str(out), format="turtle")
    print(f"ABox serializada em {out} — {len(g)} triplas")
