# DSL Building Blocks (v 1)

This file lists the *core* pieces we settled on for a typed-AST façade that supports
symbolic 2-D grids (cells / edges / vertices), list and grid windows, and a minimal
generic IR.

---

## 1  IR / AST Node Kinds

| Node class | Important tag / fields | Purpose |
|------------|------------------------|---------|
| **`Node`** | `children: tuple[Node,…]` | Base; enables uniform traversal. |
| `IntLit`, `BoolLit`, `Var` | — | Numeric / Boolean literals, symbolic params. |
| `Add`, `SubNode`, `MulNode`, `DivNode` | `lhs`, `rhs` | Integer arithmetic. |
| `LambdaNode` | `var_name`, `param_type`, `body` | λ-abstraction (for functions). |
| `ListNode`, `DictNode` | `elements`, `items` | Literal containers. |
| `MapNode` | `lst`, `fn` | Point-wise map over a list. |
| `ListWindowNode` | `k` (window length) | 1-D sliding-window transform. |
| `GridEnumNode` | `mode ∈ {cells, vtx, eH, eV, rows, cols}` | Enumerate flat domains or row/col lists. |
| `GridSliceNode` | `axis ∈ {row, col}`, `index` | Single row or column slice. |
| `GridWindowEnumNode` | `h, w`, `sR, sC` | 2-D tile enumeration (windows with stride). |
| `GridTabulateNode` | `nR`, `nC` | Identity grid: `(r,c) ↦ CellIdx`. |

All nodes inherit from **`Node`** and store only their children.

---

## 2  Façade / `Expr` Wrapper Classes

| Wrapper | Generic params | Notes / helpers |
|---------|----------------|-----------------|
| **`Expr`** | —  | Base; holds `.node`, `.type`, integer `+`. |
| `IntExpr`, `BoolExpr` | —  | Ground scalar values. |
| `ListExpr[T]` | `T : Expr` | `.map`, `.windows`, `.elem_type`. |
| `DictExpr[K,V]` | `K`, `V` | Dict-specific helpers (future). |
| `ArrowExpr[P,R]` | `P`, `R` | Callable wrapper for functions. |
| `GridExpr[V]` | `V : Expr` | `.cells()`, `.rows()`, `.cols()`, `.tiles()`, `.index_grid()`. |
| `CellIdxExpr`, `VertexIdxExpr`, `EdgeIdxExpr` | — | Abstract coordinate values (opaque). |

`wrap(node, type)` creates the right subclass and memoises it.

---

## 3  First-Class Type Objects

| Type | Fields | Meaning |
|------|--------|---------|
| `Int`, `Bool` | — | Ground scalar singletons. |
| `Arrow` | `param`, `result` | Function type. |
| `ListT` | `elem`, `len (Node\|None)` | 1-D list with (symbolic) length. |
| `DictT` | `key`, `value` | Homogeneous dict. |
| `TupleT` | `elts` | n-ary product. |
| **`GridT`** | `value : Type_`<br>`nR, nC : Node`<br>`domain : {cells, vtx, eH, eV}` | 2-D lattice with symbolic shape *and* domain tag. |
| `CellIdx`, `VertexIdx`, `EdgeIdx` | — | Abstract index sorts shown to DSL users. |

`GridT`’s `domain` tag distinguishes cells vs. vertices vs. horizontal /
vertical edges irrespective of element type transformations.

---