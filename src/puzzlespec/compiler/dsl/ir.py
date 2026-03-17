from __future__ import annotations
import typing as tp
# Unified Types and IR
from dataclasses import dataclass
import functools as ft

# Every node stores three kinds of data:
#   1. _children:       structural child Nodes (e.g. the N in Fin(N))
#   2. _named_children: named child Nodes (e.g. T, obl, ref, view)
#   3. _fields:         non-Node scalar data (e.g. the 5 in Lit(5))
# All three participate in hashing and equality.
# A fourth kind, _metadata, holds ad-hoc non-Node data (e.g. analysis results)
# that does NOT affect hashing or equality but is copied on replace().
_op_cnt = 0
class Node:
    _fields: tp.Tuple[str, ...] = ()
    _named_children: tp.Tuple[str, ...] = ()

    def __init__(self, *children: 'Node'):
        for child in children:
            if not isinstance(child, Node):
                raise TypeError(f"Expected Node, got {child}: {type(child)}")
        if self._numc >= 0 and len(children) != self._numc:
            raise TypeError(f"Expected {self._numc} children, got {len(children)}")
        self._children: tp.Tuple[Node, ...] = children
        self._metadata = {}

    # ---- Hashing (all 3 kinds contribute) ----

    @ft.cached_property
    def _hash(self):
        return hash((
            self._opcode,
            tuple(self.field_dict.values()),
            tuple(c._hash for c in self._children),
            tuple(
                nc._hash if nc is not None else -(i + 1)
                for i, nc in enumerate(self.named_children_dict.values())
            ),
        ))

    def __hash__(self) -> int:
        return self._hash

    # ---- Equality (all 3 kinds contribute) ----

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, Node):
            return False
        if self._hash != other._hash:
            return False
        return (self._opcode == other._opcode
                and self.field_dict == other.field_dict
                and self._children == other._children
                and self.named_children_dict == other.named_children_dict)

    def __lt__(self, other: 'Node'):
        if self._opcode != other._opcode:
            return NODE_PRIORITY[type(self)] < NODE_PRIORITY[type(other)]
        if self.field_vals != other.field_vals:
            return self.field_vals < other.field_vals
        return self._children < other._children

    # ---- Accessors ----

    @property
    def num_children(self):
        return len(self._children)

    @property
    def all_nodes(self) -> tp.Tuple['Node', ...]:
        """All Node-valued parts: _children + non-None named children."""
        named = tuple(nc for nc in self.named_children_dict.values() if nc is not None)
        return self._children + named

    @ft.cached_property
    def named_children_dict(self) -> tp.Dict[str, tp.Optional['Node']]:
        """Map from named child name to its value (or None)."""
        return {n: getattr(self, n) for n in self._named_children}

    @ft.cached_property
    def field_dict(self):
        fd = {f: getattr(self, f) for f in self._fields}
        assert all(not isinstance(v, Node) for v in fd.values())
        return fd

    @property
    def field_vals(self):
        return tuple(self.field_dict.values())

    # ---- Traversal ----

    def __iter__(self):
        return iter(self._children)

    def __repr__(self):
        from ..passes.analyses.pretty_printer import pretty
        return pretty(self)

    def __str__(self):
        return self.__repr__()

    # ---- Construction ----

    def replace(self, *new_children: 'Node', **kwargs: tp.Any) -> 'Node':
        new_fields = {**self.field_dict, **kwargs}
        if (new_fields == self.field_dict) and (new_children == self._children):
            return self
        new_node = type(self)(*new_children, **new_fields)
        for k, v in self._metadata.items():
            new_node._metadata[k] = v
        return new_node

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        global _op_cnt
        cls._opcode = _op_cnt
        _op_cnt +=1
        numc = getattr(cls, '_numc', None)
        if numc is None:
            return
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

class MetaVar(Node):
    _params = ('id',)
    _numc = 0
    def __init__(self, id: int):
        self.id = id
        super().__init__()

##############################
## Core-level IR Type nodes
##############################

