# PuzzleSpec Developer Guide

This guide covers the internal architecture, IR design, and pass infrastructure for developers working on the PuzzleSpec compiler.

## System Overview

PuzzleSpec is a domain-centric DSL for expressing puzzle specifications as dependent constraints over structured domains. The user writes high-level puzzle descriptions using the DSL; the compiler lowers them through a series of passes into a form suitable for SMT solving.

### Layer Diagram

```
libs/           User-facing libraries (std, nd, var_def, topology, optional)
  |
compiler/dsl/
  ast.py        DSL wrapper layer — operator-overloaded Python expressions
  ast_nd.py     N-dimensional domain/array extensions (NDDomainExpr, NDArrayExpr)
  ir.py         Core IR — immutable typed expression graph
  spec.py       Spec construction and compilation entry point
  |
compiler/passes/
  pass_base.py  Pass infrastructure (Transform, Analysis, @handles, PassManager)
  transforms/   Rewrite passes (simplification, beta reduction, guard lifting, ...)
  analyses/     Read-only passes (type checking, free vars, pretty printing, ...)
  utils.py      simplify() pipeline — assembles passes into a PassManager
```

## Compiler Design Principles

### Everything lives in the IR tree

All semantic information — types, obligations, refinements, views — is stored directly on IR nodes as named children, not in external side tables or separate data structures. Transformation passes become brittle when they must keep external mappings in sync with a changing tree. By embedding everything in the tree itself, passes can freely rewrite subtrees without worrying about stale references in auxiliary structures.

### Types are IR nodes

Types are full IR nodes, not a separate type-level language. This is necessary for two reasons:

1. **Types contain value children.** A refined type like `{Int | Fin(N)}` has a child value (the domain `Fin(N)`). Since types participate in the expression graph, the same traversal and rewriting infrastructure handles both values and types uniformly.

2. **The DSL wrapper layer needs eager types.** The Python AST facade (`ast.py`) must know the type of every value at construction time to select the correct wrapper class (`IntExpr`, `BoolExpr`, `DomainExpr`, etc.). Types are therefore computed eagerly during construction — this is why `ApplyT` (type-level application) is immediately beta-reduced rather than left as a thunk.

### Immutability

All nodes are immutable. Once constructed, a node's fields, children, and named children never change. Modification is done via `replace()`, which returns a new node (or `self` if nothing changed). This enables hash-consing and safe structural sharing.

## Core IR (`ir.py`)

The IR is an immutable, hash-consed expression graph. Every node stores four kinds of data — children, named children, fields, and metadata — described in detail below.

### Node Base Classes

There are three node base classes:

#### `Node`

Base for everything. `Spec` is the only direct `Node` subclass in practice — it holds `cons` (constraints) and `obls` (obligations).

#### `Type`

Types in the IR. Has three **named children** beyond `_children`:

| Named Child | Purpose |
|-------------|---------|
| `ref` | Refinement domain restricting the type's inhabitants |
| `view` | Index view providing alternative indexing structure |
| `obl` | Obligation predicate that must hold |

Key subclasses:

| Node | Meaning |
|------|---------|
| `IntT`, `BoolT`, `UnitT` | Base types |
| `EnumT(name, labels)` | Enumeration type |
| `TupleT(*elTs)` | Product type (variadic) |
| `SumT(*elTs)` | Coproduct type (variadic) |
| `DomT(carT)` | Domain type (carrier type `carT`) |
| `PiT(argT, resT)` | Dependent function type (de Bruijn) |
| `PiTHOAS(argT, resT)` | Dependent function type (HOAS) |
| `FuncT(dom, lamT)` | Concrete function type (domain + lambda type) |
| `ApplyT(piT, arg)` | Type-level application |

`replace()` signature for Type:
```python
node.replace(*new_children, ref=new_ref, view=new_view, obl=new_obl)
```

#### `Value`

Values/expressions in the IR. Has two **named children** beyond `_children`:

| Named Child | Purpose |
|-------------|---------|
| `T` | The type of this value (always present) |
| `obl` | Obligation predicate (`None` = unconditionally valid) |

Key subclasses:

