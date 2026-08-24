"""Testes de regressão contra os valores publicados no artigo."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from context import RN_2025 as c
from vuav import evaluate, generate_counterfactuals

def approx(a, b, tol): return abs(a - b) <= tol

def test_derivacoes():
    assert approx(c.horas_ativas, 5212, 1)
    assert approx(c.ciclos_ano, 1303, 1)
    assert approx(c.producao_h2_kg / 1000, 99300, 100)
    assert approx(c.energia_bess_mwh, 4690800, 500)
    assert approx(c.eta_impl, 0.75, 0.005)

def test_vuav():
    _, r = evaluate(c)
    assert approx(r["rn_h2v_strategy"].value / 1e6, 54.6, 0.2)
    assert approx(r["rn_bess_strategy"].value / 1e6, -248.6, 0.3)
    assert list(r)[0] == "rn_h2v_strategy"
    assert r["rn_h2v_strategy"].value > r["rn_ni_strategy"].value > r["rn_bess_strategy"].value

def test_contrafactuais_paridade():
    t = {x.symbol: x.threshold for x in generate_counterfactuals(c, criterion="parity")}
    assert approx(t["c_log"], 0.55, 0.02)
    assert approx(t["PLD"], 145.0, 1.0)
    assert approx(t["LCOS"], 92.0, 1.0)
    assert approx(t["CAPEX_AWE"], 1190.0, 20.0)

def test_limiares_de_reversao():
    t = {x.symbol: x.threshold for x in generate_counterfactuals(c, criterion="vuav_ranking")}
    assert approx(t["PLD"], 157.0, 1.0)      # fronteira H2V/BESS declarada no artigo
    assert approx(t["CAPEX_AWE"], 866.0, 2.0)  # limiar em que H2V torna-se Deprecated

def test_politica_de_criterio():
    from unpacking import dual_thresholds
    d = {x["symbol"]: x for x in dual_thresholds(c)}
    assert approx(d["PLD"]["valor_a_reportar"], 157.0, 1.0)
    assert approx(d["FC"]["valor_a_reportar"], 0.43, 0.01)
    assert d["CAPEX_AWE"]["criterio_exigido"] == "reversão"

def test_divergencia_fc_conhecida():
    d = c.diagnostico_lcoh()
    assert not approx(d["fc_paridade"]["analytic_residual"], 0.34, 0.01)

if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"  {n}: OK")
    print("\nTodos os testes passaram.")
