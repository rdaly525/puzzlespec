### Tactics IR and Builder EDSL

This document describes the tactic intermediate representation (IR) and the Python EDSL used to author tactics against an existing puzzle specification. The design goals are:

- Explicitly reference puzzle spec variables (no implicit variables)
- Monotone, sound steps with SMT-checkable proofs
- Small, typed core with ergonomic sugar

The tactic IR reuses the base spec IR node type (`puzzlespec.ir.Node`) and AST wrappers (`puzzlespec.ast.Expr`, etc.). The EDSL composes tactics as guarded rewrites that strengthen the current state.

### Core concepts

- State S = (C, A)
  - C: fixed constraints from the puzzle spec (translated to SMT)
  - A: current abstract store (domains, bounds, aggregates), queried via helpers
- Tactic rule = (bindings, guard, actions, explanation)
  - bindings: how we enumerate a small neighborhood (rows, cols, indices)
  - guard: side-effect-free predicates over the store (domains/counts/bounds)
  - actions: monotone updates (assign/remove/tighten)
  - explanation: optional string for human-facing description

Progress is a strict contraction of the store (e.g., domain shrink, bound tightening). Each action has a proof obligation discharged by UNSAT checks against C ∧ A.

### Referencing the puzzle spec

- Always import and build the spec, then reference its variables directly.
- Use the spec's decision variable dictionaries for concrete variables. For Sudoku:

```python
from puzzlespec.puzzles.sudoku import build_sudoku_spec

spec = build_sudoku_spec()
[cell_vals] = spec.get_var_dicts(role="decision")  # DictExpr[{CellIdx}: Int]
grid = spec.topo  # Grid2D
```

- Obtain structural lists of cell indices from the grid:

```python
from packages.tactics import rows_from, cols_from

rows = rows_from(grid)  # List[List[CellIdx]]
cols = cols_from(grid)  # List[List[CellIdx]]
```

- Index into these lists or bind over them to pick indices, then look up the actual decision variable via the dict, e.g. `cell_vals[idx]`.

### Builder EDSL (context-managed)

```python
from packages.tactics import tactic, values, foreach
from packages.tactics import dom, size, contains, the_one, count_has

with tactic("Name", explain="Optional explanation") as t:
  x = t.bind(domain)        # generator binding over a ListExpr
  t.where(x != y)           # structural filters (no store reads)
  t.when(size(dom(x)) == 1) # guards (store reads ok)
  t.do(assign(x, the_one(dom(x))))  # actions
  rule = t.build()
```

Notes
- Use Python assignment for aliasing deterministic expressions (no explicit `let`).
- `.bind(domain)` expects a `ListExpr[...]` (or an `Expr` to carry type); it returns a parameter of the element type.
- `.where(...)` is structural only; `.when(...)` can read the store.
- `.do(...)` collects actions. `foreach(domain, fn)` helps build repeated actions.

### Guards and actions (helpers)

- Domains and counts:
  - `x.dom()` → DomExpr
  - `x.is_singleton()`
  - `x.only_candidate_is(v)` → size(dom(x))==1 ∧ the_one(dom(x))==v
  - `C.count_has(values(...))` → IntExpr
- Predicates on DomExpr:
  - `dom.contains(v)`, `dom.size()`, `dom.the_one()`
- Actions:
  - `assign(x, v)`, `remove(x, values(...))`
  - `tighten_sum(list[Int], lo, hi)`, `tighten_count(vars, values, lo, hi)`

### Soundness (SMT proof obligations)

- assign(x, v): prove UNSAT(C ∧ S ∧ x ≠ v)
- remove(x, R): for each v ∈ R, prove UNSAT(C ∧ S ∧ x = v)
- tighten (linear): check UNSAT of the negated bound (e.g., s ≤ L′−1 or s ≥ U′+1)
- counts over values: reify only locally for the affected vars/values in that proof

### Structural vs guard separation

- Bind structure using spec IR collections:
  - Sudoku: `rows_from(grid)`, `cols_from(grid)`, index into them
  - Bind indices directly (0..N−1) or bind cells from the row/col lists
- Put state-dependent checks in `when(...)` using `dom/size/contains/count_has`.

### Examples

- Naked single (Sudoku):

```python
with tactic("NakedSingle") as t:
  # Iterate all cell decision variables
  spec = build_sudoku_spec()
  [cell_vals] = spec.get_var_dicts(role="decision")
  grid = spec.topo
  cells = rows_from(grid).concat(cols_from(grid)[0])  # or expose a flat list in your facade

  x_idx = t.bind(cells)     # bind cell index
  x = cell_vals[x_idx]      # concrete decision variable
  t.when(x.is_singleton())
  t.do(assign(x, x.dom().the_one()))
  rule = t.build()
```

- X-Wing (row-based, indices) excerpt:

```python
spec = build_sudoku_spec()
[cell_vals] = spec.get_var_dicts(role="decision")
grid = spec.topo
rows = rows_from(grid)
cols = cols_from(grid)

with tactic("XWing_RowBased_Idx") as t:
  ri = values(*range(9))
  ci = values(*range(9))
  ri1, ri2 = t.bind(ri), t.bind(ri)
  t.where(ri1 != ri2)
  cA, cB = t.bind(ci), t.bind(ci)
  t.where(cA != cB)
  v = t.bind(values(1,2,3,4,5,6,7,8,9))

  R1, R2 = rows[ri1], rows[ri2]
  x1A, x1B = cell_vals[R1[cA]], cell_vals[R1[cB]]
  x2A, x2B = cell_vals[R2[cA]], cell_vals[R2[cB]]

  R1V, R2V = R1.map(lambda i: cell_vals[i]), R2.map(lambda i: cell_vals[i])
  t.when(count_has(R1V, values(v)) == 2)
  t.when(contains(x1A.dom(), v) & contains(x1B.dom(), v))
  t.when(R1V.forall(lambda z: (contains(z.dom(), v)).implies((z == x1A) | (z == x1B))))
  # symmetric for R2
  # eliminate from columns except the wing cells using masks + foreach
  # ...
  rule = t.build()
```

### Implementation layout

- `packages/tactics/ir.py`: tactic node types (`TacRule`, `TacActions`, `TacAssign`, `TacRemove`, aggregates, queries)
- `packages/tactics/ast.py`: AST facade for tactics (helpers, instance methods)
- `packages/tactics/builder.py`: context-managed EDSL (`tactic`), sugar (`values`, `foreach`, `windows`)

### Authoring guidelines

- Reference only spec variables for decision facts (e.g., Sudoku `cell_vals[idx]`)
- Use Python assignment for aliases; only `.bind/.where/.when/.do` in the EDSL
- Keep structural pattern small (bind indices or cells), push store checks into guards
- For cross-puzzle tactics, bind via the spec’s topology (rows/cols/tiles/adjacency) and operate on the spec’s decision variables