| Node | Meaning |
|------|---------|
| `Lit(T, val=...)` | Literal value |
| `VarHOAS(T, name=...)` | Free variable (HOAS) |
| `BoundVarHOAS(T, name=...)` | Bound variable (HOAS) |
| `LambdaHOAS(T, body)` | Lambda abstraction (HOAS) |
| `Apply(T, func, arg)` | Function application |
| `Sum/Prod/Conj/Disj(T, *args)` | Variadic arithmetic/logic |
| `Eq/Lt/LtEq(T, a, b)` | Comparisons |
| `Fin(T, n)` | Finite domain {0..n-1} |
| `CartProd(T, *doms)` | Cartesian product domain |
| `Image(T, func)` | Image of a function (as a domain) |
| `Singleton(T, val)` | Single-element domain |
| `Card(T, dom)` | Cardinality of a domain |
| `Forall(T, func)` | Universal quantification |
| `IsMember(T, dom, val)` | Domain membership test |

`replace()` signature for Value:
```python
node.replace(*new_children, T=new_T, obl=new_obl)
```

### Four Kinds of Node Data

Every IR node stores four distinct kinds of data. The first three participate in hashing and equality; the fourth does not.

| Kind | Declared via | Accessor | Affects hash/eq | Description |
|------|-------------|----------|----------------|-------------|
| **Children** | `_numc` | `_children` (tuple) | Yes | Structural child Nodes (e.g. the `N` in `Fin(N)`) |
| **Named children** | `_named_children` | `named_children_dict` (dict) | Yes | Node-valued children with specific semantic roles (e.g. `T`, `obl`, `ref`, `view`) |
| **Fields** | `_fields` | `field_dict` (dict) | Yes | Non-Node scalar data (e.g. the `5` in `Lit(5)`, the `idx` in `BoundVar`) |
| **Metadata** | (ad-hoc) | `_metadata` (dict) | No | Non-structural, non-Node data for ad-hoc annotations (e.g. analysis results). Copied on `replace()` but ignored by hash/eq. |

**Children** (`_children`) are the positional structural children of a node, declared via `_numc`. They define the node's tree structure.

**Named children** (`_named_children`) are Node-valued children stored outside `_children`. They have specific semantic roles — a Value's type (`T`), an obligation (`obl`), a refinement domain (`ref`), an index view (`view`). They participate in hashing/equality and are visited by passes, but are tracked separately from `_children` because they have distinct roles and different `replace()` conventions.

**Fields** (`_fields`) are non-Node scalar data like literal values or indices. They are set as instance attributes before calling `super().__init__()` and accessed via `field_dict`.

**Metadata** (`_metadata`) is for ad-hoc non-Node annotations that should not affect identity. Example: storing an `'inj'` flag on a lambda node. Metadata is copied on `replace()` but does not participate in hashing or equality.

#### Accessors

Both `named_children_dict` and `field_dict` are cached properties returning `{name: value}` dicts:

```python
node.named_children_dict  # e.g. {'T': IntT(), 'obl': None}
node.field_dict           # e.g. {'val': 5}
```

### `all_nodes`

Read-only traversal of all Node-valued parts (children + named children):
- `Value.all_nodes` → `(T, *_children, obl?)` (obl only if non-None)
- `Type.all_nodes` → `(*_children, ref?, view?, obl?)`

Use this instead of hand-checking each named child in analyses.

### `replace()`

Returns `self` if nothing changed (identity optimization). Copies `_metadata` to the new node. Named children (`T`, `obl` for Value; `ref`, `view`, `obl` for Type) are **required keyword arguments** — never use sentinel defaults.

### Declaring IR Node Subclasses

Do not use `@dataclass`. Declare `_fields` and `_numc`:

```python
class Eq(Value):
    _numc = 2  # (lhs, rhs)

class Conj(Value):
    _numc = -1  # variadic

class BoundVar(Value):
    _fields = ('idx',)
    _numc = 0
    def __init__(self, T: Type, idx: int, obl=None):
        self.idx = idx
        super().__init__(T, obl=obl)
```

`_numc` semantics:
- `_numc = N` (N >= 0): exactly N children, auto-generates `_arg0`, `_arg1`, ... properties
- `_numc = -1`: variadic, auto-generates `_argN` property returning all children
- `__match_args__` is auto-generated from `_numc` for structural pattern matching

## Binding: HOAS vs de Bruijn

The IR supports two representations for variable binding. Both coexist in the codebase because they serve different phases of the compiler.

