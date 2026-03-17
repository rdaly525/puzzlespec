# PuzzleSpec DSL

PuzzleSpec is a Python-embedded formal DSL for specifying combinatorial puzzles and, more generally, constraint satisfaction problems.

You write a high-level puzzle specification in Python that serves as the single source of truth for a puzzle's mathematical structure. A specification includes symbolic parameters, state spaces, and constraints. For example, a Sudoku specification describes the constraints for *all* N-by-N grids and *all* possible clues.

## Key Insight

All puzzles have a natural structure:

- A set of **domains** (cells, digits, colors) — finite sets of values.
- **Decision variables** that are total functions between those domains.
- **Constraints** expressed as universal quantification over domain elements.

## Uses

1. **Verification and solving.** Given concrete parameters (e.g., clues), solve the puzzle. Or synthesize a concrete set of clues that yields a valid puzzle.
2. **Meta-reasoning.** Difficulty metrics, tactic discovery, or synthesizing new kinds of puzzles.

## Quick Example: Sudoku

```python
from puzzlespec import func_var, param, func_param, Unit, U, PuzzleSpecBuilder
from puzzlespec.libs import std, nd

p = PuzzleSpecBuilder()

# Parameters
B = param(std.Nat, name='B')       # box size (symbolic)
N = B * B                          # grid dimension

# Domains
Cells  = nd.fin(N) * nd.fin(N)     # N x N grid of cells
Digits = nd.range(1, N + 1)        # {1, 2, ..., N}

# Decision variable: each cell maps to a digit
cell_digits = func_var(Cells, Digits, name="cell_digits")

# Constraints: rows, columns, and boxes have distinct digits
p += nd.rows(cell_digits).forall(lambda row: std.distinct(row))
p += nd.cols(cell_digits).forall(lambda col: std.distinct(col))
p += nd.tiles(cell_digits, size=(B, B), stride=(B, B)).forall(
    lambda box: std.distinct(box)
)

# Clues: each cell optionally has a given digit
OptionalDigits = U(Unit) + Digits
givens = func_param(Cells, OptionalDigits, name="givens")

p += Cells.forall(
    lambda c: givens(c).match(
        lambda _: True,              # no clue — no constraint
        lambda d: cell_digits(c) == d  # clue — must match
    )
)

spec = p.build("Sudoku")
```

## Design Philosophy

- **Domains are values, not types.** A domain like `fin(9)` is a first-class expression that can be computed, passed to functions, and manipulated symbolically. Domains can depend on parameters (`fin(N*N)` where `N` is a variable) and compose via Cartesian product.
- **Functions are total.** A decision variable `F : Cells -> Digits` is a total function — every cell maps to exactly one digit. Partiality is modeled explicitly via sum types (`U(Unit) + T`).
- **Dependent types.** Function types can depend on their argument: `Pi(i : fin(N)). fin(i)` is a function whose codomain varies with the input. The type system tracks these dependencies through Pi types.
- **Symbolic parameters.** Puzzle dimensions (`N`, `B`) can be symbolic — the spec is generic over grid size and specializes at solve time.

## Domains

Domains are finite sets of values with set semantics — elements are unique and unordered. They are the core organizational unit.

| Formal | DSL | Meaning |
|--------|-----|---------|
| Fin(n) | `fin(n)` | {0, 1, ..., n-1} |
| [lo, hi) | `range(lo, hi)` | {lo, lo+1, ..., hi-1} |
| A x B | `A * B` | Cartesian product (N-dimensional) |
| A + B | `A + B` | Disjoint union (sum type domain) |
| {x in D \| p(x)} | `dom.restrict(pred)` | Subdomain filtered by predicate |
| Im(f) | `dom.map(f).image` | Image of a function over a domain |

Domains support operations like `.size` (cardinality), `.forall(pred)`, `.exists(pred)`, and `.contains(val)`.

### N-Dimensional Domains

Cartesian products of domains form N-dimensional domains. `fin(N) * fin(M)` has rank 2, `fin(N) * fin(M) * fin(K)` has rank 3, and so on. ND domains support numpy-style indexing and slicing:

```python
dom = fin(N) * fin(M) * fin(K)    # rank-3 domain
dom[2, :, 1]                       # slice: fixes axes 0 and 2, yields rank-1 subdomain
dom[1:4, 3]                        # slice: range on axis 0, fix axis 1
```

A function with a 1D domain (`F : fin(N) -> T`) is semantically an **indexable array** — a sequence of N values. A function with an ND domain (`F : fin(N) * fin(M) -> T`) is a **symbolic ND array**, analogous to a numpy ndarray. Indexing and slicing the domain induces indexing and slicing of the array.

Library functions like `nd.rows`, `nd.cols`, `nd.tiles`, and `F.windows` are all built on top of this indexing and slicing infrastructure.

## Variables: `var` vs `param`

PuzzleSpec distinguishes two kinds of free variables:

- **`var`** (existential): Decision variables — unknowns the solver must find. These are the "answers" of the puzzle.
- **`param`** (universal): Parameters — known quantities provided as input. Grid dimensions, clue values, etc.

Both support dependent function types via `func_var` and `func_param`:

```python
N = param(std.Nat, name='N')                     # parameter: grid size
Cells = fin(N) * fin(N)                          # domain depending on N
Digits = range(1, N + 1)                         # domain depending on N
F = func_var(Cells, Digits, name='F')            # decision variable: Cell -> Digit
givens = func_param(Cells, OptDigits, name='g')  # parameter: Cell -> Optional[Digit]
```

## Type System

### Base Types

```
Unit                    -- unit type (single inhabitant)
Bool                    -- booleans
Int                     -- integers
Enum(l1, ..., ln)       -- enumeration with named labels
T1 * ... * Tn           -- product (tuple) type
T1 + ... + Tn           -- sum (coproduct) type
Dom[T]                  -- domain type (finite set of T-values)
Pi(x : T1). T2          -- Pi type (dependent function type)
```

### Sum Types and Pattern Matching

Sum types model tagged unions. Optional values are the most common case:

```python
OptDigit = U(Unit) + Digits    # Unit + Digits

givens(c).match(
    lambda _: True,            # case Unit (no clue)
    lambda d: F(c) == d        # case Digit (must match)
)
```

Enums are also supported:

```python
BW_dom, BW = std.make_enum('BW')   # creates {B, W} domain + accessor
color = func_var(Cells, BW_dom, name='color')
```

### Refinement Types

Types can be refined to restrict their inhabitants. Refinements are stored as **domain values** rather than predicates — a natural choice because PuzzleSpec is built around finite domains.

```python
# Nat = integers > 0
Nat = Int.refine(lambda i: i > 0)

# Even natural numbers
EvenNat = Nat.refine(lambda i: i % 2 == 0)
```

Refinements compose — successive `.refine()` calls intersect the domain constraints. This means that `EvenNat` above restricts to positive even integers.

### Dependent Types via Refinements

PuzzleSpec's type system is first-order — there are no higher-kinded types or type-level computation. Dependent types are expressed through refinements: `fin(N)` is a domain value, and a variable with type refined by that domain is constrained to its elements.

```python
N = param(std.Nat, name='N')
x = var(fin(N), name='x')    # x has type {Int | ref = fin(N)}, i.e., 0 <= x < N
```

The dependency becomes essential when the codomain varies with the input:

```python
# F(i) is in fin(i) — the codomain depends on the argument
F = func_var(fin(N), lambda i: fin(i), name='F')
```

All values have simple base types (Int, Bool, etc.) at the core level. Domain membership is a constraint, not a type judgment.

## Obligations (Guards)

An **obligation** is a boolean predicate attached to a value that must hold for that expression to be valid. Obligations arise from operations with preconditions:

- **Division**: `x / y` produces a result guarded by `y != 0`
- **Domain membership**: applying a function `F` at index `i` guards by `i` being in `dom(F)`
- **User-specified**: `expr.guard(p)` explicitly attaches predicate `p`

Guards compose: if `x` already has obligation `p`, then `x.guard(q)` produces obligation `p & q`.

## Constraints

Constraints are boolean expressions added to a `PuzzleSpecBuilder` with `+=`:

```python
p = PuzzleSpecBuilder()
p += nd.rows(F).forall(lambda row: std.distinct(row))
p += Cells.forall(lambda c: givens(c).match(
    lambda _: True,
    lambda d: F(c) == d
))
spec = p.build("Sudoku")
```

Key constraint combinators from `libs/std`:

| Combinator | Meaning |
|------------|---------|
| `std.distinct(func)` | All values in the function's image are different |
| `std.all_same(func)` | All values are equal |
| `std.all(preds)` | Conjunction (logical AND over a domain) |
| `std.any(preds)` | Disjunction (logical OR over a domain) |
| `std.sum(func)` | Arithmetic sum over a domain |
| `std.prod(func)` | Arithmetic product over a domain |
| `std.count(func, pred)` | Count elements satisfying a predicate |

## Libraries

PuzzleSpec ships with several library modules under `puzzlespec.libs`:

| Module | Import | Purpose |
|--------|--------|---------|
| `std` | `from puzzlespec.libs import std` | Standard combinators: `distinct`, `all_same`, `count`, `sum`, `prod`, `all`, `any`. Also provides `std.Nat` (positive integers), `std.make_enum` for creating enum domains. |
| `nd` | `from puzzlespec.libs import nd` | N-dimensional domain and array operations: `nd.fin`, `nd.range`, `nd.rows`, `nd.cols`, `nd.tiles`. Provides the ND-aware domain constructors. |
| `topology` | `from puzzlespec.libs import topology as topo` | Grid topology helpers. `topo.Grid2D(nR, nC)` creates a 2D grid with `.cells()`, `.edges()`, and related structural accessors. |
| `optional` | `from puzzlespec.libs import optional as opt` | Optional/sum-type utilities. `opt.optional_dom(D)` creates a `Unit + D` domain. `opt.fold(val, on_none=..., on_some=...)` pattern-matches on optional values. `opt.count_some(func)` counts non-None entries. |

## Compilation and Specialization

```
User Python code
  -> PuzzleSpecBuilder (collects constraints)
  -> p.build("name") -> PuzzleSpec (raw IR)
  -> spec.optimize() -> PuzzleSpec (simplified IR)
  -> SMT backend (future)
```

A generic spec can be specialized by binding parameters:

```python
spec = p.build("Sudoku")          # generic over B
setter = VarSetter(spec)
setter.B = 3                      # 9x9 Sudoku
spec9 = setter.build()
print(spec9.optimize())
```

## Full Example: Unruly

```python
from puzzlespec import var, func_var, Unit, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std, nd, topology as topo, optional as opt

p = PuzzleSpecBuilder()

# Grid dimensions (must be even)
nR = var(std.Nat, name='nR').refine(lambda i: i % 2 == 0)
nC = var(std.Nat, name='nC').refine(lambda i: i % 2 == 0)

grid = topo.Grid2D(nR, nC)

# Color domain (black and white)
BW_dom, BW = std.make_enum('BW')

# Givens: each cell optionally has a color
givens = func_var(grid.cells(), opt.optional_dom(BW_dom), name='givens')

# Decision variable: each cell has a color
color = func_var(grid.cells(), BW_dom, name='color')

# Givens must match decision variables
p += grid.cells().forall(
    lambda c: opt.fold(givens(c), on_none=True, on_some=lambda v: color(c) == v)
)

# Equal balance of colors in all rows and columns
p += nd.rows(grid.cells()).forall(
    lambda row: std.count(color[row], lambda v: v == BW.B) == nC // 2
)
p += nd.cols(grid.cells()).forall(
    lambda col: std.count(color[col], lambda v: v == BW.B) == nR // 2
)

# No three consecutive same-colored cells
p += nd.rows(color).forall(
    lambda row: row.windows(3, 1).forall(lambda win: ~std.all_same(win))
)
p += nd.cols(color).forall(
    lambda col: col.windows(3, 1).forall(lambda win: ~std.all_same(win))
)

# Each row and column pattern is unique
p += std.distinct(nd.rows(color))
p += std.distinct(nd.cols(color))

spec = p.build("Unruly")
```
