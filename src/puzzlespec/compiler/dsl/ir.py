import typing as tp
from ..dsl import ir_types as irT

# Base class for IR
class Node:
    _fields: tp.Tuple[str, ...] = ()
    def __init__(self, *children: 'Node'):
        for child in children:
            if not isinstance(child, Node):
                raise TypeError(f"Expected Node, got {child}")
        self._children: tp.Tuple[Node, ...] = children

    def __iter__(self):
        return iter(self._children)
    
    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(repr(c) for c in self._children)})"

    def replace(self, *new_children: 'Node', **kwargs: tp.Any) -> 'Node':
        fields = {f: getattr(self, f) for f in self._fields}
        fields.update(kwargs)
        return type(self)(*new_children, **fields)

class VarRef(Node):
    _fields = ("sid",)
    def __init__(self, sid: int):
        self.sid = sid
        super().__init__()

class BoundVar(Node):
    _fields = ('idx') # De Bruijn index
    def __init__(self, idx: int):
        self.idx = idx
        super().__init__()

class _BoundVarPlaceholder(Node):
    def __init__(self):
        super().__init__()

# Literal value
class Lit(Node):
    _fields = ("value", "T")
    def __init__(self, value: tp.Any, T: irT.Type_):
        assert T in (irT.Bool, irT.Int)
        self.T = T
        self.value = T.cast_as(value)
        super().__init__()

# User-defined parameter
# Uniquified by 'name'.
# Eventually gets transformed into a normal VarRef with a 'P' role
class _Param(Node):
    _fields = ("name", "T")
    def __init__(self, name: str, T: irT.Type_):
        assert T in (irT.Bool, irT.Int)
        self.name = name
        self.T = T
        super().__init__()

# Base Type operators
class Eq(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class And(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Implies(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Or(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Not(Node):
    def __init__(self, a: Node):
        super().__init__(a)

# Variadic logical nodes
class Conj(Node):
    def __init__(self, *args: Node):
        super().__init__(*args)

class Disj(Node):
    def __init__(self, *args: Node):
        super().__init__(*args)

class Neg(Node):
    def __init__(self, a: Node):
        super().__init__(a)

class Add(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Sub(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Mul(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Div(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Mod(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Gt(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class GtEq(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Lt(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class LtEq(Node):
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)


## COLLECTIONS

## Tuple nodes

# Concrete tuple
class Tuple(Node):
    def __init__(self, *elements: Node):
        super().__init__(*elements)

# TODO Do I need a Tuple Tabulate?

## List Nodes

# Concrete list
class List(Node):
    def __init__(self, *elements: Node):
        super().__init__(*elements)

# Represents a symbolic list
class ListTabulate(Node):
    def __init__(self, size: Node, fun: Node):
        super().__init__(size, fun)

# Operations on lists
class ListGet(Node):
    def __init__(self, list: Node, idx: Node):
        super().__init__(list, idx)

class ListLength(Node):
    def __init__(self, list: Node):
        super().__init__(list)

# Enumerate a list of windows
class ListWindow(Node):
    def __init__(self, list: Node, size: Node, stride: Node):
        super().__init__(list, size, stride)

class ListConcat(Node): 
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)


# List predicates/utilities
class ListContains(Node):
    def __init__(self, list: Node, elem: Node):
        super().__init__(list, elem)

class OnlyElement(Node):
    """Return the only element of a list; intended to be guarded by ListLength == 1."""
    def __init__(self, list: Node):
        super().__init__(list)


## Dict Nodes

# Concrete dict
class Dict(Node):
    def __init__(self, *flat_key_vals: Node):
        if len(flat_key_vals) % 2 != 0:
            raise ValueError("Keys and values must have the same length")
        super().__init__(*flat_key_vals)

    def keys(self) -> tp.List[Node]:
        return self._children[::2]

    def values(self) -> tp.List[Node]:
        return self._children[1::2]

# Represents a symbolic dict (Tabulated from keys)
class DictTabulate(Node):
    def __init__(self, keys: Node, fun: Node):
        super().__init__(keys, fun)

# Operators on dicts
class DictGet(Node):
    def __init__(self, dict: Node, key: Node):
        super().__init__(dict, key)

class DictMap(Node):
    def __init__(self, dict: Node, fun: Node):
        super().__init__(dict, fun)

class DictLength(Node):
    def __init__(self, dict: Node):
        super().__init__(dict)

## Grid Nodes

# A concrete grid
class Grid(Node):
    _fields = ("nR", "nC")
    def __init__(self, *elements: Node, nR: int, nC: int):
        self.nR = nR
        self.nC = nC
        super().__init__(*elements)

# A symbolic Grid
class GridTabulate(Node):
    def __init__(self, nR: Node, nC: Node, fun: Node):
        super().__init__(nR, nC, fun)

# enumerate cells, rows, cols, edges, etc
class GridEnumNode(Node):
    _fields = ("mode",)
    def __init__(self, nR: Node, nC: Node, mode: str):
        self.mode = mode
        super().__init__(nR, nC)

## Single slice of a grid (mode = "C" | "V" | "EV" | "EH")
#class GridSliceNode(Node):
#    def __init__(self, mode: str, grid: Node, slice_idx: Node):
#        self.mode = mode
#        super().__init__(grid, slice_idx)

# 2-D sliding window
class GridWindowNode(Node):
    def __init__(self, grid: Node, size_r: Node, size_c: Node, stride_r: Node, stride_c: Node):
        super().__init__(grid, size_r, size_c, stride_r, stride_c)


class GridNumRows(Node):
    def __init__(self, grid: Node):
        super().__init__(grid)
    
class GridNumCols(Node):
    def __init__(self, grid: Node):
        super().__init__(grid)


# Grid cell selection helpers (for tactics/spec ergonomics)
class GridCellAt(Node):
    """Select the unique cell at the intersection of a row list and a col list.

    Children:
      - row_cells: Node (list of cell indices)
      - col_cells: Node (list of cell indices)
    """

    def __init__(self, row_cells: Node, col_cells: Node):
        super().__init__(row_cells, col_cells)

## Higher Order Operators
class _LambdaPlaceholder(Node):
    _fields = ('paramT',)
    def __init__(self, bound_var: Node, body: Node, paramT: irT.Type_):
        self.paramT = paramT
        super().__init__(bound_var, body)

class Lambda(Node):
    _fields = ('paramT',)
    def __init__(self, body: Node, paramT: irT.Type_):
        self.paramT = paramT
        super().__init__(body)

class Sum(Node):
    def __init__(self, vals: Node):
        super().__init__(vals)

class Distinct(Node):
    def __init__(self, vals: Node):
        super().__init__(vals)

class Forall(Node):
    def __init__(self, domain: Node, fun: Node):
        super().__init__(domain, fun)

class Map(Node):
    def __init__(self, domain: Node, fun: Node):
        super().__init__(domain, fun)