### HOAS (Higher-Order Abstract Syntax)

HOAS uses **named bound variables**. Each bound variable carries an explicit `name` field, and the binder (`LambdaHOAS`, `PiTHOAS`) stores the corresponding `bv_name`. Variable identity is determined by name matching.

| Node | Role |
|------|------|
| `BoundVarHOAS(T, closed, name)` | Named bound variable |
| `LambdaHOAS(T, body, bv_name)` | Lambda with named binder |
| `PiTHOAS(argT, resT, bv_name)` | Pi type with named binder |
| `VarHOAS(T, name, kind, metadata)` | Free variable (named) |

HOAS is used during **DSL construction** — when the user writes Python code like `func_var(Cells, Digits, name='F')`, the AST wrapper layer builds HOAS nodes. Named variables are natural here because they come directly from user-supplied names and Python lambda parameters.

```python
# User writes:
F = func_var(Cells, Digits, name='F')
p += Cells.forall(lambda c: F(c) > 0)

# DSL layer builds HOAS nodes:
# LambdaHOAS(body=..., bv_name='c')
# BoundVarHOAS(name='c')
```

### De Bruijn Indices

De Bruijn indexing uses **positional indices** instead of names. A `BoundVar` stores an `idx` (integer) indicating how many binders outward to look: index 0 refers to the innermost enclosing binder, 1 to the next one out, and so on. Binders (`Lambda`, `PiT`) carry no variable name.

| Node | Role |
|------|------|
| `BoundVar(T, idx)` | Positional bound variable (de Bruijn index) |
| `Lambda(T, body)` | Lambda abstraction (no name) |
| `PiT(argT, resT)` | Pi type (no name) |

De Bruijn representation is used during **compilation**. It avoids name-collision issues (no alpha-equivalence needed), makes structural equality trivial, and simplifies substitution in passes like beta reduction. The `ResolveBoundVars` pass converts HOAS nodes to de Bruijn nodes.

```
# HOAS:                          De Bruijn:
# lambda x. lambda y. x + y  =>  Lambda(Lambda(BoundVar(1) + BoundVar(0)))
```

### Which to use

- Writing DSL wrappers or library code (`ast.py`, `libs/`): use HOAS nodes.
- Writing compiler passes (`passes/`): expect and produce de Bruijn nodes (unless the pass specifically handles HOAS, like `BetaReductionHOAS`).

## DSL Wrapper Layer (`ast.py`, `ast_nd.py`)

The wrapper layer provides a Pythonic API over raw IR nodes. These are `@dataclass` classes wrapping `ir.Node`:

```
Expr
├── TExpr       — wraps ir.Type
│   ├── DomainType, IntType, BoolType, ...
└── VExpr       — wraps ir.Value
    ├── IntExpr, BoolExpr, DomainExpr, FuncExpr, TupleExpr, ...
```

Key conventions:
- **Operator overloading** builds IR: `x + y` → `ir.Sum(ir.IntT(), x.node, y.node)`
- **`wrap(node)`** and **`wrapT(node)`** auto-select the right wrapper subclass
- **`.make(val)`** factory methods coerce Python values to wrapper types
- **`.node`** accesses the underlying `ir.Node`
- **`.obl`** returns the obligation as a `BoolExpr` (or `None`)
- **`.guard(p)`** attaches an obligation, conjoining with any existing one
- **`.simplify()`** runs the full optimization pipeline

The `ast_nd.py` module extends this with N-dimensional domains (`NDDomainExpr`) and arrays (`NDArrayExpr`) supporting slicing, tiling, windowing, and rank-polymorphic operations.

**Prefer DSL operators over raw IR constructors** in wrapper code:
```python
# Preferred
new_obl = (self.obl & p).node

# Avoid
new_obl = ir.Conj(ir.BoolT(), self.obl.node, p.node)
```

## Obligations (Guards)

Obligations are boolean predicates that must hold for an expression to be valid. They arise from:
- **Division**: `x / y` generates `obl = (y != 0)`
- **Domain membership**: accessing an array at index `i` generates `obl = (i ∈ dom)`
- **User-specified**: `.guard(p)` on any expression

Guards compose: if a value already has obligation `p`, then `.guard(q)` produces `p & q`.

### Obligation Passes

