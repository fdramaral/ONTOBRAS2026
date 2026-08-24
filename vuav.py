"""
vuav.py — Cálculo determinístico do VUAV e ontological unpacking.

    VUAV(s, ctx) = Σᵢ [ L(GEᵢ|ctx) × I(GEᵢ) ] − Σⱼ [ L(LEⱼ|s,ctx) × S(LEⱼ) ]

O cálculo é feito a partir dos parâmetros recuperados do grafo RDF por consulta
SPARQL — nunca de constantes embutidas no código. A estratégia com maior VUAV é
a Preferred Bearer; as demais são Deprecated Bearers.

Referência: ONTOBRAS/WTDO 2026, Seções 3.3, 3.4 e 5.3–5.5.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rdflib import Graph, Namespace, Literal, XSD, URIRef

from context import DecisionContext, RN_2025
from abox import build_abox, SIDE, COVER

QDIR = Path(__file__).resolve().parents[1] / "queries"
ODIR = Path(__file__).resolve().parents[1] / "ontology"


def load_query(name: str) -> str:
    prefixes = (QDIR / "_prefixes.rq").read_text(encoding="utf-8")
    body = (QDIR / name).read_text(encoding="utf-8")
    return prefixes + "\n" + body


def load_graph(ctx: DecisionContext = RN_2025) -> Graph:
    """TBox + ABox instanciada a partir do contexto."""
    g = Graph()
    g.parse(str(ODIR / "side_tbox.ttl"), format="turtle")
    g += build_abox(ctx)
    return g


# =============================================================================
# 1. Termos e resultado
# =============================================================================

@dataclass
class Term:
    kind: str          # 'gain' | 'loss'
    event: str
    likelihood: float
    magnitude: float
    growth: float = 0.0

    def contribution(self, t: int = 0) -> float:
        lik = min(1.0, self.likelihood + self.growth * t)
        signed = 1.0 if self.kind == "gain" else -1.0
        return signed * lik * self.magnitude


@dataclass
class VUAVResult:
    strategy: str
    terms: list
    value: float
    bearer_status: str = ""

    @property
    def gains(self):
        return [t for t in self.terms if t.kind == "gain"]

    @property
    def losses(self):
        return [t for t in self.terms if t.kind == "loss"]

    def at_year(self, t: int) -> float:
        return sum(term.contribution(t) for term in self.terms)


def _short(uri) -> str:
    return str(uri).split("#")[-1]


# =============================================================================
# 2. Cálculo do VUAV a partir do grafo
# =============================================================================

def compute_vuav(g: Graph, t: int = 0) -> dict:
    """Recupera L, I e S por SPARQL e computa o VUAV de cada estratégia."""
    rows = g.query(load_query("q1_vuav_parameters.rq"))

    by_strategy: dict = {}
    for r in rows:
        s = _short(r.strategy)
        term = Term(
            kind=str(r.termType),
            event=_short(r.event),
            likelihood=float(r.likelihood),
            magnitude=float(r.magnitude),
            growth=float(r.growth) if r.growth is not None else 0.0,
        )
        by_strategy.setdefault(s, []).append(term)

    results = {}
    for s, terms in by_strategy.items():
        # deduplica (a UNION pode retornar o mesmo evento por caminhos distintos)
        uniq = {tm.event: tm for tm in terms}
        terms = list(uniq.values())
        results[s] = VUAVResult(strategy=s, terms=terms,
                                value=sum(tm.contribution(t) for tm in terms))

    ranking = sorted(results.values(), key=lambda r: r.value, reverse=True)
    for i, r in enumerate(ranking):
        r.bearer_status = "PreferredBearer" if i == 0 else "DeprecatedBearer"
    return {r.strategy: r for r in ranking}


def write_vuav_to_graph(g: Graph, results: dict) -> Graph:
    """Materializa os VUAV calculados e o bearer status no grafo (Figura 5)."""
    from abox import DECISIONS
    strat_to_dec = {v: k for k, v in DECISIONS.items()}
    for strategy, res in results.items():
        did = strat_to_dec.get(strategy)
        if not did:
            continue
        nuv = SIDE[f"{did}_netusevalue"]
        g.remove((nuv, COVER.hasValue, None))
        g.add((nuv, COVER.hasValue, Literal(float(res.value), datatype=XSD.float)))
        status = COVER.PreferredBearer if res.bearer_status == "PreferredBearer" \
            else COVER.DeprecatedBearer
        bearer = SIDE[f"{strategy}_bearer"]
        g.remove((SIDE[strategy], SIDE.hasBearerStatus, None))
        g.add((bearer, __import__("rdflib").RDF.type, status))
        g.add((SIDE[strategy], SIDE.hasBearerStatus, bearer))
    return g


def evaluate(ctx: DecisionContext = RN_2025, t: int = 0):
    """Pipeline completo: grafo -> SPARQL -> VUAV -> materialização."""
    g = load_graph(ctx)
    results = compute_vuav(g, t=t)
    write_vuav_to_graph(g, results)
    return g, results


# =============================================================================
# 3. Ontological unpacking — contrafactuais
# =============================================================================

@dataclass
class Counterfactual:
    truthmaker: str
    symbol: str
    baseline: float
    threshold: float
    direction: str        # 'geq' | 'leq'
    unit: str
    new_preferred: str
    mechanism: str

    def statement(self) -> str:
        op = "≥" if self.direction == "geq" else "≤"
        return (f"{self.symbol} {op} {self.threshold:,.2f} {self.unit} "
                f"(base: {self.baseline:,.2f}) → Preferred Bearer passa a ser "
                f"{self.new_preferred}")


def _preferred(ctx: DecisionContext, t: int = 0) -> str:
    _, res = evaluate(ctx, t=t)
    return next(iter(res))


def _vuav_of(ctx: DecisionContext, strategy: str, t: int = 0) -> float:
    _, res = evaluate(ctx, t=t)
    r = res.get(strategy)
    return r.value if r else float("nan")


def _bisect(predicate, lo: float, hi: float, tol: float = 1e-4):
    """
    Menor |valor| em [lo, hi] a partir do qual predicate(valor) é verdadeiro.
    Assume predicate monotônico no intervalo. Retorna None se nunca ocorre.
    """
    if not predicate(hi):
        return None
    if predicate(lo):
        return lo
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if predicate(mid):
            hi = mid
        else:
            lo = mid
        if abs(hi - lo) < tol:
            break
    return hi


# Sondas contrafactuais: campo do contexto, símbolo do truthmaker, extremo da
# busca, direção, unidade, estratégia-alvo e mecanismo ontológico narrado.
PROBES = [
    ("capex_awe_usd_kw", "CAPEX_AWE", 3000.0, "geq", "USD/kW", "rn_h2v_strategy",
     "LCOH ultrapassa a paridade com o H₂ cinza; o H2ProductionGain converte-se em "
     "Loss e o CapexPreservationGain de NI passa a dominar"),
    ("fc", "FC", 0.02, "leq", "adimensional", "rn_h2v_strategy",
     "IntermittentCurtailmentVulnerability manifesta-se: as horas ativas caem, o LCOH "
     "sobe e o H2ProductionGain desaparece"),
    ("custo_logistico_usd_kg", "c_log", 3.0, "geq", "USD/kgH2", "rn_h2v_strategy",
     "LogisticsDistanceVulnerability manifesta-se; o LogisticsLoss elimina a margem de H₂V"),
    ("pld_arbitragem_usd_mwh", "PLD", 600.0, "geq", "USD/MWh", "rn_bess_strategy",
     "LowPLDArbitrageVulnerability é desativada e a EnergyArbitrageCapability "
     "manifesta-se plenamente"),
    ("lcos_usd_mwh", "LCOS", 5.0, "leq", "USD/MWh", "rn_bess_strategy",
     "HighCyclingDegradationVulnerability é mitigada; o BatteryDegradationLoss recua "
     "abaixo do ArbitrageGain"),
]


def generate_counterfactuals(ctx: DecisionContext = RN_2025, t: int = 0,
                             criterion: str = "vuav_ranking") -> list:
    """
    Terceira etapa do ontological unpacking: identifica, com direção e magnitude,
    quais truthmakers deveriam mudar para inverter a preferência. Os limiares são
    CALCULADOS por busca sobre o grafo, não tabelados.

    criterion = 'vuav_ranking'
        A preferência inverte quando outra estratégia ultrapassa a Preferred
        Bearer. É o critério coerente com a definição de Preferred Bearer adotada
        no artigo (maior VUAV do conjunto).

    criterion = 'parity'
        O limiar é o ponto em que VUAV(estratégia-alvo) cruza zero. Reproduz os
        limiares publicados na Tabela 5, que foram calibrados por paridade
        econômica e não por comparação entre alternativas. Os dois critérios só
        coincidem se VUAV das demais alternativas for aproximadamente nulo.
    """
    if criterion not in ("vuav_ranking", "parity"):
        raise ValueError(criterion)

    base_pref = _preferred(ctx, t)
    out = []

    for field, symbol, extreme, direction, unit, target, mechanism in PROBES:
        base_val = getattr(ctx, field)

        if criterion == "vuav_ranking":
            def pred(v, f=field):
                return _preferred(ctx.with_(**{f: v}), t) != base_pref
        else:
            sign = 1.0 if target == base_pref else -1.0
            def pred(v, f=field, tg=target, sg=sign):
                return sg * _vuav_of(ctx.with_(**{f: v}), tg, t) <= 0.0

        thr = _bisect(pred, base_val, extreme)
        if thr is None:
            continue

        new_pref = _preferred(ctx.with_(**{field: thr}), t)
        tm = next((x for x in ctx.truthmakers() if x.symbol == symbol), None)
        out.append(Counterfactual(
            truthmaker=tm.tid if tm else field,
            symbol=symbol,
            baseline=base_val,
            threshold=round(thr, 4),
            direction=direction,
            unit=unit,
            new_preferred=new_pref,
            mechanism=mechanism,
        ))
    return out


def write_counterfactuals_to_graph(g: Graph, cfs: list, ctx: DecisionContext = RN_2025) -> Graph:
    """Materializa cada contrafactual como side:CounterfactualClaim no grafo."""
    from rdflib import RDF, RDFS
    for i, cf in enumerate(cfs, 1):
        u = SIDE[f"cf_{cf.symbol.lower()}_{i}"]
        g.add((u, RDF.type, SIDE.CounterfactualClaim))
        g.add((u, RDFS.label, Literal(cf.statement(), lang="pt")))
        g.add((u, SIDE.altersTruthmaker, SIDE[cf.truthmaker]))
        g.add((u, SIDE.hasThreshold, Literal(float(cf.threshold), datatype=XSD.float)))
        g.add((u, SIDE.hasThresholdDirection, Literal(cf.direction)))
        g.add((u, SIDE.revertsPreferenceOf, SIDE[cf.new_preferred]))
        g.add((u, RDFS.comment, Literal(cf.mechanism, lang="pt")))
    return g


# =============================================================================
# 4. Ano de inversão de NI (OpportunityCostVulnerability crescente)
# =============================================================================

def ni_reversal_year(ctx: DecisionContext = RN_2025, horizon: Optional[int] = None) -> Optional[int]:
    """Primeiro ano em que VUAV(NI) se torna negativo."""
    horizon = horizon or ctx.vida_util_anos
    _, res = evaluate(ctx, t=0)
    ni = res.get("rn_ni_strategy")
    if ni is None:
        return None
    for t in range(horizon + 1):
        if ni.at_year(t) < 0:
            return t
    return None
