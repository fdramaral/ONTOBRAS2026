# SIDE — Implementação OWL 2 / RDF / SPARQL

Instanciação computacional do arcabouço ontológico descrito em **Amaral, Peixoto,
Baião e Maçaira (2026)**, *Modelagem Ontológica de Valor e Risco em Decisões de
Investimento em Energia: Uma Abordagem Baseada em COVeR e IA Explicável*
(ONTOBRAS/WTDO 2026), Seções 3.1–3.5, 4 e 5.

O arcabouço estende a **COVeR** (Common Ontology of Value and Risk) ao domínio de
decisão de investimento em aproveitamento de *constrained-off* renovável,
comparando três estratégias — não investir (NI), hidrogênio verde (H₂V) e
armazenamento por baterias (BESS) — no contexto do Rio Grande do Norte.

---

## Estrutura

```
side/
├── ontology/
│   ├── side_tbox.ttl          TBox OWL 2: stubs UFO/COVeR + extensão SIDE
│   └── rn_2025_abox.ttl       ABox: truthmakers e cadeias causais de RN_2025
├── queries/
│   ├── _prefixes.rq           prefixos compartilhados
│   ├── q0_vuav_ranking.rq     Figura 6 do artigo — ordenação por VUAV
│   ├── q1_vuav_parameters.rq  L(GEᵢ), I(GEᵢ), L(LEⱼ), S(LEⱼ)
│   ├── q2_qc1_direct_explanation.rq   QC1 — Capability → Gain → Intention
│   ├── q3_unpacking_chain.rq  Vulnerability → Loss Event → Intention
│   ├── q4_active_truthmakers.rq       truthmakers ativos por classificação
│   ├── q5_qc3_bess_condition.rq       QC3 — condições de reversão do BESS
│   └── q6_ni_refinement.rq    verificação do refinamento de NI (Seção 3.2)
├── src/
│   ├── context.py             truthmakers primários e derivações
│   ├── abox.py                construtor do grafo RDF
│   ├── vuav.py                cálculo do VUAV e busca de contrafactuais
│   ├── unpacking.py           explicações, QCs, sensibilidade e dual_thresholds
│   ├── build_owl.py           exportação OWL/XML e reasoner HermiT
│   └── test_side.py           testes de regressão contra os valores publicados
├── paper/
│   ├── fig5_mapa_decisao.py           regenera a Figura 5 do artigo
│   └── tab3_tabela_sensibilidade.py   regenera a Tabela 3 do artigo
├── out/                       artefatos gerados (versionados por conveniência)
├── CITATION.cff
└── run_all.py                 pipeline completo (Figura 3)
```

---

## Execução

```bash
pip install -r requirements.txt
python3 run_all.py                        # pipeline completo
python3 src/test_side.py                  # testes de regressão
python3 paper/fig5_mapa_decisao.py        # regenera a Figura 5
python3 paper/tab3_tabela_sensibilidade.py  # regenera a Tabela 3
```

Os scripts de `paper/` derivam todos os números de `dual_thresholds()` — nenhum
limiar é digitado à mão nas figuras ou tabelas do artigo.

O reasoner HermiT exige um runtime Java; sem ele o pipeline roda normalmente e a
etapa de consistência é reportada como indisponível.

Gera em `out/`:

| Arquivo | Conteúdo |
|---|---|
| `side.owl` | TBox + ABox em RDF/XML — abre no Protégé |
| `side_full.ttl` | mesmo grafo em Turtle |
| `resultados.json` | VUAV, contrafactuais, sensibilidade, validação, diagnóstico |

---

## Princípio de projeto

Nenhum resultado numérico é constante no código. Os **Gain e Loss Events são
derivados dos truthmakers primários**, e os parâmetros do VUAV são recuperados do
grafo RDF por consulta SPARQL antes de qualquer cálculo. É essa cadeia que torna
os contrafactuais efetivamente computáveis: alterar um truthmaker reconstrói o
grafo, refaz as consultas e recalcula a Preferred Bearer.

Os limiares contrafactuais não são tabelados — são **encontrados por bissecção
sobre o grafo**.

---

## Resultados reproduzidos

Executando `run_all.py` sobre o contexto RN_2025:

| Grandeza | Publicado | Obtido |
|---|---|---|
| Horas ativas/ano | 5.212 | 5.212,2 |
| Ciclos/ano (BESS) | 1.303 | 1.303,0 |
| Produção H₂ | 99.300 t/ano | 99.280 t/ano |
| Energia BESS | 4.690.800 MWh | 4.690.980 MWh |
| η_impl | 0,75 | 0,7505 |
| VUAV(H₂V) | +54,6 M USD/ano | +54,6 |
| VUAV(BESS) | −248,6 M USD/ano | −248,6 |
| Limiar c_log | 0,55 USD/kg | 0,55 |
| Limiar PLD | 145 USD/MWh | 145,0 |
| Limiar LCOS | 92 USD/MWh | 92,0 |
| Limiar CAPEX | 1.190 USD/kW | 1.177,4 |
| **Limiar FC** | **34%** | **43,0%** |

Ordenação `VUAV(H₂V) > VUAV(NI) > VUAV(BESS)` confirmada. Os seis cenários da
Tabela 5 reproduzem a coluna *Preferred Bearer* publicada.

**Consistência:** 89 classes, 68 indivíduos, 35 propriedades; ontologia
consistente sob HermiT, sem classes insatisfazíveis. `NoInvestmentStrategy` é
satisfazível e porta quatro restrições existenciais — a verificação formal da
afirmação da Seção 3.2 de que NI não é uma classe vazia.

---

## Divergências identificadas

### 1. Limiar de FC (34% vs. 43,0% vs. 46,4%)

A curva da Figura 10, `LCOH(FC) = 141,78/(166,86 × FC)`, decompõe-se exatamente
em `(CAPEX × FCR + OPEX) / (8760 × FC / κ)` — ou seja, considera apenas CAPEX e
OPEX. Avaliada em FC = 59,5% devolve **1,43 USD/kg**, e não os **1,95 USD/kg** da
Tabela 2, que vêm do Monte Carlo do SBPO e incluem custo de energia, reposição de
stack e BOP. A diferença é de **0,52 USD/kg**.

Em consequência, o FC de paridade depende do modelo adotado:

| Modelo | FC de paridade |
|---|---|
| Curva analítica publicada (Fig. 10) | 34,0% |
| Analítico + componente residual | 43,0% |
| Proporcional (LCOH ∝ CAPEX, ∝ 1/FC) | 46,4% |

Os demais limiares da Tabela 5 são coerentes com os dois últimos modelos, não com
o primeiro: o LCOH de 2,73 USD/kg em CAPEX = 1.190 USD/kW é reproduzido
**exatamente** pelo modelo proporcional, e o limiar de CAPEX de 1.190 USD/kW é
reproduzido dentro de 1,1% pelo modelo analítico com residual. Recomenda-se
adotar um único modelo e recalcular a Figura 10 e a Tabela 5 a partir dele.

### 2. Critério de reversão: viabilidade vs. preferência

Cada afirmação de limiar pertence a uma de duas famílias, e usar o critério
errado devolve um número certo para a pergunta errada:

- **viabilidade** — "o Gain Event converte-se em Loss", "a margem é eliminada".
  Ponto em que VUAV(s) cruza zero. Independe das demais alternativas e, portanto,
  da calibração de NI.
- **reversão** — "torna-se Preferred Bearer", "torna-se Deprecated". Ponto em que
  outra estratégia ultrapassa. Depende do VUAV das demais alternativas.

| Truthmaker | Viabilidade | Reversão | Critério exigido pela afirmação |
|---|---|---|---|
| CAPEX_AWE | 1.177 USD/kW | **866 USD/kW** | reversão (QC2: "tornariam H₂V *Deprecated*") |
| FC | **43,0%** | 58,5% | viabilidade ("o Gain Event converte-se em Loss Event") |
| c_log | **0,55 USD/kg** | 0,046 USD/kg | viabilidade ("elimina a margem de H₂V") |
| PLD | 145 USD/MWh | **157 USD/MWh** | reversão ("BESS torna-se *Preferred Bearer*") |
| LCOS | **92 USD/MWh** | 80 USD/MWh | viabilidade ("margem → USD 0/MWh") |