- **`GuardLift`**: Floats obligations upward out of lambda/PiT bodies. Obligations that depend on a bound variable stay inside the binder; independent ones float to the enclosing scope. This is the only correct way to move obligations through binders.
- **`GuardOpt`**: Removes trivially-true obligations (`obl = Lit(True)` → `obl = None`).

**Critical rule**: Optimization passes must propagate obligations onto replacement nodes using `_with_obl(result, obl)` from `transforms/_obl_utils.py`. This is safe for non-binder nodes. Never propagate obligations through Lambda/PiT — use GuardLift semantics instead.

## Compiler Pass Infrastructure (`pass_base.py`)

### Pass Types

- **`Analysis`**: Read-only. The `run()` method returns an `AnalysisObject` which is stored in `Context`.
- **`Transform`**: Rewrites the IR tree. The `run()` method returns `new_root` or `(new_root, *analysis_objects)`.

Both use `__call__` as the entry point (which sets up caching and calls `run()`). Always invoke via `p(node, ctx)`, not `p.run()`.

### Dispatch with `@handles`

```python
class MyPass(Transform):
    name = "my_pass"

    @handles(ir.Sum, ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        # ... simplification logic ...
        return node.replace(*vc.children, T=vc.T, obl=vc.obl)
```

The `@handles` decorator registers a method to be called for specific node types via `singledispatchmethod`. Multiple `_` methods with different `@handles` decorators can coexist in a single pass. Unhandled nodes fall through to the default `visit()`, which reconstructs the node with visited children and properly propagated named children.

### `visit_children` Returns

Structured results depending on node kind:
- **Value** → `VCValue(children=(...), T=visited_T, obl=visited_obl)`
- **Type** → `VCType(children=(...), ref=visited_ref, view=visited_view, obl=visited_obl)`
- **Other** → plain tuple of visited children

### Transform Handler Pattern

The typical handler pattern:

```python
@handles(ir.SomeNode)
def _(self, node: ir.SomeNode) -> ir.Node:
    vc = self.visit_children(node)       # recurse into children first
    a, b = vc.children                   # destructure visited children
    # ... simplification logic ...
    return _with_obl(result, vc.obl)     # propagate obligations
```

For cases where no simplification applies, reconstruct with visited children:
```python
return node.replace(*vc.children, T=vc.T, obl=vc.obl)
```

### PassManager and Fixed Points

`PassManager` runs a sequence of passes. A **list-of-passes** within the sequence is run as a **fixed-point loop** — it iterates until the IR stops changing (equality check via `__eq__`) or hits `max_iter`.

```python
# From utils.py — the simplification pipeline:
opt_passes = [
    TypeCheckingPass(),      # analysis: run once
    GuardLift(),             # transform: run once
    [                        # fixed-point group:
        CanonicalizePass(),
        ConstFoldPass(),
        AlgebraicSimplificationPass(),
        DomainSimplificationPass(),
        GuardOpt(),
        BetaReductionHOAS(),
        VerifyDag()
    ],
    NDSimplificationPass(),  # transform: run once
]
```

When a transform modifies the IR (detected by `new_root != root`), the `Context` is invalidated — all non-persistent analysis objects are removed. This ensures subsequent passes don't rely on stale analysis results.

### Context and Dependencies

Passes declare their dependencies via class attributes:
- `requires`: tuple of `AnalysisObject` subclasses that must be in the `Context`
- `produces`: tuple of `AnalysisObject` subclasses that this pass adds to `Context`

The `PassManager` automatically runs required analyses if they're missing and registered in `analysis_map`, or if the `AnalysisObject` has a `gen_pass` class attribute pointing to the generating pass.

### Memoization

Both `Analysis` and `Transform` memoize `visit()` calls by default (`enable_memoization = True`). For transforms, `BoundVar` nodes use a cache key that includes the enclosing binder to correctly handle variable scoping. Binder frames (`_bframes`) are pushed/popped when entering/leaving `Lambda` and `PiT` nodes.

## How to Add a New Pass

### 1. Create the pass file

Create a new file in the appropriate directory:
- `compiler/passes/transforms/my_pass.py` for a transform
- `compiler/passes/analyses/my_pass.py` for an analysis

### 2. Define the pass class