class Type(Node):
    _named_children = ('ref', 'view', 'obl')

    def __init__(self, *children: Node, ref=None, view=None, obl=None):
        self._ref = ref
        self._view = view
        self._obl = obl
        super().__init__(*children)

    @property
    def T(self) -> tp.Self:
        return self

    @property
    def ref(self):
        return self._ref

    @property
    def view(self):
        return self._view

    @property
    def obl(self):
        return self._obl

    @property
    def rawT(self):
        from ..passes.analyses.type_check import stripT
        return stripT(self)

    def replace(self, *new_children, ref, view, obl, **field_kwargs):
        new_fields = {**self.field_dict, **field_kwargs}
        if (ref is self._ref and view is self._view and obl is self._obl and
                new_fields == self.field_dict and new_children == self._children):
            return self
        new_node = type(self)(*new_children, ref=ref, view=view, obl=obl, **new_fields)
        for k, v in self._metadata.items():
            new_node._metadata[k] = v
        return new_node

## Base types
class UnitT(Type):
    _numc = 0
    def __repr__(self):
        return "𝟙"

class BoolT(Type):
    _numc = 0
    def __repr__(self):
        return "𝔹"

    @classmethod
    def cast_as(cls, val: tp.Any):
        return bool(val)

class IntT(Type):
    _numc = 0
    def __repr__(self):
        return "ℤ"

    @classmethod
    def cast_as(cls, val: tp.Any):
        return int(val)


class EnumT(Type):
    _fields = ("name", "labels")
    _numc = 0
    def __init__(self, name: str, labels: tp.Tuple[str], ref=None, view=None, obl=None):
        self.name = name
        self.labels = labels
        super().__init__(ref=ref, view=view, obl=obl)

    def __repr__(self):
        return f"Enum<{self.name}>"

    def __len__(self):
        return len(self.labels)

class TupleT(Type):
    _numc = -1
    def __init__(self, *ts: Type, ref=None, view=None, obl=None):
        if not all(isinstance(t, Type) for t in ts):
            raise ValueError(f"TupleT children must be Types, got {ts}")
        super().__init__(*ts, ref=ref, view=view, obl=obl)

    @property
    def elemTs(self):
        return tuple(self[i] for i in range(len(self)))

    def __getitem__(self, idx: int):
        if idx >= len(self):
            raise IndexError(f"TupleT index {idx} out of bounds for tuple of length {len(self._children)}")
        return self._children[idx]

    def __len__(self):
        return len(self._children)

class SumT(Type):
    _numc = -1
    def __init__(self, *ts: Type, ref=None, view=None, obl=None):
        super().__init__(*ts, ref=ref, view=view, obl=obl)

    @property
    def elemTs(self):
        return tuple(self[i] for i in range(len(self)))

    def __getitem__(self, idx: int):
        if idx >= len(self):
            raise IndexError(f"SumT index {idx} out of bounds for sum of length {len(self)}")
        return self._children[idx]

    def __len__(self):
        return len(self._children)


class DomT(Type):
    _numc = 1
    def __init__(self, carT: Type, ref=None, view=None, obl=None):
        super().__init__(carT, ref=ref, view=view, obl=obl)

    @property
    def carT(self) -> Type:
        return self._children[0]


class _PiT(Type):
    @property
    def resT(self) -> Type:
        raise NotImplementedError()

    @property
    def argT(self) -> Type:
        raise NotImplementedError()

class PiT(_PiT):
    _numc = 2
    def __init__(self, argT: Type, resT: Type, ref=None, view=None, obl=None):
        super().__init__(argT, resT, ref=ref, view=view, obl=obl)

    @property
    def resT(self) -> Type:
        return self._children[1]

    @property
    def argT(self) -> Type:
        return self._children[0]


class ViewT(Type):
    _numc = 0

class ApplyT(Type):
    _numc = 2
    def __init__(self, lamT: PiT, arg: Value, ref=None, view=None, obl=None):
        if not isinstance(lamT, (PiT, PiTHOAS)):
            raise ValueError(f"ApplyT must be a PiT, got {lamT}")
        super().__init__(lamT, arg, ref=ref, view=view, obl=obl)

    def __repr__(self):
        return f"AppT({self.piT}, {self.arg})"

    @property
    def arg(self) -> Value:
        return self._children[1]

##############################
## Core-level IR Value nodes (Used throughout entire compiler flow)
##############################

