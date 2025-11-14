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

    @property
    def is_lit(self):
        return isinstance(self, Lit)

    @property
    def num_children(self):
        return len(self._children)

    def _gen_key(self):
        child_keys = tuple(c._key for c in self._children)
        assert None not in child_keys
        fields = tuple(getattr(self, field, None) for field in self._fields)
        assert None not in fields
        priority = NODE_PRIORITY[(type(self))]
        key = (priority, self.__class__.__name__, fields, child_keys)
        return key

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

# Core Nodes

# Background info: Containers are represented a 'Func[Dom(A) -> B]'
# So a 'List[B]' would be Func(Fin(n) -> B).
# And a Set[B] would be Func(Dom(B) -> Bool)
# A Func[Dom(A) -> B] is typed as Arrow[carrier(A) -> B]
# Every Func has an tag stored in an envrionment indicating typeclass-like properties (seq, etc...) along with the Dom stored (or that info is derivable)

##############################
## Core-level IR nodes (Used throughout entire compiler flow)
##############################

class Unit(Node):
    _numc = 0
    def __init__(self):
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

# (lamda x:paramT body) -> (paramT -> type(body))
class Lambda(Node):
    _fields = ('paramT',)
    _numc = 1
    def __init__(self, body: Node, paramT: irT.Type_):
        self.paramT = paramT
        super().__init__(body)

### Int/Bool 

# Literal value for any base type
class Lit(Node):
    _fields = ("val", "T")
    _numc = 0
    def __init__(self, val: tp.Any, T: irT.Type_):
        assert T in (irT.Bool, irT.Int)
        self.T = T
        self.val = T.cast_as(val)
        super().__init__()

class Eq(Node):
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

class Ite(Node):
    _numc = 3
    def __init__(self, pred: Node, t: Node, f: Node):
        super().__init__(pred, t, f)

class Not(Node):
    _numc = 1
    def __init__(self, a: Node):
        super().__init__(a)

class Neg(Node):
    _numc = 1
    def __init__(self, a: Node):
        super().__init__(a)