```python
# transforms/my_pass.py
from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir
from ._obl_utils import _with_obl
import typing as tp


class MyPass(Transform):
    name = "my_pass"
    requires: tp.Tuple[type, ...] = ()   # AnalysisObject subclasses needed
    produces: tp.Tuple[type, ...] = ()   # AnalysisObject subclasses produced

    def run(self, root: ir.Node, ctx: Context):
        return self.visit(root)

    @handles(ir.Sum)
    def _(self, node: ir.Sum) -> ir.Node:
        vc = self.visit_children(node)
        children = vc.children
        # ... your rewrite logic ...
        return node.replace(*children, T=vc.T, obl=vc.obl)

    @handles(ir.Eq, ir.Lt)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        a, b = vc.children
        # ... your rewrite logic ...
        return _with_obl(result, vc.obl)
```

For an analysis:

```python
# analyses/my_analysis.py
from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir


class MyResult(AnalysisObject):
    """Stores the analysis result."""
    def __init__(self, data):
        self.data = data


class MyAnalysis(Analysis):
    name = "my_analysis"
    requires: tuple = ()
    produces = (MyResult,)

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.data = {}
        self.visit(root)
        return MyResult(self.data)

    @handles(ir.VarHOAS)
    def _(self, node: ir.VarHOAS):
        self.data[node.name] = node
        self.visit_children(node)
```

### 3. Export from `__init__.py`

For transforms, add an import in `compiler/passes/transforms/__init__.py`:

```python
from .my_pass import MyPass
```

### 4. Register in the pipeline (if needed)

If the pass should run during `spec.optimize()`, add it to the pass list in `compiler/passes/utils.py`:

```python
opt_passes = [
    TypeCheckingPass(),
    GuardLift(),
    [
        CanonicalizePass(),
        ConstFoldPass(),
        AlgebraicSimplificationPass(),
        DomainSimplificationPass(),
        GuardOpt(),
        BetaReductionHOAS(),
        MyPass(),              # add here if it should be in the fixed-point loop
        VerifyDag()
    ],
    NDSimplificationPass(),
]
```

Passes inside the `[...]` list run in a fixed-point loop. Passes outside run once. Place your pass accordingly.

### 5. Write tests

Create a test file in `tests/test_passes/`:

```python
# tests/test_passes/test_my_pass.py
from puzzlespec.compiler.dsl import ir
from puzzlespec.compiler.passes.pass_base import Context
from puzzlespec.compiler.passes.transforms.my_pass import MyPass


def test_basic():
    # Build an IR node
    node = ir.Sum(ir.IntT(), ir.Lit(ir.IntT(), 1), ir.Lit(ir.IntT(), 2))
    ctx = Context()
    result, _ = MyPass()(node, ctx)
    assert result == ir.Lit(ir.IntT(), 3)
```

## Naming Conventions

- **Type IR nodes**: `T` suffix — `BoolT`, `IntT`, `DomT`, `PiT`
- **Value IR nodes**: descriptive names — `Lit`, `Eq`, `Forall`, `CartProd`
- **Abstract/base variants**: leading `_` — `_PiT`, `_Lambda`
- **HOAS variants**: explicit suffix — `PiTHOAS`, `LambdaHOAS`, `BoundVarHOAS`
- **De Bruijn variants**: no suffix — `Lambda`, `BoundVar`, `PiT`
- **Compiler passes**: `Pass` suffix — `ConstFoldPass`, `TypeCheckingPass`
- **Common short names**: `T` (type), `ctx` (context), `bv` (bound variable), `dom` (domain), `val` (value), `vc` (visit_children result)

## Compilation Pipeline

```
User Python code
  → PuzzleSpecBuilder (collects constraints via +=)
  → p.build("name") → PuzzleSpec (raw IR, HOAS binding)
  → spec.optimize() → PuzzleSpec (simplified IR)
  → SMT backend (future)
```

The `optimize()` method calls `simplify()` from `passes/utils.py`, which assembles and runs the `PassManager` with:

1. **TypeCheckingPass** — analysis, run once
2. **GuardLift** — float obligations out of binders
3. **Fixed-point loop**:
   - CanonicalizePass
   - ConstFoldPass
   - AlgebraicSimplificationPass
   - DomainSimplificationPass
   - GuardOpt
   - BetaReductionHOAS
   - VerifyDag
4. **NDSimplificationPass** — run once after fixed point