# Base class for Nodes that store their Type (not meant to be instantiated directly)
class Value(Node):
    _named_children = ('T', 'obl')

    def __init__(self, T: Type, *children: Node, obl=None):
        if not isinstance(T, Type):
            raise ValueError(f"{T} must be a Type")
        if obl is not None and not isinstance(obl, Value):
            raise ValueError(f"obl must be a Value or None, got {obl}")
        self._T = T
        self._obl = obl
        super().__init__(*children)

    @property
    def T(self) -> Type:
        return self._T

    @property
    def obl(self):
        return self._obl

    def replace(self, *new_children, T, obl, **field_kwargs):
        new_fields = {**self.field_dict, **field_kwargs}
        if (T is self._T and obl is self._obl and
                new_fields == self.field_dict and new_children == self._children):
            return self
        new_node = type(self)(T, *new_children, obl=obl, **new_fields)
        for k, v in self._metadata.items():
            new_node._metadata[k] = v
        return new_node

class VarRef(Value):
    _fields = ("sid",)
    _numc = 0
    def __init__(self, T: Type, sid: int, obl=None):
        self.sid = sid
        super().__init__(T, obl=obl)

class Choose(Value):
    _numc=1
    def __init__(self, T: Type, plam: Value, obl=None):
        super().__init__(T, plam, obl=obl)

class BoundVar(Value):
    _fields = ('idx',) # De Bruijn index
    _numc = 0
    def __init__(self, T: Type, idx: int, obl=None):
        self.idx = idx
        super().__init__(T, obl=obl)

class Unit(Value):
    _numc = 0
    def __init__(self, T: Type, obl=None):
        super().__init__(T, obl=obl)

# (lamda x:paramT body) -> (paramT -> type(body))
class _Lambda(Value):
    pass

class Lambda(_Lambda):
    _numc = 1
    def __init__(self, T: Type, body: Value, obl=None):
        assert isinstance(T, PiT)
        super().__init__(T, body, obl=obl)

### Int/Bool

# Literal value for any base type
class Lit(Value):
    _fields = ("val",)
    _numc = 0
    def __init__(self, T: Type, val: tp.Any, obl=None):
        self.val = val
        super().__init__(T, obl=obl)

class Eq(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value, b: Value, obl=None):
        super().__init__(T, a, b, obl=obl)

class Lt(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value, b: Value, obl=None):
        super().__init__(T, a, b, obl=obl)

class LtEq(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value, b: Value, obl=None):
        super().__init__(T, a, b, obl=obl)

class Ite(Value):
    _numc = 3
    def __init__(self, T: Type, pred: Value, t: Value, f: Value, obl=None):
        super().__init__(T, pred, t, f, obl=obl)

class Not(Value):
    _numc = 1
    def __init__(self, T: Type, a: Value, obl=None):
        super().__init__(T, a, obl=obl)

class Neg(Value):
    _numc = 1
    def __init__(self, T: Type, a: Value, obl=None):
        super().__init__(T, a, obl=obl)

class FloorDiv(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value, b: Value, obl=None):
        super().__init__(T, a, b, obl=obl)

class TrueDiv(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value, b: Value, obl=None):
        super().__init__(T, a, b, obl=obl)

class Mod(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value, b: Value, obl=None):
        super().__init__(T, a, b, obl=obl)

class Isqrt(Value):
    _numc = 1
    def __init__(self, T: Type, a: Value, obl=None):
        super().__init__(T, a, obl=obl)

class Conj(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value, obl=None):
        super().__init__(T, *args, obl=obl)

class Disj(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value, obl=None):
        super().__init__(T, *args, obl=obl)

# integer sum
class Sum(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value, obl=None):
        super().__init__(T, *args, obl=obl)

# integer product
class Prod(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value, obl=None):
        super().__init__(T, *args, obl=obl)

## Domains

# Dom(T)
class Universe(Value):
    _numc = 0
    def __init__(self, T: Type, obl=None):
        super().__init__(T, obl=obl)

# Dom(T)
class Empty(Value):
    _numc = 0
    def __init__(self, T: Type, obl=None):
        super().__init__(T, obl=obl)

# Domain with single element
class Singleton(Value):
    _numc = 1
    def __init__(self, T: Type, v: Value, obl=None):
        super().__init__(T, v, obl=obl)

