
### ⚡ One-Page Summary — *LogicPuzzles* Embedded DSL & Framework
---

#### 1. Conceptual Layers
| Layer | Role | Key Types |
|-------|------|-----------|
| **Parametric Family** | “Schema” of a puzzle class; uses **symbolic parameters** instead of numbers so one definition covers 4×4, 9×9, etc. | `Param`, `Domain`, `Grid` |
| **Constraint DSL** | Declarative helpers that read like rule sheets. They return solver‑agnostic **IR nodes**. | `alldifferent`, `sum_equals`, `exactly_k_true`, `connected`, … |
| **Intermediate Representation (IR)** | Tiny set of primitive nodes that every helper lowers to (`Eq`, `Le`, `Add`, `And`, `Distinct`, …). | `Constraint` subclasses |
| **Resolver** | Substitutes concrete values for all `Param`s, picks bit‑widths, expands regions, producing a *ground* IR. | `resolve(family_spec, config) → Model` |
| **Back‑ends** | Visitors that map primitive IR → solver calls. Multiple implementations run side‑by‑side. | `HWTypesVisitor`, `CPSATVisitor`, `CVC5Visitor`, … |
| **Generators / Solvers / Tactic‑miners** | Work on *resolved* models; independent of the DSL’s syntax. | `PuzzleGenerator`, `HumanLikeSolver`, … |

---

#### 2. Core Objects (User‑Facing)
```python
Param("SIZE")                 # symbolic integer
Domain(1, Param("SIZE"))      # digits 1‥SIZE
g = Grid(Param("SIZE"), Param("SIZE"), digits)

for row in g.rows():
    model.append(alldifferent(row))    # declarative helper

family_spec = Model(grid=g, ir=model)  # still symbolic
```

*Nothing is concrete until `resolve(family_spec, {"SIZE": 9})`.*

---

#### 3. Workflow
1. **Author** rules with helpers & `Param`s → *Family* object.  
2. **Resolve** with a `Config` → concrete *Model*.  
3. **Select Back‑end** (`"z3"`, `"cvc5"`, `"cp_sat"`) → primitive solver formula.  
4. **Generate / Solve / Rate** puzzle instances.  
5. (Optional) **LLM loop**: prompt model to emit new rule helpers → validate via the same pipeline → keep interesting survivors.

---

#### 4. Why it Works
* **Re‑use:** one ruleset covers all board sizes & variants.  
* **Backend freedom:** every solver only implements ~6 primitives.  
* **Safety:** resolver guarantees finite domains & bit‑widths before solving.  
* **Extensibility:** new helpers are local sugar that lower to the same IR.  
* **Meta‑generation:** rules are plain Python data ⇒ easy to mutate, combine, score, and feed back into an evolutionary or LLM search loop.

---

#### 5. Typical File Layout
```
logicpuzzles/
├─ core/          (Param, Grid, IR, resolver)
├─ helpers/       (alldifferent, sum_equals, ...)
├─ backends/      (hwtypes.py, ortools.py, cvc5.py)
├─ rules/         (sudoku.py, kakuro.py, ...)
└─ meta/          (generator.py, tactic_miner.py, llm_search.py)
```

---

#### 6. Next Steps
1. **Implement** the primitive IR + a single back‑end (HWTypes/Z3).  
2. **Port** one classic family (Sudoku) end‑to‑end.  
3. **Add** the resolver & second back‑end to validate abstraction.  
4. **Prototype** the LLM rule‑inventor with a strict validation harness.  

This provides a minimal but complete pipeline—from declarative, parametric rule description all the way to solver results and automated rule‑set discovery.
