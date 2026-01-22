from __future__ import annotations
import typing as tp
# Unified Types and IR
from dataclasses import dataclass
import functools as ft

def calc_hash(opcode: int, fields: tp.Tuple[tp.Any], child_hashes: tp.Tuple[int]):
    return hash((opcode, fields, child_hashes))
# Base class for IR
_op_cnt = 0
class Node:
    _fields: tp.Tuple[str, ...] = ()
    def __init__(self, *children: 'Node'):
        for child in children:
            if not isinstance(child, Node):
                raise TypeError(f"Expected Node, got {child}: {type(child)}")
        if self._numc >= 0 and len(children) != self._numc:
            raise TypeError(f"Expected {self._numc} children, got {len(children)}")
        self._children: tp.Tuple[Node, ...] = children
        self._hash = calc_hash(self._opcode, tuple(self.field_dict.values()), tuple(c._hash for c in self._children))

    @property
    def num_children(self):
        return len(self._children)

    #def _gen_key(self):
    #    child_keys = tuple(c._key for c in self._children)
    #    assert None not in child_keys
    #    fields = tuple(getattr(self, field, None) for field in self._fields)
    #    priority = NODE_PRIORITY[(type(self))]
    #    key = (priority, self.__class__.__name__, fields, child_keys)
    #    return key

    def __iter__(self):
        return iter(self._children)
    
    def __repr__(self):
        # Pretty printing while debugging
        from ..passes.analyses.pretty_printer import pretty
        return pretty(self)
    
    def __str__(self):
        return self.__repr__()

    @ft.cached_property
    def field_dict(self):
        fd = {f: getattr(self, f) for f in self._fields}
        assert all(not isinstance(v, Node) for v in fd.values())
        return fd

    @property
    def field_vals(self):
        return tuple(self.field_dict.values())

    def replace(self, *new_children: 'Node', **kwargs: tp.Any) -> 'Node':
        new_fields = {**self.field_dict, **kwargs}
        if (new_fields == self.field_dict) and (new_children == self._children):
            return self
        #from ..passes.analyses.type_check import type_check, stripT
        #if isinstance(self, Value):
        #    if stripT(self.T) != stripT(new_children[0]):
        #        raise ValueError()
        new_node = type(self)(*new_children, **new_fields)
        #if isinstance(self, DomT):
        #    if self != new_node:
        #        raise ValueError()
        #type_check(new_node)
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

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, Node):
            return False
        if self._hash != other._hash:
            return False
        return self._opcode == other._opcode and self.field_dict == other.field_dict and self._children==other._children

    def __lt__(self, other: Node):
        if self._opcode!=other._opcode:
            return NODE_PRIORITY[type(self)] < NODE_PRIORITY[type(other)]
        if self.field_vals != other.field_vals:
            return self.field_vals < other.field_vals
        return self._children < other._children


# Background info: Containers are represented a 'Func[Dom(A) -> B]'
# So a 'List[B]' would be Func(Fin(n) -> B).
# And a Set[B] would be Func(Dom(B) -> Bool)
# A Func[Dom(A) -> B] is typed as Arrow[carrier(A) -> B]

##############################
## Core-level IR Type nodes 
##############################

class Type(Node):
    @property
    def T(self) -> tp.Self:
        return self
    
    @property
    def rawT(self):
        from ..passes.analyses.type_check import stripT
        return stripT(self)

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
    def __init__(self, name: str, labels: tp.Tuple[str]):
        self.name = name
        self.labels = labels
        super().__init__()

    def __repr__(self):
        return f"Enum<{self.name}>"

    def __len__(self):
        return len(self.labels)

class TupleT(Type):
    _numc = -1
    def __init__(self, *ts: Type):
        if not all(isinstance(t, Type) for t in ts):
            raise ValueError(f"TupleT children must be Types, got {ts}")
        super().__init__(*ts)

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
    def __init__(self, *ts: Type):
        super().__init__(*ts)
    
    @property
    def elemTs(self):
        return tuple(self[i] for i in range(len(self)))

    def __getitem__(self, idx: int):
        if idx >= len(self):
            raise IndexError(f"SumT index {idx} out of bounds for sum of length {len(self)}")
        return self._children[idx]

    def __len__(self):
        return len(self._children)

    #def __repr__(self):
    #    return "⊎".join(str(child) for child in self._children)

class _DomT(Type):
    ord = False
    is_singleton=False

    @property
    def carT(self) -> Type:
        raise NotImplementedError()