# Unique element of singleton domain
class Unique(Value):
    _numc = 1
    def __init__(self, T: Type, dom: Value, obl=None):
        super().__init__(T, dom, obl=obl)

# Dom(T) with literal elements
class DomLit(Value):
    _fields = ('is_set',) # is_set => is proven to be a set (i.e., elems are unique). ~is_set means "I dont know"
    _numc = -1
    def __init__(self, T: Type, *elems: Value, is_set: bool=False, obl=None):
        if not all(isinstance(elem, Value) for elem in elems):
            raise ValueError("DomLit children must be Values")
        self.is_set = False
        super().__init__(T, *elems, obl=obl)

# Int -> Dom[Int]
class Fin(Value):
    _numc = 1
    def __init__(self, T: Type, N: Value, obl=None):
        super().__init__(T, N, obl=obl)

# Get the size of a domain
# Dom(A) -> Int
class Card(Value):
    _numc = 1
    def __init__(self, T: Type, domain: Value, obl=None):
        super().__init__(T, domain, obl=obl)

# Dom(A) -> A -> Bool
class IsMember(Value):
    _numc = 2
    def __init__(self, T: Type, domain: Value, val: Value, obl=None):
        super().__init__(T, domain, val, obl=obl)

## Cartesian Products

# (Dom[A], Dom[B],...) -> Dom(AxBx...)
class CartProd(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value, obl=None):
        super().__init__(T, *doms, obl=obl)

# Dom(AxB,...) -> 0 -> A | 1 -> B | ...
class DomProj(Value):
    _fields = ('idx',)
    _numc = 1
    def __init__(self, T: Type, dom: Value, idx: int, obl=None):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, dom, obl=obl)

# subset + equal
class Subset(Value):
    _numc = 2
    def __init__(self, T: Type, domA: Value, domB: Value, obl=None):
        super().__init__(T, domA, domB, obl=obl)

# subset but not equal
class ProperSubset(Value):
    _numc = 2
    def __init__(self, T: Type, domA: Value, domB: Value, obl=None):
        super().__init__(T, domA, domB, obl=obl)

class Union(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value, obl=None):
        super().__init__(T, *doms, obl=obl)

class Intersection(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value, obl=None):
        super().__init__(T, *doms, obl=obl)

class TupleLit(Value):
    _numc = -1
    def __init__(self, T: Type, *vals: Value, obl=None):
        super().__init__(T, *vals, obl=obl)

    def __len__(self):
        return len(self.T)

class Proj(Value):
    _fields = ('idx',)
    _numc = 1
    def __init__(self, T: Type, tup: Value, idx: int, obl=None):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, tup, obl=obl)

class DisjUnion(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value, obl=None):
        super().__init__(T, *doms, obl=obl)

class DomInj(Value):
    _fields = ('idx',)
    _numc = 1
    def __init__(self, T: Type, dom: Value, idx: int, obl=None):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, dom, obl=obl)

# Injection for disjoint unions
class Inj(Value):
    _fields = ("idx", )
    _numc = 1
    def __init__(self, T: Type, val: Value, idx: int, obl=None):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, val, obl=obl)

# Literal for sum types
class SumLit(Value):
    _numc = -1
    def __init__(self, T: Type, tag: Value, *elems: Value, obl=None):
        if not isinstance(tag, Value):
            raise ValueError("SumLit tag must be a Value")
        if not all(isinstance(elem, Value) for elem in elems):
            raise ValueError("SumLit children must be Values")
        super().__init__(T, tag, *elems, obl=obl)

# (A|B|...) -> (A->T, B->T,...) -> T
class Match(Value):
    _numc = -1
    def __init__(self, T: Type, scrut: Value, *branches: Value, obl=None):
        super().__init__(T, scrut, *branches, obl=obl)