`dual_thresholds()` devolve as duas colunas e o critério que cada afirmação exige.
As QCs 2 e 3 usam `vuav_ranking` por default, porque perguntam por status de
bearer. A tabela de sensibilidade reporta limiares de viabilidade, mais robustos
porque não dependem da calibração de NI.

Consequência prática: em CAPEX = USD 850/kW a vantagem de H₂V sobre NI é de
apenas USD 4,6 M/ano, e a preferência se inverte já em USD 866/kW. Essa margem
estreita é inteiramente função da calibração de NI abaixo — não é um resultado
robusto do arcabouço.

---

## Parâmetros calibrados nesta implementação

O artigo qualifica VUAV(NI) como "positivo transitório" sem publicar os valores de
L, I e S da alternativa NI. Os parâmetros abaixo são **calibração desta
implementação**, não resultados do artigo, e estão isolados em `context.py` sob
comentário explícito:

| Parâmetro | Valor | Justificativa |
|---|---|---|
| `I(CapexPreservationGain)` | CAPEX × WACC = 102 M USD/ano | custo de oportunidade do capital não imobilizado |
| `I(TechLockInAvoidanceGain)` | 25 M USD/ano, L = 0,60 | valor de opção — subjetivo |
| `I(RegulatoryRiskAvoidanceGain)` | 15 M USD/ano, L = 0,50 | valor de opção — subjetivo |
| `L(RevenueOpportunityLoss)` em t=0 | 0,30, crescendo 0,05/ano | ramp-up do mercado |

Resultado: VUAV(NI) = +50,0 M USD/ano em t = 0, tornando-se negativo no **ano 5** —
compatível com a descrição qualitativa do artigo e com a ordenação publicada.
**Devem ser confirmados ou substituídos antes de qualquer uso na dissertação.**

---

## Extensões desta implementação em relação ao artigo

1. `side:threatens` (Vulnerability → GainEvent): distingue vulnerabilidades que
   produzem um Loss Event próprio (`cover:produces`) daquelas cuja manifestação
   converte um Gain Event existente em perda. Necessária para representar a
   `IntermittentCurtailmentVulnerability` e a `LowPLDArbitrageVulnerability` sem
   duplicar eventos de custo.
2. `side:isActive` (Vulnerability → boolean): uma vulnerabilidade inativa
   permanece inerente à estratégia mas não se manifesta. É essa distinção que
   torna a reversão de preferência representável no grafo.
3. `side:hasLikelihoodGrowthRate`: representa vulnerabilidades de magnitude
   crescente, como a `OpportunityCostVulnerability` de NI.
4. `side:CounterfactualClaim` materializado como indivíduo no grafo, com limiar,
   direção e truthmaker alterado.

---

## Nota sobre os namespaces `ufo:` e `cover:`

As classes sob `http://purl.org/side/ufo#` e `http://purl.org/side/cover#` são
**stubs de alinhamento**: reproduzem a taxonomia mínima da UFO e da COVeR
necessária para ancorar a extensão SIDE. A COVeR (Sales et al., 2018) não possui
serialização OWL canônica com IRIs estáveis publicada. Ao adotar uma, substituir
os prefixos e declarar `owl:equivalentClass` entre os stubs e as classes oficiais.

---

## Dependências

```
rdflib >= 7.0
owlready2 >= 0.46
Java (opcional — apenas para o reasoner HermiT)
```


---

## Licença

Licença dupla, pela natureza do artefato:

| Abrange | Licença |
|---|---|
| `src/`, `paper/`, `run_all.py` — código | [MIT](LICENSE) |
| `ontology/`, `queries/`, `out/side.owl`, `out/side_full.ttl`, figuras e tabelas | [CC BY 4.0](LICENSE-ONTOLOGY) |

MIT no código porque a barreira de reúso deve ser mínima; CC BY 4.0 na ontologia
porque é obra intelectual cuja atribuição importa — quem estender o SIDE deve
creditar a origem, do mesmo modo que este trabalho credita a COVeR.

Os stubs sob `ufo:` e `cover:` reproduzem a taxonomia mínima de ontologias de
referência de terceiros e não substituem as fontes originais.
