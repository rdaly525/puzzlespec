LogicPuzzles DSL is a small Python-embedded language for writing size-independent rules for grid-based logic puzzles.

At its core the DSL speaks about three structural kinds—Cells, Edges, and Vertices—without committing to any memory layout. A Grid(nR, nC) object produces symbolic sets of those entities (rows, columns, sliding windows, incident edges, …). The board dimensions nR and nC can be left symbolic by declaring them as Params that resolve later.

Puzzle state is described with Variables. A variable is created with
Var(name, domain, over=entity_set)
where the domain is one of Bool, Enum, or ranged Int. When over is omitted the variable is a global scalar; when over is an entity set it becomes an array addressed as var[entity] (e.g., var[cell], var[edge]).

Rule bodies are ordinary Python expressions built from logical and arithmetic operators plus two key constructs:

• Quantifiers: forall(entity_set, lambda v: …) (exists is similar).
• Aggregates: Sum(S, key=lambda e: …) and CountTrue(S, key=…).

Entity sets supply attribute sugar—row.sum_of(color), row.count_true(…), row.windows(3)—so most rules read naturally. A small helper library captures common patterns such as balanced(row, color) or exactly_k_true(S, k).

The DSL compiles immediately to a schema-free IR containing quantifier and aggregate nodes. After Params are concrete a RepresentationSchema rewrites each node into bit-level expressions and emits the chosen solver format (e.g. SMT-LIB).

Example (Unruly):

```python
nR, nC = Param("nR", int), Param("nC", int)
grid   = Grid(nR, nC)
color  = Bool.over(grid.C)

m = Model()
m += forall(grid.rows, lambda r: r.sum_of(color) == nC // 2)
m += forall(grid.cols, lambda c: c.sum_of(color) == nR // 2)

def no_triple(line):
    return forall(line.windows(3),
                  lambda w: 0 < w.sum_of(color) < 3)

m += forall(grid.rows, no_triple)
m += forall(grid.cols, no_triple)
```

Rule-time checks ensure domain compatibility and correct binder usage, and the DSL offers a pretty-printer to inspect the generated IR before it is lowered.
