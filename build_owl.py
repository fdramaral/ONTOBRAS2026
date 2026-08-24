"""
build_owl.py — Instanciação em OWL 2 via owlready2 e verificação de consistência.

Corresponde à Seção 4 do artigo ONTOBRAS/WTDO 2026 ("O modelo foi instanciado em
OWL 2 via owlready2 (Python 3.12)"). Exporta:

    out/side.owl        TBox + ABox em RDF/XML, carregável no Protégé
    out/side_full.ttl   o mesmo grafo em Turtle

e roda o reasoner HermiT sobre o resultado, reportando inconsistências e classes
insatisfazíveis. A verificação é o que sustenta a afirmação de que o refinamento
de NoInvestmentStrategy produz uma classe satisfazível — e não uma classe vazia.
"""

from pathlib import Path
import shutil
import sys

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
ODIR = ROOT / "ontology"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import RN_2025          # noqa: E402
from abox import build_abox          # noqa: E402
from vuav import evaluate            # noqa: E402


def export(ctx=RN_2025):
    """Consolida TBox + ABox com os VUAV materializados e exporta."""
    g, results = evaluate(ctx)

    ttl = OUT / "side_full.ttl"
    owl = OUT / "side.owl"
    g.serialize(destination=str(ttl), format="turtle")
    g.serialize(destination=str(owl), format="xml")
    return g, results, owl, ttl


def reason(owl_path: Path):
    """Carrega o OWL no owlready2 e roda o HermiT."""
    import owlready2
    from owlready2 import get_ontology, sync_reasoner, Thing

    world = owlready2.World()
    onto = world.get_ontology(owl_path.as_uri()).load()

    n_classes = len(list(world.classes()))
    n_individuals = len(list(world.individuals()))
    n_props = len(list(world.object_properties())) + len(list(world.data_properties()))

    report = {
        "classes": n_classes,
        "individuals": n_individuals,
        "properties": n_props,
        "consistent": None,
        "unsatisfiable": [],
        "reasoner": "HermiT",
        "error": None,
    }

    if not shutil.which("java"):
        report["reasoner"] = "indisponível (sem runtime Java)"
        return report, onto, world

    try:
        with onto:
            sync_reasoner(world, infer_property_values=False, debug=0)
        unsat = [c.name for c in world.classes()
                 if Thing in getattr(c, "equivalent_to", []) is None]
        # classes insatisfazíveis são equivalentes a owl:Nothing após o raciocínio
        unsat = [c.name for c in world.classes()
                 if owlready2.Nothing in c.equivalent_to]
        report["consistent"] = True
        report["unsatisfiable"] = unsat
    except owlready2.OwlReadyInconsistentOntologyError:
        report["consistent"] = False
    except Exception as e:                                   # noqa: BLE001
        report["error"] = f"{type(e).__name__}: {e}"
        report["reasoner"] = "falhou"

    return report, onto, world


def check_ni_satisfiable(world):
    """
    Verificação dirigida do refinamento da Seção 3.2: NoInvestmentStrategy deve
    ser satisfazível E ter restrições existenciais declaradas — isto é, não pode
    ser nem insatisfazível nem uma classe sem axiomas.
    """
    import owlready2
    ni = world.search_one(iri="http://purl.org/side/energy#NoInvestmentStrategy")
    if ni is None:
        return {"found": False}
    restrictions = [str(r) for r in ni.is_a
                    if isinstance(r, owlready2.class_construct.Restriction)]
    return {
        "found": True,
        "insatisfazivel": owlready2.Nothing in ni.equivalent_to,
        "n_restricoes_existenciais": len(restrictions),
        "restricoes": restrictions,
        "n_instancias": len(list(ni.instances())),
    }


if __name__ == "__main__":
    g, results, owl, ttl = export()
    print(f"Grafo consolidado: {len(g)} triplas")
    print(f"  {owl}")
    print(f"  {ttl}\n")

    report, onto, world = reason(owl)
    for k, v in report.items():
        print(f"  {k:16s}: {v}")

    print("\nVerificação do refinamento de NoInvestmentStrategy:")
    for k, v in check_ni_satisfiable(world).items():
        print(f"  {k:28s}: {v}")