class DomT(_DomT):
    _fields = ('ord', 'is_singleton')
    _numc = 1
    def __init__(self, carT: Type, ord: bool, is_singleton: bool=False):
        self.ord = ord
        self.is_singleton = is_singleton
        super().__init__(carT)

    @property
    def carT(self) -> Type:
        return self._children[0]

    #def __repr__(self):
    #    return f"DomT[{self.carT}]"

class NDDomT(_DomT):
    _fields=('axes',)
    _numc=-1
    def __init__(self, *factors: Type, axes: tp.Tuple[int]):
        assert all(isinstance(f, DomT) for f in factors)
        self.axes = axes
        super().__init__(*factors)
    
    @property
    def carT(self) -> Type:
        return TupleT(*(f.carT for f in self._children))
    
    @property
    def factors(self) -> tp.Tuple[_DomT]:
        return self._children

    @property
    def ord(self) -> bool:
        return all(f.ord for f in self.factors)

class _LambdaT(Type):
    @property
    def argT(self) -> Type:
        raise NotImplementedError()

    @property
    def resT(self) -> Type:
        raise NotImplementedError()


class PiT(_LambdaT):
    _numc = 2
    def __init__(self, argT: Type, resT: Type):
        super().__init__(argT, resT)

    @property
    def resT(self) -> Type:
        return self._children[1]

    @property
    def argT(self) -> Type:
        return self._children[0]

class ArrowT(_LambdaT):
    _numc = 2
    def __init__(self, argT: Type, resT: Type):
        super().__init__(argT, resT)

    @property
    def argT(self) -> Type:
        return self._children[0]

    @property
    def resT(self) -> Type:
        return self._children[1]


class FuncT(Type):
    _numc = 2
    def __init__(self, dom: Value, lamT: Type):
        assert isinstance(lamT, (PiT, PiTHOAS, ArrowT))
        super().__init__(dom, lamT)

    @property
    def dom(self) -> Value:
        return self._children[0]
    
    @property
    def lamT(self) -> PiT:
        return self._children[1]

    #def __repr__(self):
    #    return f"Func[{self.dom.T}, {self.lamT}]"

    def eq(self, other):
        return isinstance(other, FuncT) and self.dom.eq(other.dom) and self.lamT.eq(other.lamT)

class RefT(Type):
    _numc = 2
    def __init__(self, T: Type, dom: Value):
        #assert not isinstance(T, RefT)
        super().__init__(T, dom)

    @property
    def T(self) -> Type:
        return self._children[0]

    @property
    def dom(self) -> Value:
        return self._children[1]

    def cast_as(self, val: tp.Any):
        return self.T.cast_as(val)


def _is_value(v: Node) -> bool:
    return isinstance(v, (Value, BoundVar, VarRef))

class ApplyT(Type):
    _numc = 2
    def __init__(self, lamT: PiT, arg: Value):
        assert _is_value(arg)
        if not isinstance(lamT, (PiT, PiTHOAS)):
            raise ValueError(f"ApplyT must be a PiT, got {lamT}")
        super().__init__(lamT, arg)

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
    def __init__(self, T: Type, *children: Node):
        if not isinstance(T, Type):
            raise ValueError(f"{T} must be a Type")
        if any(isinstance(c, Type) for c in children):
            raise ValueError(f"{children} must not have Type children, got {children}")
        super().__init__(T, *children)
    
    @property
    def T(self) -> Type:
        return self._children[0]

class VarRef(Value):
    _fields = ("sid",)
    _numc = 1
    def __init__(self, T: Type, sid: int):
        self.sid = sid
        super().__init__(T)

class BoundVar(Value):
    _fields = ('idx',) # De Bruijn index
    _numc = 1
    def __init__(self, T: Type, idx: int):
        self.idx = idx
        super().__init__(T)


class Unit(Value):
    _numc = 1
    def __init__(self, T: Type):
        super().__init__(T)

# (lamda x:paramT body) -> (paramT -> type(body))
class Lambda(Value):
    _numc = 2
    def __init__(self, T: Type, body: Value):
        assert isinstance(T, PiT)
        super().__init__(T, body)

### Int/Bool 

# Literal value for any base type
class Lit(Value):
    _fields = ("val",)
    _numc = 1
    def __init__(self, T: Type, val: tp.Any):
        if val == -9:
            raise ValueError()
        self.val = val
        super().__init__(T)

