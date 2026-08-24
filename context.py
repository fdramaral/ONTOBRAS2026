"""
context.py — Truthmakers primários e derivações do arcabouço SIDE.

Cada truthmaker é declarado com valor, unidade, fonte e classificação ontológica
(técnico / econômico / espacial). Os Gain e Loss Events NÃO são hardcoded: suas
magnitudes são derivadas dos truthmakers primários. Essa é a condição para que os
contrafactuais do ontological unpacking sejam efetivamente computáveis — alterar
um truthmaker recalcula toda a cadeia.

Referência: Amaral, Peixoto, Baião e Maçaira (2026), ONTOBRAS/WTDO, Tabelas 2, 4 e 5.
"""

from dataclasses import dataclass, field, replace
from typing import Optional


# =============================================================================
# 1. TRUTHMAKER
# =============================================================================

@dataclass(frozen=True)
class Truthmaker:
    tid: str                 # identificador local (vira IRI side:tm_...)
    symbol: str              # símbolo usado na dissertação
    label: str
    value: float
    unit: str
    kind: str                # 'technical' | 'economic' | 'spatial'
    source: str
    derived: bool = False
    formula: Optional[str] = None


# =============================================================================
# 2. CONTEXTO DECISÓRIO
# =============================================================================

@dataclass(frozen=True)
class DecisionContext:
    """Truthmakers primários do contexto RN_2025 (Tabela 2 do artigo)."""

    cid: str = "RioGrandeDoNorte_2025"
    label: str = "Rio Grande do Norte, Abr/2024–Mar/2026"

    # --- técnicos -------------------------------------------------------
    fc: float = 0.595                  # fator de capacidade de constrained-off
    kappa: float = 52.5                # kWh/kgH2 (parâmetro primário do AWE)
    eta_rt: float = 0.90               # eficiência round-trip do BESS
    potencia_mw: float = 1000.0        # capacidade sugerida
    duracao_descarga_h: float = 4.0    # BESS 4h
    capacidade_instalada_mw: float = 11700.0
    mwmed_janelas: float = 1847.0
    coff_eolico_gwh: float = 18442.0   # 24 meses
    hhv_h2: float = 39.4               # kWh/kg (para η_impl = HHV/κ)

    # --- econômicos -----------------------------------------------------
    capex_awe_usd_kw: float = 850.0
    capex_bess_usd_kwh: float = 320.0
    opex_awe_frac: float = 0.02
    opex_bess_frac: float = 0.015
    lcoh_usd_kg: float = 1.95
    lcos_usd_mwh: float = 145.0
    preco_h2_usd_kg: float = 2.50      # paridade com H2 cinza
    pld_arbitragem_usd_mwh: float = 92.0
    wacc: float = 0.12
    vida_util_anos: int = 20
    fcr: float = 0.1468                # fixed charge rate

    # --- espaciais ------------------------------------------------------
    distancia_porto_km: float = 250.0  # Pecém/CE
    custo_logistico_usd_kg: float = 0.0   # 0 no caso-base; 0.55 no cenário logístico
    infra_portuaria_h2: bool = False

    # --- calibração do VUAV para a alternativa NI -----------------------
    # ATENÇÃO: o artigo qualifica VUAV(NI) como "positivo transitório" sem
    # publicar os valores de L, I e S. Os parâmetros abaixo são uma CALIBRAÇÃO
    # EXPLÍCITA desta implementação, não um resultado do artigo. Devem ser
    # confirmados ou substituídos antes de qualquer uso na dissertação.
    ni_l_capex_preservation: float = 1.00
    ni_l_techlockin: float = 0.60
    ni_i_techlockin_usd: float = 25.0e6
    ni_l_regulatory: float = 0.50
    ni_i_regulatory_usd: float = 15.0e6
    ni_l_oportunidade_t0: float = 0.30     # L(RevenueOpportunityLoss) no ano 1
    ni_l_oportunidade_growth: float = 0.05 # crescimento anual da likelihood

    # --- modelo de LCOH -------------------------------------------------
    # 'analytic_residual' : LCOH = (CAPEX×FCR + OPEX) / (8760×FC/κ) + Δ_res
    #                       Δ_res é o componente residual (energia, reposição de
    #                       stack, BOP) calibrado para reproduzir LCOH=1,95 no
    #                       ponto-base. Responde a CAPEX e a FC.
    # 'proportional'      : LCOH = 1,95 × (CAPEX/850) × (0,595/FC)
    #                       Modelo implícito na Tabela 5 do artigo (reproduz
    #                       exatamente USD 2,73/kg em CAPEX = USD 1.190/kW).
    # 'fixed'             : LCOH constante — não responde a contrafactuais.
    lcoh_model: str = "analytic_residual"

    # ------------------------------------------------------------------
    # DERIVAÇÕES
    # ------------------------------------------------------------------

    @property
    def horas_ativas(self) -> float:
        """Horas de operação ativas por ano = 8.760 × FC."""
        return 8760.0 * self.fc

    @property
    def ciclos_ano(self) -> float:
        """Ciclos completos/ano do BESS = horas ativas ÷ duração de descarga."""
        return self.horas_ativas / self.duracao_descarga_h

    @property
    def eta_impl(self) -> float:
        """Eficiência implícita do stack: η_impl = HHV_H2 / κ."""
        return self.hhv_h2 / self.kappa

    @property
    def producao_h2_kg(self) -> float:
        """Produção anual de H2 = P[MW] × h × 1000 ÷ κ."""
        return self.potencia_mw * self.horas_ativas * 1000.0 / self.kappa

    @property
    def energia_bess_mwh(self) -> float:
        """Energia anual entregue pelo BESS = P[MW] × h × η_RT."""
        return self.potencia_mw * self.horas_ativas * self.eta_rt

    @property
    def capex_awe_total(self) -> float:
        return self.capex_awe_usd_kw * self.potencia_mw * 1000.0

    @property
    def capex_bess_total(self) -> float:
        return self.capex_bess_usd_kwh * self.potencia_mw * self.duracao_descarga_h * 1000.0

    # --- modelo de LCOH -------------------------------------------------

    @property
    def custo_anualizado_usd_kw(self) -> float:
        """CAPEX×FCR + OPEX, em USD/kW-ano. No ponto-base: 850×0,1468 + 17 = 141,78."""
        return self.capex_awe_usd_kw * (self.fcr + self.opex_awe_frac)

    def kg_por_kw_ano(self, fc: float) -> float:
        """Produção específica de H2 por kW instalado: 8760×FC/κ. Base: 166,86×FC."""
        return 8760.0 * fc / self.kappa

    def lcoh_analitico(self, fc: float = None, capex: float = None) -> float:
        fc = self.fc if fc is None else fc
        capex = self.capex_awe_usd_kw if capex is None else capex
        return capex * (self.fcr + self.opex_awe_frac) / self.kg_por_kw_ano(fc)

    @property
    def lcoh_residual(self) -> float:
        """
        Δ_res: diferença entre o LCOH da Tabela 2 (Monte Carlo do SBPO, que
        incorpora custo de energia, reposição de stack e BOP) e o LCOH analítico
        que considera apenas CAPEX e OPEX. Calibrado no ponto-base do artigo.
        """
        base = DecisionContext.__dataclass_fields__
        fc0 = base["fc"].default
        capex0 = base["capex_awe_usd_kw"].default
        lcoh0 = base["lcoh_usd_kg"].default
        analitico0 = capex0 * (self.fcr + self.opex_awe_frac) / (8760.0 * fc0 / self.kappa)
        return lcoh0 - analitico0

    def lcoh_efetivo(self, fc: float = None, capex: float = None) -> float:
        """LCOH sob o modelo selecionado, respondendo a FC e CAPEX."""
        fc = self.fc if fc is None else fc
        capex = self.capex_awe_usd_kw if capex is None else capex
        if self.lcoh_model == "analytic_residual":
            return self.lcoh_analitico(fc, capex) + self.lcoh_residual
        if self.lcoh_model == "proportional":
            f = DecisionContext.__dataclass_fields__
            return (f["lcoh_usd_kg"].default
                    * (capex / f["capex_awe_usd_kw"].default)
                    * (f["fc"].default / fc))
        if self.lcoh_model == "fixed":
            return self.lcoh_usd_kg
        raise ValueError(f"modelo de LCOH desconhecido: {self.lcoh_model}")

    @property
    def lcoh_total(self) -> float:
        """LCOH efetivo + custo logístico (LogisticsDistanceVulnerability)."""
        return self.lcoh_efetivo() + self.custo_logistico_usd_kg

    # --- diagnóstico das inconsistências conhecidas ---------------------

    def fc_de_paridade(self, model: str = None) -> float:
        """FC em que LCOH atinge a paridade com o H2 cinza, por bissecção."""
        model = model or self.lcoh_model
        c = replace(self, lcoh_model=model)
        lo, hi = 0.01, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if c.lcoh_efetivo(fc=mid) > self.preco_h2_usd_kg:
                lo = mid
            else:
                hi = mid
        return round((lo + hi) / 2, 4)

    def capex_de_paridade(self, model: str = None) -> float:
        model = model or self.lcoh_model
        c = replace(self, lcoh_model=model)
        lo, hi = 100.0, 5000.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if c.lcoh_efetivo(capex=mid) < self.preco_h2_usd_kg:
                lo = mid
            else:
                hi = mid
        return round((lo + hi) / 2, 2)

    def diagnostico_lcoh(self) -> dict:
        """
        Reúne as divergências entre os limiares publicados e os recalculados.
        Serve de insumo para a harmonização prevista para a versão final.
        """
        curva_fig10 = 141.78 / (166.86 * 0.595)
        return {
            "lcoh_tabela2_usd_kg": self.lcoh_usd_kg,
            "lcoh_analitico_capex_opex_usd_kg": round(self.lcoh_analitico(), 4),
            "residual_delta_usd_kg": round(self.lcoh_residual, 4),
            "curva_fig10_em_fc_0595": round(curva_fig10, 4),
            "fc_paridade": {
                "curva_fig10_publicada": 0.34,
                "analytic_residual": self.fc_de_paridade("analytic_residual"),
                "proportional": self.fc_de_paridade("proportional"),
            },
            "capex_paridade_usd_kw": {
                "publicado_tabela5": 1190.0,
                "analytic_residual": self.capex_de_paridade("analytic_residual"),
                "proportional": self.capex_de_paridade("proportional"),
            },
            "lcoh_em_capex_1190": {
                "publicado_tabela5": 2.73,
                "analytic_residual": round(
                    replace(self, lcoh_model="analytic_residual").lcoh_efetivo(capex=1190.0), 4),
                "proportional": round(
                    replace(self, lcoh_model="proportional").lcoh_efetivo(capex=1190.0), 4),
            },
        }

    def with_(self, **kwargs) -> "DecisionContext":
        """Retorna uma cópia do contexto com truthmakers alterados (contrafactual)."""
        return replace(self, **kwargs)

    # ------------------------------------------------------------------
    # TRUTHMAKERS COMO ENTIDADES DO GRAFO
    # ------------------------------------------------------------------

    def truthmakers(self) -> list:
        T, E, S = "technical", "economic", "spatial"
        ons = "ONS (2026a); Amaral, Baião e Maçaira (2026)"
        return [
            # técnicos
            Truthmaker("tm_fc_595", "FC", "Fator de capacidade de constrained-off",
                       self.fc, "adimensional", T, ons),
            Truthmaker("tm_kappa_525", "κ", "Consumo específico do eletrolisador AWE",
                       self.kappa, "kWh/kgH2", T, "IRENA (2020a)"),
            Truthmaker("tm_eta_impl", "η_impl", "Eficiência implícita do stack (HHV/κ)",
                       round(self.eta_impl, 4), "adimensional", T, "IRENA (2020a)",
                       derived=True, formula="HHV_H2 / κ"),
            Truthmaker("tm_eta_rt_090", "η_RT", "Eficiência round-trip do BESS",
                       self.eta_rt, "adimensional", T, "NREL (2023)"),
            Truthmaker("tm_potencia_1000", "P", "Capacidade sugerida do ativo",
                       self.potencia_mw, "MW", T, "elaboração própria"),
            Truthmaker("tm_horas_ativas", "h", "Horas de operação ativas por ano",
                       round(self.horas_ativas, 1), "h/ano", T, ons,
                       derived=True, formula="8760 × FC"),
            Truthmaker("tm_ciclos_ano", "n_ciclos", "Ciclos completos por ano do BESS",
                       round(self.ciclos_ano, 1), "ciclos/ano", T, "Schmidt et al. (2017)",
                       derived=True, formula="h ÷ duração de descarga"),
            Truthmaker("tm_coff_eolico", "E_coff", "Constrained-off eólico acumulado (24 meses)",
                       self.coff_eolico_gwh, "GWh", T, "ONS (2026a)"),
            Truthmaker("tm_mwmed_janelas", "P_med", "Potência média nas horas com corte",
                       self.mwmed_janelas, "MWmed", T, "ONS (2026a)"),
            Truthmaker("tm_capacidade_instalada", "C_inst", "Capacidade instalada eólica + solar",
                       self.capacidade_instalada_mw, "MW", T, "ANEEL (2026)"),
            # econômicos
            Truthmaker("tm_capex_awe_850", "CAPEX_AWE", "CAPEX unitário do eletrolisador",
                       self.capex_awe_usd_kw, "USD/kW", E, "IRENA (2020a)"),
            Truthmaker("tm_capex_bess_320", "CAPEX_BESS", "CAPEX unitário do BESS",
                       self.capex_bess_usd_kwh, "USD/kWh", E, "NREL (2023)"),
            Truthmaker("tm_lcoh_195", "LCOH", "Custo nivelado do hidrogênio (cenário S1)",
                       self.lcoh_usd_kg, "USD/kgH2", E, "Amaral, Baião e Maçaira (2026)"),
            Truthmaker("tm_lcos_145", "LCOS", "Custo nivelado de armazenamento em alta ciclagem",
                       self.lcos_usd_mwh, "USD/MWh", E, "Schmidt et al. (2017)"),
            Truthmaker("tm_paridade_h2_250", "P_H2", "Paridade com o H2 cinza",
                       self.preco_h2_usd_kg, "USD/kgH2", E, "IRENA (2020a)"),
            Truthmaker("tm_pld_arbitragem_92", "PLD", "Benefício unitário de arbitragem",
                       self.pld_arbitragem_usd_mwh, "USD/MWh", E, "CCEE (2026)"),
            Truthmaker("tm_wacc_012", "WACC", "Custo médio ponderado de capital",
                       self.wacc, "adimensional", E, "elaboração própria"),
            Truthmaker("tm_fcr_1468", "FCR", "Fixed charge rate (WACC=12%, n=20)",
                       self.fcr, "adimensional", E, "elaboração própria", derived=True,
                       formula="WACC(1+WACC)^n / ((1+WACC)^n − 1)"),
            # espaciais
            Truthmaker("tm_distancia_pecem", "d_porto", "Distância ao porto de exportação (Pecém/CE)",
                       self.distancia_porto_km, "km", S, "elaboração própria"),
            Truthmaker("tm_custo_logistico", "c_log", "Custo logístico unitário de escoamento do H2",
                       self.custo_logistico_usd_kg, "USD/kgH2", S, "IRENA (2019)"),
            Truthmaker("tm_infra_portuaria", "I_porto", "Disponibilidade de infraestrutura portuária de H2",
                       1.0 if self.infra_portuaria_h2 else 0.0, "booleano", S, "Sedec-RN (2025)"),
        ]


RN_2025 = DecisionContext()
