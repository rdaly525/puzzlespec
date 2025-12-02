from __future__ import annotations
import typing as tp
# Unified Types and IR
from dataclasses import dataclass
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

    #@property
    #def is_lit(self):
    #    return isinstance(self, Lit)

    @property
    def num_children(self):
        return len(self._children)

    def _gen_key(self):
        child_keys = tuple(c._key for c in self._children)
        assert None not in child_keys
        fields = tuple(getattr(self, field, None) for field in self._fields)
        #assert None not in fields
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
        #if (c1._key==c2._key for c1, c2 in zip(new_children,self._children)) and new_fields == self.field_dict:
        if (new_children == self._children) and new_fields == self.field_dict:
            return self
        return type(self)(*new_children, **new_fields)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
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

    @classmethod
    def equals(cls, a: Node, b: Node):
        return a._key == b._key
    
    def eq(self, other):
        return isinstance(other, Node) and self._key==other._key




# Background info: Containers are represented a 'Func[Dom(A) -> B]'
# So a 'List[B]' would be Func(Fin(n) -> B).
# And a Set[B] would be Func(Dom(B) -> Bool)
# A Func[Dom(A) -> B] is typed as Arrow[carrier(A) -> B]

##############################
## Core-level IR Type nodes 
##############################

class Type(Node):
    ...   

## Base types
class UnitT(Type):
    _numc = 0
    def __repr__(self):
        return "𝟙"

    def eq(self, other):
        return isinstance(other, UnitT)

class BoolT(Type):
    _numc = 0
    def __repr__(self):
        return "𝔹"

    @classmethod
    def cast_as(cls, val: tp.Any):
        return bool(val)

    def eq(self, other):
        return isinstance(other, BoolT)


class IntT(Type):
    _numc = 0
    def __repr__(self):
        return "ℤ"

    @classmethod
    def cast_as(cls, val: tp.Any):
        return int(val)

    def eq(self, other):
        return isinstance(other, IntT)


class EnumT(Type):
    _fields = ("name", "labels")
    _numc = 0
    def __init__(self, name: str, labels: tp.Tuple[str]):
        self.name = name
        self.labels = labels
        super().__init__()

    def __repr__(self):
        return f"Enum<{self.name}>"

    def eq(self, other):
        return isinstance(other, EnumT) and self.name==other.name and self.labels ==other.labels


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

    def __repr__(self):
        return "⨯".join(str(child) for child in self._children)

    def eq(self, other):
        return isinstance(other, TupleT) and len(self)==len(other) and all(self[i].eq(other[i]) for i in range(len(self)))

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

    def __repr__(self):
        return "⊎".join(str(child) for child in self._children)

    def eq(self, other):
        return isinstance(other, SumT) and len(self)==len(other) and all(self[i].eq(other[i]) for i in range(len(self)))


#class ArrowT(Type):
#    _numc=2
#    def __init__(self, argT: Type, resT: Type):
#        super().__init__(argT, resT)
#
#    @property
#    def argT(self):
#        return self._children[0]
#    
#    @property
#    def resT(self):
#        return self._children[1]
#
#    def __repr__(self):
#        return f"{self.argT} -> {self.resT}"
#    
#    def eq(self, other):
#        return isinstance(other, ArrowT) and self.argT.eq(other.argT) and self.resT.eq(other.resT)

class DomT(Type):
    _fields = ("fins", "ords", "axes")
    _numc = -1
    def __init__(self, *factors: Type, fins: tp.Tuple[bool], ords: tp.Tuple[bool], axes : tp.Tuple[int]):
        N = len(factors)
        assert isinstance(factors, tuple) and len(factors)>0 and all(isinstance(f, Type) for f in factors)
        assert isinstance(fins, tuple) and len(fins)==N and all(isinstance(f, bool) for f in fins)
        assert isinstance(ords, tuple) and len(ords)==N and all(isinstance(o, bool) for o in ords)
        assert isinstance(axes, tuple) and all(isinstance(a, int) and a<N for a in axes)
        self.fins = fins
        self.ords = ords
        self.axes=axes
        super().__init__(*factors)

    @classmethod
    def make(cls, carT: Type, fin: bool, ord: bool):
        factors = (carT,)
        fins = (fin,)
        ords = (ord,)
        axes = (0,)
        return DomT(*factors, fins=fins, ords=ords, axes=axes)

    @property
    def factors(self):
        return tuple(self._children)

    @property
    def carT(self):
        if len(self.factors)==1:
            return self.factors[0]
        else:
            return TupleT(*self.factors)

    @property
    def rank(self):
        return len(self.axes)
    
    @property
    def fin(self):
        return all(self.fins)

    @property
    def ord(self):
        return all(self.ords)

    def __repr__(self):
        rank = len(self.axes)
        #return f"Dom<{self.fins},{self.ords},{rank}>[{self.carT}]"
        return f"Dom[{self.carT}]"

    def eq(self, other):
        return isinstance(other, DomT) and self.carT.eq(other.carT) and self.fins==other.fins and self.ords==other.ords and self.axes==other.axes