class Eq(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Lt(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class LtEq(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Ite(Value):
    _numc = 4
    def __init__(self, T: Type, pred: Value, t: Value, f: Value):
        super().__init__(T, pred, t, f)

class Not(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value):
        super().__init__(T, a)

class Neg(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value):
        super().__init__(T, a)

class Div(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Mod(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Conj(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value):
        super().__init__(T, *args)

class Disj(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value):
        super().__init__(T, *args)

# integer sum
class Sum(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value):
        super().__init__(T, *args)

# integer product
class Prod(Value):
    _numc = -1
    def __init__(self, T: Type, *args: Value):
        super().__init__(T, *args)

## Domains

# Dom(T)
class Universe(Value):
    _numc = 1
    def __init__(self, T: Type):
        super().__init__(T)

# Dom(T)
class Empty(Value):
    _numc = 1
    def __init__(self, T: Type):
        super().__init__(T)

# Domain with single element
class Singleton(Value):
    _numc = 2
    def __init__(self, T: Type, v: Value):
        super().__init__(T, v)

# Unique element of singleton domain
class Unique(Value):
    _numc = 2
    def __init__(self, T: Type, dom: Value):
        super().__init__(T, dom)

# Dom(T) with literal elements
class DomLit(Value):
    _fields = ('is_set',) # is_set => is proven to be a set (i.e., elems are unique). ~is_set means "I dont know"
    _numc = -1
    def __init__(self, T: Type, *elems: Value, is_set: bool=False):
        if not all(isinstance(elem, Value) for elem in elems):
            raise ValueError("DomLit children must be Values")
        self.is_set = False
        super().__init__(T, *elems)

# Int -> Dom[Int]
class Fin(Value):
    _numc = 2
    def __init__(self, T: Type, N: Value):
        super().__init__(T, N)

# Get the size of a domain
# Dom(A) -> Int
class Card(Value):
    _numc = 2
    def __init__(self, T: Type, domain: Value):
        super().__init__(T, domain)

# Dom(A) -> A -> Bool 
class IsMember(Value):
    _numc = 3
    def __init__(self, T: Type, domain: Value, val: Value):
        super().__init__(T, domain, val)

## Cartesian Products

# (Dom[A], Dom[B],...) -> Dom(AxBx...)
class CartProd(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value):
        super().__init__(T, *doms)

# Dom(AxB,...) -> 0 -> A | 1 -> B | ...
class DomProj(Value):
    _fields = ('idx',)
    _numc = 2
    def __init__(self, T: Type, dom: Value, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, dom)

# subset + equal
class Subset(Value):
    _numc = 3
    def __init__(self, T: Type, domA: Value, domB: Value):
        super().__init__(T, domA, domB)

# subset but not equal
class ProperSubset(Value):
    _numc = 3
    def __init__(self, T: Type, domA: Value, domB: Value):
        super().__init__(T, domA, domB)

class Union(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value):
        super().__init__(T, *doms)

class Intersection(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value):
        super().__init__(T, *doms)

class TupleLit(Value):
    _numc = -1
    def __init__(self, T: Type, *vals: Value):
        super().__init__(T, *vals)

class Proj(Value):
    _fields = ('idx',)
    _numc = 2
    def __init__(self, T: Type, tup: Value, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, tup)

class DisjUnion(Value):
    _numc = -1
    def __init__(self, T: Type, *doms: Value):
        super().__init__(T, *doms)

class DomInj(Value):
    _fields = ('idx')
    _numc = 2
    def __init__(self, T: Type, dom: Value, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, dom)

# Injection for disjoint unions
class Inj(Value):
    _fields = ("idx", )
    _numc = 2
    def __init__(self, T: Type, val: Value, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, val)

# Literal for sum types
class SumLit(Value):
    _numc = -1
    def __init__(self, T: Type, tag: Value, *elems: Value):
        if not isinstance(tag, Value):
            raise ValueError("SumLit tag must be a Value")
        if not all(isinstance(elem, Value) for elem in elems):
            raise ValueError("SumLit children must be Values")
        super().__init__(T, tag, *elems)

# (A|B|...) -> (A->T, B->T,...) -> T
class Match(Value):
    _numc = -1
    def __init__(self, T: Type, scrut: Value, *branches: Value):
        super().__init__(T, scrut, *branches)

# Func(Dom(A) -> Bool) -> Dom(A)
class Restrict(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

# Func(Dom(A) -> Bool) -> Bool
class Forall(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

# Func(Dom(A) -> Bool) -> Bool
class Exists(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

# Dom(A) -> (A->B) -> Func(Dom(A)->B)
class Map(Value):
    _numc=3
    def __init__(self, T: Type, dom: Value, lam: Value):
        super().__init__(T, dom, lam)

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
    def __init__(self, T: Type, dom: Value, *elems: Value, layout: _FuncLitLayout):
        assert isinstance(layout, _FuncLitLayout)
        self.layout = layout
        super().__init__(T, dom, *elems)

    @property
    def elems(self):
        return self._children[2:]

class Image(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

# Image of a func known to be injective
#class InjImage(Value):
#    _numc = 2
#    def __init__(self, T: Type, func: Value):
#        super().__init__(T, func)

# Func(Dom(A)->B) -> A -> B
class ApplyFunc(Value):
    _numc = 3
    def __init__(self, T: Type, func: Value, arg: Value):
        super().__init__(T, func, arg)

class Apply(Value):
    _numc = 3
    def __init__(self, T: Type, lam: Value, arg: Value):
        super().__init__(T, lam, arg)

# F: B -> C
# G: A - B
# Compose == F o G
class Compose(Value):
    _numc = 3
    def __init__(self, T: Type, g: Value, f: Value):
        super().__init__(T, g, f)


# only used on Seq Funcs TODO maybe should have scan as the fundimental IR node
# Seq[A] -> ((A,B) -> B) -> B -> B
class Fold(Value):
    _numc = 4
    def __init__(self, T: Type, func: Value, lam: Value, init: Value):
        super().__init__(T, func, lam, init)


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
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Abs(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value):
        super().__init__(T, a)

# Common Fold Values
class SumReduce(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

# multiply all the elements of a sequence
class ProdReduce(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

class AllDistinct(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

class AllSame(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

# ND nodes
class Slice(Value):
    _numc = 5
    def __init__(self, T: Type, dom: Value, lo: Value, hi: Value, step: Value):
        super().__init__(T, dom, lo, hi, step)

class ElemAt(Value):
    _numc = 3
    def __init__(self, T: Type, dom: Value, idx: Value):
        super().__init__(T, dom, idx)

class Range(Value):
    _numc = 4
    def __init__(self, T: Type, lo: Value, hi: Value, step: Value):
        super().__init__(T, lo, hi, step)

class Enumerate(Value):
    _numc = 2
    def __init__(self, T: Type, dom: Value):
        super().__init__(T, dom)


##############################
## Constructor-level IR nodes (Used for construction but immediatley gets transformed for spec)
##############################

# gets tranformed to a de-bruijn BoundVar
class BoundVarHOAS(Value):
    _fields = ('closed', 'name')
    _numc = 1
    _cnt = 0
    def __init__(self, T: Type, closed: bool, name: tp.Optional[str]=None):
        if name is None:
            name = f"b{self._cnt}"
            BoundVarHOAS._cnt +=1
        self.name = f"{name}"
        self.closed = closed
        super().__init__(T)

    @property
    def T(self) -> RefT:
        return self._children[0]

class PiTHOAS(_LambdaT):
    _fields = ('bv_name', 'inj',)
    _numc = 2
    def __init__(self, argT: Value, resT: Type, bv_name: str, inj=False):
        self.bv_name = bv_name
        self.inj = inj
        super().__init__(argT, resT)

    @property
    def argT(self):
        return self._children[0]

    @property
    def resT(self) -> Type:
        return self._children[1]


class LambdaHOAS(Value):
    _fields = ('bv_name', 'inj',) #True -> Known to be injective
    _numc = 2
    def __init__(self, T: Type, body: Value, bv_name: str, inj: bool):
        self.bv_name = bv_name
        self.inj=inj
        super().__init__(T, body)

class VarHOAS(Value):
    _fields = ('name', 'metadata')
    _numc = 1
    def __init__(self, T: Type, name: str, metadata: tp.Dict[str, tp.Any]):
        self.name = name
        self.metadata = metadata
        super().__init__(T)

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
    NDDomT: 0,
    FuncT: 0,
    ArrowT: 0,
    PiTHOAS: 0,
    PiT: 0,
    ApplyT: 0,
    RefT: 0,
    
    # Spec
    Spec: 0,
    # UnitT
    Unit: 10,
    
    # Bool/Int/Enum
    Lit: 20,
    
    # Any Type
    VarRef: 30,
    VarHOAS: 31,
    BoundVar: 40,
    BoundVarHOAS: 41,
    
    ApplyFunc: 800,
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
    Div: 220,
    Mod: 221,
    Card: 230,
    SumReduce: 240,
    ProdReduce: 241,

    # Domains
    Empty: 300,
    Universe: 301,
    Singleton: 302,
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
    Map: 440,
    Enumerate: 450, 

    # Lambdas
    Lambda: 500,
    LambdaHOAS: 501,

}