class Div(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Mod(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class Conj(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)

class Disj(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)

# integer sum
class Sum(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)

# integer product
class Prod(Node):
    _numc = -1
    def __init__(self, *args: Node):
        super().__init__(*args)

## Domains

# Dom(T)
class Universe(Node):
    _fields = ('T',)
    _numc = 0
    def __init__(self, T: irT.Type_):
        self.T = T
        super().__init__()

# Int -> Dom[Int]
class Fin(Node):
    _numc = 1
    def __init__(self, N: Node):
        super().__init__(N)

# Dom[EnumT]
class Enum(Node):
    _fields = ("enumT",)
    _numc = 0
    def __init__(self, enumT: irT.EnumT):
        self.enumT = enumT
        super().__init__()

# Dom[EnumT] -> EnumT
class EnumLit(Node):
    _fields = ("enumT", "label")
    _numc = 0
    def __init__(self, enumT: irT.EnumT, label: str):
        self.enumT = enumT
        self.label = label
        super().__init__()

# Get the size of a domain
# Dom(A) -> Int
class Card(Node):
    _numc = 1
    def __init__(self, domain: Node):
        super().__init__(domain)

# Dom(A) -> A -> Bool 
class IsMember(Node):
    _numc = 2
    def __init__(self, domain: Node, val: Node):
        super().__init__(domain, val)

## Cartesian Products

# (Dom[A], Dom[B],...) -> Dom(AxBx...)
class CartProd(Node):
    _numc = -1
    def __init__(self, *doms: Node):
        super().__init__(*doms)

# Dom(AxB,...) -> 0 -> A | 1 -> B | ...
class DomProj(Node):
    _fields = ('idx',)
    _numc = 1
    def __init__(self, dom: Node, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(dom)

class TupleLit(Node):
    _numc = -1
    def __init__(self, *vals: Node):
        super().__init__(*vals)

class Proj(Node):
    _fields = ('idx',)
    _numc = 1
    def __init__(self, tup: Node, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(tup)

class DisjUnion(Node):
    _numc = -1
    def __init__(self, *doms: Node):
        super().__init__(*doms)

class DomInj(Node):
    _fields = ('idx', 'T')
    _numc = 1
    def __init__(self, dom: Node, idx: int, T: irT.Type_):
        assert isinstance(idx, int)
        self.idx = idx
        self.T = T
        super().__init__(dom)

# Injection for disjoint unions
class Inj(Node):
    _fields = ("idx", "T")
    _numc = 1
    def __init__(self, val: Node, idx: int, T: irT.Type_):
        assert isinstance(idx, int)
        self.T = T
        self.idx = idx
        super().__init__(val)

# (A|B|...) -> (A->T, B->T,...) -> T
class Match(Node):
    _numc = 2
    def __init__(self, scrut: Node, branches: Node):
        # Branches should be tuple of lambdas. checked during type checking
        super().__init__(scrut, branches)

# Dom(A) -> (A->Bool) -> Dom(A)
class Restrict(Node):
    _numc = 2
    def __init__(self, domain: Node, pred: Node):
        super().__init__(domain, pred)

# Dom(A) -> (A -> Bool) -> Bool
class Forall(Node):
    _numc = 2
    def __init__(self, domain: Node, fun: Node):
        super().__init__(domain, fun)

# Dom(A) -> (A -> Bool) -> Bool
class Exists(Node):
    _numc = 2
    def __init__(self, domain: Node, fun: Node):
        super().__init__(domain, fun)

# Dom(A) -> (AxA->Bool) -> Dom(Dom(A))
class Quotient(Node):
    _numc = 2
    def __init__(self, domain: Node, eqrel: Node):
        super().__init__(domain, eqrel)



## Funcs (i.e., containers)

# Dom(A) -> (A->B) -> Func(Dom(A)->B)
class Tabulate(Node):
    _numc=2
    def __init__(self, dom: Node, fun: Node):
        super().__init__(dom, fun)

# Get domain of container
# Func(Dom(A) -> B) -> Dom(A)
class DomOf(Node):
    _numc = 1
    def __init__(self, func: Node):
        super().__init__(func)

class ImageOf(Node):
    _numc = 1
    def __init__(self, func: Node):
        super().__init__(func)

# Func(Dom(A)->B) -> A -> B
class Apply(Node):
    _numc = 2
    def __init__(self, func: Node, arg: Node):
        super().__init__(func, arg)

#(v0:A,v1:A,...) -> Func(Fin(n) -> A)
class ListLit(Node):
    _numc = -1
    def __init__(self, *vals: Node):
        super().__init__(*vals)

# only used on Seq Funcs TODO maybe should have scan as the fundimental IR node
# Seq[A] -> ((A,B) -> B) -> B -> B
class Fold(Node):
    _numc = 3
    def __init__(self, func: Node, fun: Node, init: Node):
        super().__init__(func, fun, init)

##############################
## Surface-level IR nodes (Used for analyis, but can be collapes)
##############################

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

class Gt(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

class GtEq(Node):
    _numc = 2
    def __init__(self, a: Node, b: Node):
        super().__init__(a, b)

# Array[A] -> Int -> Int -> Array[Fin(n) -> Array[A]]
class Windows(Node):
    _numc = 3
    def __init__(self, list: Node, size: Node, stride: Node):
        super().__init__(list, size, stride)

# NDDom[A] -> (Int,...) -> (Int,...) -> Array[Fin(n1) x Fin(n2) x ... -> NDDom[A]]
class Tiles(Node):
    _numc = 3
    def __init__(self, dom: Node, sizes: Node, strides: Node):
        super().__init__(dom, sizes, strides)

# creates an array of slices in a given index
class Slices(Node):
    _fields = ('idx',)
    _numc = 1
    def __init__(self, dom: Node, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(dom)

# Common Fold Nodes
class SumReduce(Node):
    _numc = 1
    def __init__(self, func: Node):
        super().__init__(func)

class ProdReduce(Node):
    _numc = 1
    def __init__(self, func: Node):
        super().__init__(func)

class AllDistinct(Node):
    _numc = 1
    def __init__(self, func: Node):
        super().__init__(func)

class AllSame(Node):
    _numc = 1
    def __init__(self, func: Node):
        super().__init__(func)

##############################
## Constructor-level IR nodes (Used for construction but immediatley gets transformed)
##############################

# gets tranformed to a de-bruijn BoundVar
class _BoundVarPlaceholder(Node):
    _fields = ('dom', 'T','is_tabulate')
    _numc = 0
    def __init__(self, dom: Node, T: irT.Type_, is_tabulate: bool):
        self.T = T
        self.dom = dom
        self.is_tabulate = is_tabulate
        super().__init__()

class _LambdaPlaceholder(Node):
    #_fields = ('paramT',)
    _numc = 2
    def __init__(self, bound_var: Node, body: Node):
        #self.paramT = paramT
        super().__init__(bound_var, body)


# Mapping from Node classes to a priority integer.
# This is probably way overengineered and there are probably better priorities
NODE_PRIORITY: tp.Dict[tp.Type[Node], int] = {
    Unit: -1,
    Lit: 0,
    VarRef: 1,
    BoundVar: 2,
    _BoundVarPlaceholder: 2,
    Not: 3,
    Neg: 3,
    And: 4,
    Or: 4,
    Implies: 5,
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
    Ite: 8,
    Conj: 8,
    Disj: 8,
    Sum: 8,
    Prod: 8,
    Universe: 9,
    Fin: 9,
    Enum: 9,
    EnumLit: 9,
    Card: 9,
    IsMember: 9,
    CartProd: 9,
    DomProj: 9,
    TupleLit: 9,
    Proj: 9,
    DisjUnion: 9,
    DomInj: 9,
    Inj: 9,
    Match: 9,
    Restrict: 9,
    Quotient: 9,
    Tabulate: 10,
    DomOf: 10,
    ImageOf: 10,
    Apply: 10,
    ListLit: 10,
    Windows: 10,
    Tiles: 10,
    Slices: 10,
    Lambda: 12,
    _LambdaPlaceholder: 12,
    Fold: 13,
    SumReduce: 14,
    ProdReduce: 14,
    Forall: 14,
    Exists: 14,
    AllDistinct: 14,
    AllSame: 14,
}