class PiTHOAS(Type):
    _numc = 2
    def __init__(self, bound_var: Value, resT: Type):
        super().__init__(bound_var, resT)

    @property
    def resT(self) -> Type:
        return self._children[1]

    @property
    def argT(self) -> Type:
        return self._children[0].T

    def __repr__(self):
        return f"(\{self._children[0]}. {self.resT})"

class PiT(Type):
    _numc = 2
    def __init__(self, argT: Type, resT: Type):
        super().__init__(argT, resT)

    @property
    def resT(self) -> Type:
        return self._children[1]

    @property
    def argT(self) -> Type:
        return self._children[0]


class FuncT(Type):
    _numc = 2
    def __init__(self, dom: Value, piT: Type):
        assert isinstance(piT, (PiT, PiTHOAS))
        super().__init__(dom, piT)

    @property
    def dom(self) -> Value:
        return self._children[0]
    
    @property
    def piT(self) -> PiT:
        return self._children[1]

    def __repr__(self):
        return f"Func[{self.dom.T}, {self.piT}]"

    def eq(self, other):
        return isinstance(other, FuncT) and self.dom.eq(other.dom) and self.piT.eq(other.piT)


def _is_value(v: Node) -> bool:
    return isinstance(v, (Value, BoundVar, VarRef))

class ApplyT(Type):
    _numc = 2
    def __init__(self, piT: PiT, arg: Value):
        assert _is_value(arg)
        if not isinstance(piT, PiT):
            raise ValueError(f"ApplyT must be a PiT, got {piT}")
        super().__init__(piT, arg)

    def __repr__(self):
        return f"AppT({self.piT}, {self.arg})"

    @property
    def piT(self) -> PiT:
        return self._children[0]

    @property
    def arg(self) -> Value:
        return self._children[1]


##############################
## Core-level IR Value nodes (Used throughout entire compiler flow)
##############################

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

# Base class for Nodes that store their Type (not meant to be instantiated directly)
class Value(Node):
    def __init__(self, T: Type, *children: Node):
        if not isinstance(T, Type):
            raise ValueError(f"{T} must be a Type")
        if any(isinstance(c, Type) for c in children):
            raise ValueError(f"{children} must not have Type children, got {children}")
        super().__init__(T, *children)
    
    @property
    def T(self):
        return self._children[0]

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
        self.val = T.cast_as(val)
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

# Dom(T) with literal elements
class DomLit(Value):
    _numc = -1
    def __init__(self, T: Type, *elems: Value):
        if not all(isinstance(elem, Value) for elem in elems):
            raise ValueError("DomLit children must be Values")
        super().__init__(T, *elems)

# Int -> Dom[Int]
class Fin(Value):
    _numc = 2
    def __init__(self, T: Type, N: Value):
        super().__init__(T, N)

# Dom[EnumT] -> EnumT
class EnumLit(Value):
    _fields = ("label",)
    _numc = 1
    def __init__(self, enumT: EnumT, label: str):
        self.label = label
        super().__init__(enumT)

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

class TupleLit(Value):
    _numc = -1
    def __init__(self, T: Type, *vals: Value):
        if not all(isinstance(val, Value) for val in vals):
            raise ValueError("Bad constructor for TupleLit")
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
    def __init__(self, T: Type, dom: Value, fun: Value):
        super().__init__(T, dom, fun)

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

# Func(Dom(A)->B) -> A -> B
class ApplyFunc(Value):
    _numc = 3
    def __init__(self, T: Type, func: Value, arg: Value):
        super().__init__(T, func, arg)

class Apply(Value):
    _numc = 3
    def __init__(self, T: Type, lam: Value, arg: Value):
        super().__init__(T, lam, arg)

