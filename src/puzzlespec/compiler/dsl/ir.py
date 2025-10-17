from __future__ import annotations
from dataclasses import field
import typing as tp
from ..dsl import ir_types as irT
import inspect
import sys
from typing import Any, get_type_hints

# Base class for IR
class Node:
    _fields: tp.Tuple[str, ...] = ()
    def __init__(self, *children: 'Node'):
        for child in children:
            if not isinstance(child, Node):
                raise TypeError(f"Expected Node, got {child}")
        if self._numc >= 0 and len(children) != self._numc:
            raise TypeError(f"Expected {self._numc} children, got {len(children)}")
        self._children: tp.Tuple[Node, ...] = children
        self._key = self._gen_key()

    def _gen_key(self):
        child_keys = tuple(c._key for c in self._children)
        assert None not in child_keys
        fields = tuple(getattr(self, field, None) for field in self._fields)
        assert None not in fields
        priority = NODE_PRIORITY[(type(self))]
        key = (priority, self.__class__.__name__, fields, child_keys)
        return key

    # TODO might want to make this more strict
    # def __eq__(self, other: 'Node'):
    #    return self._key == other._key

    def __iter__(self):
        return iter(self._children)
    
    def __repr__(self):
        field_str = ",".join([f"{k}={v}" for k,v in self.field_dict.items()])
        if field_str:
            field_str = f"[{field_str}]"
        return f"{self.__class__.__name__}{field_str}({', '.join(repr(c) for c in self._children)})"
    
    @property
    def field_dict(self):
        return {f: getattr(self, f) for f in self._fields}

    def replace(self, *new_children: 'Node', **kwargs: tp.Any) -> 'Node':
        new_fields = {**self.field_dict, **kwargs}
        if new_children == self._children and new_fields == self.field_dict:
            return self
        return type(self)(*new_children, **new_fields)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        numc = getattr(cls, '_numc', None)
        assert numc is not None and numc >= -1
        # variadic
        if numc == -1:
            match_args = ('_argN',)
            def _argN(self):
                return self._children
            setattr(cls, '_argN', property(_argN))
        else:
            match_args = tuple(f"_arg{i}" for i in range(numc))
            def make_getter(i):
                def getter(self):
                    return self._children[i]
                return property(getter)
            for i in range(numc):
                name = f"_arg{i}"
                setattr(cls, name, make_getter(i))
        setattr(cls, "__match_args__", match_args)

# Literal value
class Lit(Node):
    _fields = ("value", "T")
    _numc = 0
    def __init__(self, value: tp.Any, T: irT.Type_):
        assert T in (irT.Bool, irT.Int)
        self.T = T
        self.value = T.cast_as(value)
        super().__init__()


# User-defined parameter
# Eventually gets transformed into a normal VarRef with a 'P' role
class _Param(Node):
    _fields = ("name", "T")
    _numc = 0
    def __init__(self, name: str, T: irT.Type_):
        assert T in (irT.Bool, irT.Int)
        self.name = name
        self.T = T
        super().__init__()

class VarRef(Node):
    _fields = ("sid",)
    _numc = 0
    def __init__(self, sid: int):
        self.sid = sid
        super().__init__()

class BoundVar(Node):
    _fields = ('idx',) # De Bruijn index
    _numc = 0
    def __init__(self, idx: int):
        self.idx = idx
        super().__init__()

class _BoundVarPlaceholder(Node):
    _numc = 0
    def __init__(self):
        super().__init__()

