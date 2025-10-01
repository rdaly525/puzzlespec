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





# LogicPuzzles DSL — Rule-Layer Specification (v0.1)
_Last updated 2025-07-13_

---

## 1 Core concepts

| Concept | Description |
|---------|-------------|
| **Entity kinds** | `Cell (C)`, `Edge (E)`, and `Vertex (V)` are the only first-class structural kinds. |
| **Topology** | `Grid(nR, nC)` instantiates:<br>• `C`, `E`, `V` sets<br>• standard subsets such as `rows`, `cols`, `row(i)`, `col(j)`<br>• graph helpers (`incident_edges(c)`, sliding-window views, …).<br>`nR`, `nC` may be symbolic `Param`s. |
| **Domains** | Plain Python dataclasses:<br>• `Bool`<br>• `Enum(values: tuple[str \| int])`<br>• `Int(lo: int, hi: int \| ∞)`<br>Expose `.kind`, `.values/lo/hi`, `.cardinality()`, `.bit_width()`. |
| **Variables** | `Var(name, domain, *, over=None)` (Array-Var pattern).<br>• `over=None` → global scalar.<br>• `over=<EntitySet>` → indexed array; access with `var[entity]`.<br>Attribute sugar: `domain.over(entity_set)` returns an equivalent `Var`. |
| **Constants** | `Const(domain, value, *, over=None)` (per-entity if `over` supplied). Typically materialised from a puzzle instance via a **ClueSpec** table. |
| **Params** | `Param(name, python_type)` — symbolic values resolved just before lowering. |

---

## 2 Expression language (IR)

_All expressions are built when rule code is interpreted; the DSL never inspects Python source._

| Category | Constructors / operators |
|----------|--------------------------|
| **Logical** | `And(*exprs)`, `Or(*exprs)`, `Not(expr)`, `Implies(a, b)`, `Eq(a, b)`, `Ne(a, b)` |
| **Arithmetic** | `Add(*ints)`, `Sub(a, b)`, `Mul(a, b)`, comparisons `Le`, `Lt`, `Ge`, `Gt` |
| **Aggregates** | `Sum(index_set, key=λ)`, `CountTrue(index_set, key=λ)`<br>Attribute sugar on entity sets:<br>• `S.sum_of(expr)`<br>• `S.count_true(expr)`<br>• `S.all(expr)`<br>• `S.any(expr)` |
| **Quantifiers** | `forall(index_set, λ(binder) → BoolExpr)`; `exists` analogous. |
| **Set helpers** | `line.windows(k)` → symbolic sliding-window entity sets. |

Lowering may replace aggregates/quantifiers with SMT/SAT gadgetry.

---

## 3 Helper library (level-3 domain helpers)

| Helper | Semantics |
|--------|-----------|
| `balanced(S, pred)` | `Sum(S, key=pred) == |S| / 2` |
| `exactly_k_true(S, k, key=λ)` | `CountTrue(S, key) == k` |
| `no_triples(line, pred)` | `forall(line.windows(3), λ w: 0 < w.sum_of(pred) < 3)` |

Helpers expand to primitives before the IR stage.

---

## 4 Clue specification

```python
ClueSpec(
    places = grid.C | grid.outside_edges,   # where clues may occur
    domain = Int(0, 9)                      # or a callable returning a Domain
)
```

## Grammar for DSL

```
module LogicDSL {

  #––– Identifiers & basic values ––––––––––––––––––––––––––––––––––––––––––––
  identifier = string
  integer    = int
  boolean    = bool

  #––– Domain descriptors ––––––––––––––––––––––––––––––––––––––––––––––––––––
  domain =
        Bool                                -- Boolean domain
      | Enum(identifier* values)            -- Finite set of symbols
      | Int(integer lo, integer? hi)        -- Closed or half-open integer range
      ;

  #––– Parameters (symbolic integers) ––––––––––––––––––––––––––––––––––––––––
  param = Param(identifier name, identifier pytype)

  #––– Topology declarations –––––––––––––––––––––––––––––––––––––––––––––––––
  grid_decl = GridDecl(identifier name, param nR, param nC)

  #––– Entity kinds ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  entity_kind = cell | edge | vertex            -- C / E / V

  #––– Entity sets (symbolic until params resolve) –––––––––––––––––––––––––––
  entity_set =
        AllCells  (identifier grid)                 -- grid.C
      | AllEdges  (identifier grid)                 -- grid.E
      | AllVerts  (identifier grid)                 -- grid.V
      | Rows      (identifier grid)                 -- grid.rows
      | Cols      (identifier grid)                 -- grid.cols
      | Windows   (entity_set base, integer k)      -- sliding k-windows
      | IncidentEdges(entity cell)                  -- incident_edges(c)
      | Union      (entity_set left, entity_set right)
      | Difference (entity_set left, entity_set right)
      ;

  #––– Variable / constant declarations ––––––––––––––––––––––––––––––––––––––
  var_decl   = VarDecl  (identifier name, domain dom, entity_set? over)
  const_decl = ConstDecl(identifier name, domain dom, literal value,
                         entity_set? over)
  decl       = grid_decl | var_decl | const_decl | param

  #––– Lambda used in aggregates / quantifiers –––––––––––––––––––––––––––––––
  lambda_expr = Lambda(identifier binder, expr body)

  #––– Expressions –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  expr =
        BoolConst(boolean value)
      | IntConst (integer value)
      | EnumConst(identifier value)
      | VarRef   (identifier var, entity? index)        -- scalar if index absent

      -- logical
      | And(expr* args)
      | Or (expr* args)
      | Not(expr arg)
      | Implies(expr a, expr b)
      | Eq(expr a, expr b)  | Ne(expr a, expr b)
      | Lt(expr a, expr b)  | Le(expr a, expr b)
      | Gt(expr a, expr b)  | Ge(expr a, expr b)

      -- arithmetic
      | Add(expr* args)     | Sub(expr a, expr b)
      | Mul(expr a, expr b) | Div(expr a, expr b)

      -- aggregates
      | Sum      (entity_set scope, lambda_expr projector)
      | CountTrue(entity_set scope, lambda_expr predicate)

      -- quantifiers
      | ForAll(entity_set scope, identifier binder, expr body)
      | Exists(entity_set scope, identifier binder, expr body)
      ;

  #––– Constraint lists & model ––––––––––––––––––––––––––––––––––––––––––––––
  constraint = expr                 -- must evaluate to Bool in type checker
  model      = Model(constraint* constraints)

  #––– Complete specification document –––––––––––––––––––––––––––––––––––––––
  specification = Specification(decl* declarations, model rules)
}
```