# only used on Seq Funcs TODO maybe should have scan as the fundimental IR node
# Seq[A] -> ((A,B) -> B) -> B -> B
class Fold(Value):
    _numc = 4
    def __init__(self, T: Type, func: Value, fun: Value, init: Value):
        super().__init__(T, func, fun, init)

# Slices a Sequential Domain
class Slice(Value):
    _numc = 4
    def __init__(self, T: Type, dom: Value, lo: Value, hi: Value):
        super().__init__(T, dom, lo, hi)

# Single Element of the domain
class RestrictEq(Value):
    _numc = 3
    def __init__(self, T: Type, dom: Value, v: Value):
        super().__init__(T, dom, v)

class ElemAt(Value):
    _numc = 3
    def __init__(self, T: Type, dom: Value, idx: Value):
        super().__init__(T, dom, idx)


##############################
## Surface-level IR nodes (Used for analyis, but can be collapes)
##############################

# Special Node for 'spec'
class Spec(Node):
    _fields = ('sids',)
    _numc = 3
    def __init__(self, cons: Value, obls: Value, Ts: TupleT, sids: tp.Tuple[int]):
        self.sids = sids
        assert len(sids) == len(Ts._children)
        super().__init__(cons, obls, Ts)

    @property
    def cons(self):
        return self._children[0]
    
    @property
    def obls(self):
        return self._children[1]
    
    @property
    def Ts(self):
        return self._children[2]

class And(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Implies(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Or(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Add(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Sub(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Mul(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class Abs(Value):
    _numc = 2
    def __init__(self, T: Type, a: Value):
        super().__init__(T, a)

class Gt(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

class GtEq(Value):
    _numc = 3
    def __init__(self, T: Type, a: Value, b: Value):
        super().__init__(T, a, b)

# Represents (lo..hi)
class Range(Value):
    _numc = 3
    def __init__(self, T: Type, lo: Value, hi: Value):
        super().__init__(T, lo, hi)

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

##############################
## Constructor-level IR nodes (Used for construction but immediatley gets transformed for spec)
##############################

# gets tranformed to a de-bruijn BoundVar
class BoundVarHOAS(Value):
    #_fields = ('_map_dom', '_is_map')
    _numc = 1
    def __init__(self, T: Type):#, _map_dom: Value, _is_map: bool=False):
        #self._map_dom = _map_dom
        #self._is_map = _is_map
        super().__init__(T)

    def __str__(self):
        return f"BV[{str(id(self))[-5:]}]"

class LambdaHOAS(Value):
    _numc = 3
    def __init__(self, T: Type, bound_var: Value, body: Value):
        super().__init__(T, bound_var, body)

class VarHOAS(Value):
    _fields = ('name', 'metadata')
    _numc = 1
    def __init__(self, T: Type, name: str, metadata: tp.Dict[str, tp.Any]):
        self.name = name
        super().__init__(T)

# Mapping from Value classes to a priority integer.
# This is probably way overengineered and there are probably better priorities
NODE_PRIORITY: tp.Dict[tp.Type[Value], int] = {
    Spec: -3,
    UnitT: -2,
    BoolT: -2,
    IntT: -2,
    EnumT: -2,
    TupleT: -2,
    SumT: -2,
    DomT: -2,
    FuncT: -2,
    PiTHOAS: -2,
    PiT: -2,
    ApplyT: -2,
    Unit: -1,
    Lit: 0,
    VarRef: 1,
    VarHOAS: 1,
    BoundVar: 2,
    BoundVarHOAS: 2,
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
    Abs: 5,
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
    Range: 9,
    EnumLit: 9,
    DomLit: 9,
    Card: 9,
    IsMember: 9,
    CartProd: 9,
    DomProj: 9,
    TupleLit: 9,
    Proj: 9,
    ElemAt: 9,
    DisjUnion: 9,
    DomInj: 9,
    Inj: 9,
    SumLit: 9,
    Match: 9,
    Restrict: 9,
    Map: 10,
    FuncLit: 10,
    Image: 10,
    ApplyFunc: 10,
    Apply: 10,
    RestrictEq: 10,
    Slice: 10,
    Lambda: 12,
    LambdaHOAS: 12,
    Fold: 13,
    SumReduce: 14,
    ProdReduce: 14,
    Forall: 14,
    Exists: 14,
    AllDistinct: 14,
    AllSame: 14,
}