# Arith + Boolean
class Eq(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class And(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Implies(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Or(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Not(Node):
    _numc = 1
    def __init__(self, a: Node):
        super().__init__(a)

class Neg(Node):
    _numc = 1
    def __init__(self, a: Node):
        super().__init__(a)

class Add(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Sub(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Mul(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Div(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Mod(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Gt(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class GtEq(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Lt(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class LtEq(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

# VARIADIC
class Conj(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)

class Disj(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)

class Sum(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)

class Prod(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)



## COLLECTIONS

## Tuple nodes

# Concrete tuple
class Tuple(Node):
    _numc = -1
    def __init__(self, *elements: Node):
        super().__init__(*elements)

# No Tuple tabulate till I need it
class TupleGet(Node):
    _fields = ('idx',)
    _numc = 1
    def __init__(self, tup: Node, idx: int):
        self.idx = idx
        super().__init__(tup)

## List Nodes

# Concrete list
class List(Node):
    _numc = -1
    def __init__(self, *elements: Node):
        super().__init__(*elements)

# Represents a symbolic list
class ListTabulate(Node):
    _numc = 2
    def __init__(self, size: Node, fun: Node):
        super().__init__(size, fun)

# Operations on lists
class ListGet(Node):
    _numc = 2
    def __init__(self, list: Node, idx: Node):
        super().__init__(list, idx)

class ListLength(Node):
    _numc = 1
    def __init__(self, list: Node):
        super().__init__(list)

# Enumerate a list of windows
class ListWindow(Node):
    _numc = 3
    def __init__(self, list: Node, size: Node, stride: Node):
        super().__init__(list, size, stride)

class ListConcat(Node): 
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

# List predicates/utilities
class ListContains(Node):
    _numc = 2
    def __init__(self, list: Node, elem: Node):
        super().__init__(list, elem)

class OnlyElement(Node):
    """Return the only element of a list; intended to be guarded by ListLength == 1."""
    _numc = 1
    def __init__(self, list: Node):
        super().__init__(list)

## Dict Nodes

# Concrete dict
class Dict(Node):
    _numc = -1
    def __init__(self, *flat_key_vals: Node):
        if len(flat_key_vals) % 2 != 0:
            raise ValueError("Keys and values must have the same length")
        super().__init__(*flat_key_vals)

    def keys(self) -> tp.List[Node]:
        return self._children[::2]

    def values(self) -> tp.List[Node]:
        return self._children[1::2]

    def _size(self):
        return len(self._children)//2

# Represents a symbolic dict (Tabulated from keys)
class DictTabulate(Node):
    _numc = 2
    def __init__(self, keys: Node, fun: Node):
        super().__init__(keys, fun)

# Operators on dicts
class DictGet(Node):
    _numc = 2
    def __init__(self, dict: Node, key: Node):
        super().__init__(dict, key)

class DictMap(Node):
    _numc = 2
    def __init__(self, dict: Node, fun: Node):
        super().__init__(dict, fun)

class DictLength(Node):
    _numc = 1
    def __init__(self, dict: Node):
        super().__init__(dict)


# PRIORITY 1
## Grid Nodes

# A concrete grid
class Grid(Node):
    _fields = ("nR", "nC")
    _numc = -1
    def __init__(self, *elements: Node, nR: int, nC: int):
        self.nR = nR
        self.nC = nC
        assert len(elements) == nR*nC
        super().__init__(*elements)

# A symbolic Grid
class GridTabulate(Node):
    _numc = 3
    def __init__(self, nR: Node, nC: Node, fun: Node):
        super().__init__(nR, nC, fun)

# enumerate cells, rows, cols, edges, etc
# TODO might want to split into individual nodes
class GridEnumNode(Node):
    _fields = ("mode",)
    _numc = 2
    def __init__(self, nR: Node, nC: Node, mode: str):
        if mode not in ('CellGrid', 'Cells', 'Rows', 'Cols'):
            raise NotImplementedError(f"{mode} not supported for GridEnum")
        self.mode = mode
        super().__init__(nR, nC)

class GridFlatNode(Node):
    _numc = 1
    def __init__(self, grid: Node):
        super().__init__(grid)

# 2-D sliding window
class GridWindowNode(Node):
    _numc = 5
    def __init__(self, grid: Node, size_r: Node, size_c: Node, stride_r: Node, stride_c: Node):
        super().__init__(grid, size_r, size_c, stride_r, stride_c)

class GridDims(Node):
    _numc = 1
    def __init__(self, grid: Node):
        super().__init__(grid)

## PRIORITY 0   
## Higher Order Operators
class Lambda(Node):
    _fields = ('paramT',)
    _numc = 1
    def __init__(self, body: Node, paramT: irT.Type_):
        self.paramT = paramT
        super().__init__(body)

class _LambdaPlaceholder(Node):
    _fields = ('paramT',)
    _numc = 2
    def __init__(self, bound_var: Node, body: Node, paramT: irT.Type_):
        self.paramT = paramT
        super().__init__(bound_var, body)

class Map(Node):
    _numc = 2
    def __init__(self, domain: Node, fun: Node):
        super().__init__(domain, fun)

class Fold(Node):
    _numc = 3
    def __init__(self, domain: Node, fun: Node, init: Node):
        super().__init__(domain, fun, init)

# Common Fold Nodes
class SumReduce(Node):
    _numc = 1
    def __init__(self, vals: Node):
        super().__init__(vals)

class ProdReduce(Node):
    _numc = 1
    def __init__(self, vals: Node):
        super().__init__(vals)

class Forall(Node):
    _numc = 2
    def __init__(self, domain: Node, fun: Node):
        super().__init__(domain, fun)

class Exists(Node):
    _numc = 2
    def __init__(self, domain: Node, fun: Node):
        super().__init__(domain, fun)

class Distinct(Node):
    _numc = 1
    def __init__(self, vals: Node):
        super().__init__(vals)


# Mapping from Node classes to a priority integer.
# This is probably way overengineered and there are probably better priorities
NODE_PRIORITY: tp.Dict[tp.Type[Node], int] = {
    Lit: 0,
    _Param: 1,
    VarRef: 1,
    BoundVar: 2,
    _BoundVarPlaceholder: 2,
    Not: 3,
    And: 4,
    Or: 4,
    Implies: 5,
    Neg: 3,
    Add: 4,
    Sub: 4,
    Mul: 5,
    Div: 5,
    Mod: 5,
    Eq: 6,
    Gt: 7,
    GtEq: 7,
    Lt: 7,
    LtEq: 7,
    Conj: 8,
    Disj: 8,
    Sum: 8,
    Prod: 8,
    Tuple: 9,
    TupleGet: 9,
    List: 9,
    ListTabulate: 9,
    ListGet: 9,
    ListLength: 9,
    ListWindow: 9,
    ListConcat: 9,
    ListContains: 9,
    OnlyElement: 9,
    Dict: 10,
    DictTabulate: 10,
    DictGet: 10,
    DictMap: 10,
    DictLength: 10,
    Grid: 11,
    GridTabulate: 11,
    GridEnumNode: 11,
    GridFlatNode: 11,
    GridWindowNode: 11,
    GridDims: 11,
    Lambda: 12,
    _LambdaPlaceholder: 12,
    Map: 13,
    Fold: 13,
    SumReduce: 14,
    ProdReduce: 14,
    Forall: 14,
    Exists: 14,
    Distinct: 14,
}