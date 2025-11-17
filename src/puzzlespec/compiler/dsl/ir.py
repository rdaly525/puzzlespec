from __future__ import annotations
import typing as tp
from abc import abstractmethod
# Unified Types and IR

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

class BoolT(Type):
    _numc = 0
    def __repr__(self):
        return "𝔹"

class IntT(Type):
    _numc = 0
    def __repr__(self):
        return "ℤ"

class EnumT(Type):
    _fields = ("name", "labels")
    _numc = 0
    def __init__(self, name: str, labels: tp.Tuple[str]):
        self.name = name
        self.labels = labels
        super().__init__()

class TupleT(Type):
    _numc = -1
    def __init__(self, *ts: Type):
        super().__init__(*ts)

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

    def __getitem__(self, idx: int):
        if idx >= len(self._children):
            raise IndexError(f"SumT index {idx} out of bounds for sum of length {len(self._children)}")
        return self._children[idx]

class ArrowT(Type):
    def __init__(self, argT: Type, resT: Type):
        super().__init__(argT, resT)

    @property
    def argT(self):
        return self._children[0]
    
    @property
    def resT(self):
        return self._children[1]

class DomT(Type):
    _fields = ("fin", "ord")
    _numc = 2
    def __init__(self, carT: Type, prod_doms: tp.Tuple[Value]=None, fin: bool=None, ord: bool=None):
        self.fin = fin
        self.ord = ord
        if prod_doms is None:
            doms = ()
        elif isinstance(prod_doms, tp.Tuple):
            doms = prod_doms
        assert all(isinstance(dom, Value) for dom in doms)
        prod_doms = TupleLit(*doms)
        super().__init__(carT, prod_doms)

    @property
    def carT(self):
        return self._children[0]

    @property
    def prod_doms(self):
        return self._children[1]

    def __len__(self):
        if len(self.prod_doms.T)==0:
            return 1
        else:
            return len(self.prod_doms.T)

class FuncT(Type):
    _numc = 2
    def __init__(self, dom: Value, retT: Type):
        super().__init__(dom, retT)

    @property
    def dom(self):
        return self._children[0]
    
    @property
    def retT(self):
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
    _numc = 1
    def __init__(self, idx: int):
        self.idx = idx
        super().__init__()

# Base class for Nodes that store their Type (not meant to be instantiated directly)
class Value(Node):
    def __init__(self, T: Type, *children: Node):
        super().__init__(T, *children)
    
    @property
    def T(self):
        return self._children[0]

class Unit(Value):
    _numc = 1
    def __init__(self):
        super().__init__(UnitT())

# (lamda x:paramT body) -> (paramT -> type(body))
class Lambda(Value):
    _numc = 2
    def __init__(self, T: Type, body: Value):
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
    def __init__(self, a: Value, b: Value):
        super().__init__(BoolT(), a, b)