# Func(Dom(A) -> Bool) -> Dom(A)
class Restrict(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

# Func(Dom(A) -> Bool) -> Bool
class Forall(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

# Func(Dom(A) -> Bool) -> Bool
class Exists(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

#Compose
# (B -> C) -> (A -> B) -> (A -> C)
class Compose(Value):
    _numc=-1
    def __init__(self, T: Type, *lams: Value, obl=None):
        super().__init__(T, *lams, obl=obl)

@dataclass(eq=True, frozen=True)
class _FuncLitLayout:
    def index(self, val) -> tp.Optional[bool]:
        raise NotImplementedError()
    ...

class _SparseLayout(_FuncLitLayout):
    ...

@dataclass(eq=True, frozen=True)
class _DenseLayout(_FuncLitLayout):
    val_map: tp.Mapping[tp.Any, int]

    # probably unsafe to use val._key.
    def index(self, val: Node):
        return self.val_map.get(val._key, None)

    def __repr__(self):
        return f"Dense({len(self.val_map)})"

    def __hash__(self):
        return hash(frozenset(self.val_map))

    def __eq__(self, other):
        return isinstance(other, _DenseLayout) and self.val_map==other.val_map

    def __lt__(self, other):
        return len(self.val_map) < len(other.val_map)

class FuncLit(Value):
    _fields= ('layout',)
    _numc = -1
    def __init__(self, T: Type, dom: Value, *elems: Value, layout: _FuncLitLayout, obl=None):
        assert isinstance(layout, _FuncLitLayout)
        self.layout = layout
        super().__init__(T, dom, *elems, obl=obl)

    @property
    def elems(self):
        return self._children[1:]

class Image(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

## Func(Dom(A)->B) -> A -> B
#class ApplyFunc(Value):
#    _numc = 2
#    def __init__(self, T: Type, func: Value, arg: Value):
#        super().__init__(T, func, arg)

class Apply(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value, arg: Value, obl=None):
        super().__init__(T, func, arg, obl=obl)

# only used on Seq Funcs TODO maybe should have scan as the fundimental IR node
# OrdDom[A] -> ((A,B) -> B) -> B -> B
class Fold(Value):
    _numc = 3
    def __init__(self, T: Type, func: Value, lam: Value, init: Value, obl=None):
        super().__init__(T, func, lam, init, obl=obl)


##############################
## Surface-level IR nodes (Used for analyis, but can be collapes)
##############################

# Special Node for 'spec'
class Spec(Node):
    _numc = 2
    def __init__(self, cons: Value, obls: Value):
        super().__init__(cons, obls)

    @property
    def cons(self):
        return self._children[0]

    @property
    def obls(self):
        return self._children[1]

class Implies(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value, b: Value, obl=None):
        super().__init__(T, a, b, obl=obl)

class Abs(Value):
    _numc = 1
    def __init__(self, T: Type, a: Value, obl=None):
        super().__init__(T, a, obl=obl)

# Common Fold Values
class SumReduce(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

# multiply all the elements of a sequence
class ProdReduce(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

class AllDistinct(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

class AllSame(Value):
    _numc = 1
    def __init__(self, T: Type, func: Value, obl=None):
        super().__init__(T, func, obl=obl)

# ND nodes
class Slice(Value):
    _numc = 4
    def __init__(self, T: Type, dom: Value, lo: Value, hi: Value, step: Value, obl=None):
        super().__init__(T, dom, lo, hi, step, obl=obl)

class ElemAt(Value):
    _numc = 2
    def __init__(self, T: Type, dom: Value, idx: Value, obl=None):
        super().__init__(T, dom, idx, obl=obl)

class Range(Value):
    _numc = 3
    def __init__(self, T: Type, lo: Value, hi: Value, step: Value, obl=None):
        super().__init__(T, lo, hi, step, obl=obl)

class Enumerate(Value):
    _numc = 1
    def __init__(self, T: Type, dom: Value, obl=None):
        super().__init__(T, dom, obl=obl)

##############################
## View IR nodes
##############################

#class IdxViewT(_ViewT):
#    _numc=2
#    def __init__(self, A: Type, *bdoms: Value):
#        super().__init__(A, *bdoms)
#
#    @property
#    def A(self):
#        return self._children[0]
#
#    @property
#    def bdoms(self):
#        return self._children[1:]

class View(Value): pass


#class SqueezableDomain(DomainCapability):
#    _numc=1
#    def __init__(self, T: Type):
#        super().__init__(T)
#
#class NDDomain(DomainCapability):
#    _numc = -1
#    def __init__(self, T: Type, *factors: Value):
#        super().__init__(T, *factors)
#
#    @property
#    def factors(self) -> tp.Tuple[Type]:
#        return tuple(self._children[1:])


##############################
## Constructor-level IR nodes (Used for construction but immediatley gets transformed for spec)
##############################

# gets tranformed to a de-bruijn BoundVar
class BoundVarHOAS(Value):
    _fields = ('closed', 'name')
    _numc = 0
    _cnt = 0
    def __init__(self, T: Type, closed: bool, name: tp.Optional[str]=None, obl=None):
        if name is None:
            name = f"b{self._cnt}"
            BoundVarHOAS._cnt +=1
        self.name = f"{name}"
        self.closed = closed
        super().__init__(T, obl=obl)

class PiTHOAS(_PiT):
    _fields = ('bv_name',)
    _numc = 2
    def __init__(self, argT: Value, resT: Type, bv_name: str, ref=None, view=None, obl=None):
        self.bv_name = bv_name
        super().__init__(argT, resT, ref=ref, view=view, obl=obl)

    @property
    def argT(self):
        return self._children[0]

    @property
    def resT(self) -> Type:
        return self._children[1]

class LambdaHOAS(_Lambda):
    _fields = ('bv_name',)
    _numc = 1
    def __init__(self, T: Type, body: Value, bv_name: str, obl=None):
        assert isinstance(T, PiTHOAS)
        self.bv_name = bv_name
        super().__init__(T, body, obl=obl)

    @property
    def body(self):
        return self._children[0]

class VarHOAS(Value):
    _fields = ('name', 'kind', 'metadata')
    _numc = 0
    def __init__(self, T: Type, name: str, kind: str, metadata: tp.Dict[str, tp.Any], obl=None):
        self.name = name
        self.kind = kind
        self.metadata = metadata
        super().__init__(T, obl=obl)

    def __repr__(self):
        return f"VarHOAS[{self.name}]"

# Mapping from Nodes to a priority integer. Used for canonicalization among commutative operations
# Commutative ops: Prod, Sum, Conj, Disj, Intersect, Union, DomLit,
NODE_PRIORITY: tp.Dict[tp.Type[Value], int] = {
    # Types
    UnitT: 0,
    BoolT: 0,
    IntT: 0,
    EnumT: 0,
    TupleT: 0,
    SumT: 0,
    DomT: 0,
    PiTHOAS: 0,
    PiT: 0,
    ApplyT: 0,
    ViewT: 0,

    # Spec
    Spec: 0,
    # UnitT
    Unit: 10,

    # Bool/Int/Enum
    Lit: 20,

    # Any Type
    VarRef: 30,
    VarHOAS: 31,
    Choose: 33,
    BoundVar: 40,
    BoundVarHOAS: 41,

    Apply: 801,
    ElemAt: 802,
    Proj: 803,
    Ite: 810,
    Match: 811,
    Fold: 812,
    Unique: 813,

    # Bool
    Not: 100,
    Eq: 101,
    Lt: 102,
    LtEq: 103,
    Implies: 104,
    IsMember: 110,
    Subset: 111,
    ProperSubset: 112,
    Conj: 120,
    Disj: 121,
    AllDistinct: 130,
    AllSame: 131,
    Forall: 140,
    Exists: 141,

    # Int
    Neg: 200,
    Abs: 201,
    Sum: 210,
    Prod: 211,
    FloorDiv: 220,
    TrueDiv: 221,
    Mod: 222,
    Isqrt: 223,
    Card: 230,
    SumReduce: 240,
    ProdReduce: 241,

    # Domains
    Empty: 300,
    Universe: 301,
    Singleton: 302,
    #IndexView: 303,
    #SqueezableDomain: 304,
    #NDDomain: 305,
    Fin: 310,
    Range: 311,
    DomLit: 320,
    Restrict: 330,
    Slice: 331,
    Image: 332,
    DomProj: 333,
    DomInj: 334,
    CartProd: 340,
    DisjUnion: 341,
    Intersection: 350,
    Union: 351,

    # Tuples
    # Sums
    # Funcs
    TupleLit: 400,
    SumLit: 410,
    FuncLit: 420,
    Inj: 430,
    Enumerate: 450,
    Lambda: 460,
    LambdaHOAS: 461,

    Compose: 470,
}