class Lt(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(BoolT(), a, b)

class LtEq(Value):
    _numc = 2
    def __init__(self, a: Value, b: Value):
        super().__init__(BoolT(), a, b)

class Ite(Value):
    _numc = 4
    def __init__(self, pred: Value, t: Value, f: Value):
        super().__init__(t.T, pred, t, f)

class Not(Value):
    _numc = 2
    def __init__(self, a: Value):
        super().__init__(BoolT(), a)

class Neg(Value):
    _numc = 2
    def __init__(self, a: Value):
        super().__init__(IntT(), a)

class Div(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(IntT(), a, b)

class Mod(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(IntT(), a, b)

class Conj(Value):
    _numc = -1
    def __init__(self, *args: Value):
        super().__init__(BoolT(), *args)

class Disj(Value):
    _numc = -1
    def __init__(self, *args: Value):
        super().__init__(BoolT(), *args)

# integer sum
class Sum(Value):
    _numc = -1
    def __init__(self, *args: Value):
        super().__init__(IntT(), *args)

# integer product
class Prod(Value):
    _numc = -1
    def __init__(self, *args: Value):
        super().__init__(IntT(), *args)

## Domains

# Dom(T)
class Universe(Value):
    _numc = 1
    def __init__(self, carT: Type):
        super().__init__(DomT(carT))

# Int -> Dom[Int]
class Fin(Value):
    _numc = 2
    def __init__(self, N: Value):
        T = DomT(IntT(), fin=True, ord=True)
        super().__init__(T, N)

# Dom[EnumT]
class Enum(Value):
    _numc = 1
    def __init__(self, enumT: EnumT):
        T = DomT(enumT, fin=True, ord=False)
        super().__init__(T)

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
    def __init__(self, domain: Value):
        super().__init__(IntT(), domain)

# Dom(A) -> A -> Bool 
class IsMember(Value):
    _numc = 3
    def __init__(self, domain: Value, val: Value):
        super().__init__(BoolT(), domain, val)

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

# (A|B|...) -> (A->T, B->T,...) -> T
class Match(Value):
    _numc = 3
    def __init__(self, T: Type, scrut: Value, branches: Value):
        super().__init__(T, scrut, branches)

# Dom(A) -> (A->Bool) -> Dom(A)
class Restrict(Value):
    _numc = 3
    def __init__(self, T: Type, domain: Value, pred: Value):
        super().__init__(T, domain, pred)

# Dom(A) -> (A -> Bool) -> Bool
class Forall(Value):
    _numc = 3
    def __init__(self, domain: Value, fun: Value):
        super().__init__(BoolT(), domain, fun)

# Dom(A) -> (A -> Bool) -> Bool
class Exists(Value):
    _numc = 3
    def __init__(self, domain: Value, fun: Value):
        super().__init__(BoolT(), domain, fun)

# Dom(A) -> (AxA->Bool) -> Dom(Dom(A))
#class Quotient(Value):
#    _numc = 2
#    def __init__(self, domain: Value, eqrel: Value):
#        super().__init__(domain, eqrel)


## Funcs (i.e., containers)

# Dom(A) -> (A->B) -> Func(Dom(A)->B)
class Map(Value):
    _numc=3
    def __init__(self, T: Type, dom: Value, fun: Value):
        super().__init__(T, dom, fun)

class Image(Value):
    _numc = 2
    def __init__(self, T: Type, func: Value):
        super().__init__(T, func)

# Func(Dom(A)->B) -> A -> B
class Apply(Value):
    _numc = 3
    def __init__(self, T: Type, func: Value, arg: Value):
        super().__init__(T, func, arg)

#(v0:A,v1:A,...) -> Func(Fin(n) -> A)
class ListLit(Value):
    _numc = -1
    def __init__(self, T: Type, *vals: Value):
        super().__init__(T, *vals)

# only used on Seq Funcs TODO maybe should have scan as the fundimental IR node
# Seq[A] -> ((A,B) -> B) -> B -> B
class Fold(Value):
    _numc = 4
    def __init__(self, T: Type, func: Value, fun: Value, init: Value):
        super().__init__(T, func, fun, init)

##############################
## Surface-level IR nodes (Used for analyis, but can be collapes)
##############################

class And(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(BoolT(), a, b)

class Implies(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(BoolT(), a, b)

class Or(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(a, b)

class Add(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(IntT(), a, b)

class Sub(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(IntT(), a, b)

class Mul(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(IntT(), a, b)

class Gt(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(BoolT(), a, b)

class GtEq(Value):
    _numc = 3
    def __init__(self, a: Value, b: Value):
        super().__init__(BoolT(), a, b)

# SeqDom[A] -> Int -> Int -> Func[Fin(n) -> SeqDom[A]]
class Windows(Value):
    _numc = 4
    def __init__(self, T: Type, dom: Value, size: Value, stride: Value):
        super().__init__(T, dom, size, stride)

# NDDom[A] -> (Int,...) -> (Int,...) -> Array[Fin(n1) x Fin(n2) x ... -> NDDom[A]]
class Tiles(Value):
    _numc = 4
    def __init__(self, T: Type, dom: Value, sizes: Value, strides: Value):
        super().__init__(T, dom, sizes, strides)

# creates an array of slices in a given index
class Slices(Value):
    _fields = ('idx',)
    _numc = 2
    def __init__(self, T: Type, dom: Value, idx: int):
        assert isinstance(idx, int)
        self.idx = idx
        super().__init__(T, dom)

# Common Fold Values
class SumReduce(Value):
    _numc = 2
    def __init__(self, func: Value):
        super().__init__(BoolT(), func)

# multiply all the elements of a sequence
class ProdReduce(Value):
    _numc = 2
    def __init__(self, func: Value):
        super().__init__(IntT(), func)

class AllDistinct(Value):
    _numc = 2
    def __init__(self, func: Value):
        super().__init__(BoolT(), func)

class AllSame(Value):
    _numc = 2
    def __init__(self, func: Value):
        super().__init__(BoolT(), func)

##############################
## Constructor-level IR nodes (Used for construction but immediatley gets transformed)
##############################

# gets tranformed to a de-bruijn BoundVar
class _BoundVarPlaceholder(Value):
    _numc = 1
    def __init__(self, T: Type):
        super().__init__(T)

class _LambdaPlaceholder(Value):
    _numc = 2
    def __init__(self, T: Type, bound_var: Value, body: Value):
        super().__init__(T, bound_var, body)

class _VarPlaceholder(Value):
    _fields = ('sid',)
    _numc = 1
    def __init__(self, T: Type, sid: int):
        self.sid = sid
        super().__init__(T)

# Mapping from Value classes to a priority integer.
# This is probably way overengineered and there are probably better priorities
NODE_PRIORITY: tp.Dict[tp.Type[Value], int] = {
    Unit: -1,
    Lit: 0,
    VarRef: 1,
    _VarPlaceholder: 1,
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
    #Quotient: 9,
    Map: 10,
    Image: 10,
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

