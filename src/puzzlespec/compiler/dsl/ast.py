from __future__ import annotations
import typing as tp
from . import ir
from dataclasses import dataclass
from enum import Enum as _Enum
from .utils import _is_kind, _is_same_kind, _applyT

@dataclass
class TExpr:
    node: ir.Type

    def __post_init__(self):
        assert isinstance(self.node, ir.Type)

class UnitType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.UnitT):
            raise ValueError(f"Expected UnitType, got {self.node}")

class BoolType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.BoolT):
            raise ValueError(f"Expected BoolType, got {self.node}")

class IntType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.IntT):
            raise ValueError(f"Expected IntType, got {self.node}")

class EnumType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.EnumT):
            raise ValueError(f"Expected EnumType, got {self.node}")

class TupleType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.TupleT):
            raise ValueError(f"Expected TupleType, got {self.node}")

    def elemT(self, i: int) -> TExpr:
        if not isinstance(i, int):
            raise ValueError("Tuple index must be concrete (python) int")
        return wrapT(self.node[i])

    def __getitem__(self, i: int):
        return self.elemT(i)

    def elemTs(self) -> tp.Tuple[TExpr]:
        return tuple(self.elemT(i) for i in range(len(self)))

    def __len__(self):
        return len(self.node)


class SumType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.SumT):
            raise ValueError(f"Expected SumType, got {self.node}")

    def elemT(self, i: int) -> TExpr:
        if not isinstance(i, int):
            raise ValueError("Tuple index must be concrete (python) int")
        return wrapT(self.node[i])

    def __len__(self):
        return len(self.node)

    @property
    def elemTs(self) -> tp.Tuple[TExpr]:
        return tuple(self.elemT(i) for i in range(len(self)))

    def __getitem__(self, i: int):
        return self.elemT(i)


class LambdaType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir._LambdaTPlaceholder):
            raise ValueError(f"Expected LambdaType, got {self.node}")

    @property
    def argT(self) -> TExpr:
        return wrapT(self.node.argT)
    
    @property
    def resT(self) -> TExpr:
        return wrapT(self.node.resT)

class DomainType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.DomT):
            raise ValueError(f"Expected DomainType, got {self.node}")

    @property
    def carT(self) -> TExpr:
        return wrapT(self.node.carT)
    
    @property
    def axes(self) -> tp.Tuple[int]:
        return self.node.axes

    @property
    def rank(self) -> int:
        return len(self.axes)

    @property
    def fins(self) -> tp.Tuple[bool]:
        return self.node.fins
    
    @property
    def fin(self) -> bool:
        return self.node.fin

    @property
    def ord(self) -> bool:
        return self.node.ord

    @property
    def ords(self) -> tp.Tuple[bool]:
        return self.node.ords

    @property
    def num_factors(self):
        return len(self.ords)

    def factorT(self, idx: int) -> TExpr:
        return wrapT(self.node.factors[idx])


class PiType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.PiT):
            raise ValueError(f"Expected PiType, got {self.node}")

    def elemT(self, arg: Expr) -> TExpr:
        return wrapT(_applyT(self.node, arg.node))

    @property
    def lamT(self) -> LambdaType:
        return wrapT(self.node.lamT)


def wrapT(T: ir.Type):
    assert isinstance(T, ir.Type)
    match type(T):
        case ir.UnitT:
            return UnitType(T)
        case ir.BoolT:
            return BoolType(T)
        case ir.IntT:
            return IntType(T)
        case ir.EnumT:
            return EnumType(T)
        case ir.TupleT:
            return TupleType(T)
        case ir.SumT:
            return SumType(T)
        case ir._LambdaTPlaceholder:
            return LambdaType(T)
        case ir.DomT:
            return DomainType(T)
        case ir.PiT:
            return PiType(T)
        case _:
            raise ValueError(f"Expected Type, got {T}")

class ExprMakeError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

@dataclass
class Expr:
    node: ir.Value

    def __post_init__(self):
        if not isinstance(self.node, ir.Value):
            raise ValueError(f"Expr must be an ir.Value, got {self.node}")

    @property
    def _T(self) -> TExpr:
        return wrapT(self.node.T)
    
    @classmethod
    def make(cls, val: tp.Any) -> Expr:
        if isinstance(val, Expr):
            if type(val)==Expr:
                raise ValueError("Raw Expr found!!", val)
            return val
        if isinstance(val, ir.Value):
            return wrap(val)
        if isinstance(val, bool):
            return BoolExpr.make(val)
        if isinstance(val, int):
            return IntExpr.make(val)
        if isinstance(val, tp.Tuple):
            return TupleExpr.make(val)
        if isinstance(val, tp.List):
            return ArrayExpr.make(val)
        if isinstance(val, _Enum):
            return EnumDomainExpr.make(val)
        raise ExprMakeError(f"Cannot make Expr from {val}")

    def __repr__(self):
        return f"<{type(self).__name__} {self.node}>"

    # "Hack" to construct variables within a map
    def _set_map_dom(self, dom: DomainExpr):
        if dom is not None:
            assert isinstance(self.node, ir._BoundVarPlaceholder)
            assert isinstance(dom, DomainExpr)
            self._map_dom = dom

    def __eq__(self, other):
        other = Expr.make(other)
        if not _is_same_kind(self.T, other.T):
            raise ValueError(f"Cannot compare {self.T} and {other.T}")
        return wrap(ir.Eq(ir.BoolT(), self.node, other.node))
        
    def __ne__(self, other):
        return ~(self == other)

class UnitExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_UnitExpr(self.node):
            raise ValueError(f"Expected UnitExpr, got {self}")
        if not isinstance(self._T, UnitType):
            raise ValueError(f"Expected UnitType, got {self._T}")

    @property
    def T(self) -> UnitType:
        return tp.cast(UnitType, self._T)
    
    @staticmethod
    def make(cls) -> UnitExpr:
        return UnitExpr(ir.Unit())

class BoolExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_BoolExpr(self.node):
            raise ValueError(f"Expected BoolExpr, got {self}")
        if not isinstance(self._T, BoolType):
            raise ValueError(f"Expected BoolType, got {self._T}")

    @property
    def T(self) -> BoolType:
        return tp.cast(BoolType, self._T)

    @classmethod
    def make(cls, val: tp.Any) -> BoolExpr:
        if isinstance(val, BoolExpr):
            return val
        try:
            val = bool(val)
            node = ir.Lit(ir.BoolT(), val)
            return BoolExpr(node)
        except:
            raise ValueError(f"Cannot make BoolExpr from {val}")

    def __invert__(self) -> BoolExpr:
        node = ir.Not(ir.BoolT(), self.node)
        return BoolExpr(node)

    def implies(self, other: BoolOrExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Implies(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __and__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.And(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    __rand__ = __and__

    def __or__(self, other: BoolExpr) -> BoolExpr:
        node = ir.Or(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    __ror__ = __or__

    def ite(self, t: Expr, f: Expr) -> Expr:
        t, f = Expr.make(t), Expr.make(f)
        node = ir.Ite(t.T.node, self.node, t.node, f.node)
        return wrap(node)

    def __bool__(self) -> bool:
        raise TypeError("BoolExpr cannot be used as a python boolean")
    
    def to_int(self) -> IntExpr:
        return self.ite(IntExpr.make(1), IntExpr.make(0))

    @staticmethod
    def all_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(True)
        node = ir.Conj(ir.BoolT(), *[BoolExpr.make(a).node for a in args])
        return BoolExpr(node)

    @staticmethod
    def any_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(False)
        node = ir.Disj(ir.BoolT(), *[BoolExpr.make(a).node for a in args])
        return BoolExpr(node)

class IntExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_IntExpr(self.node):
            raise ValueError(f"Expected IntExpr, got {self}")
        if not isinstance(self._T, IntType):
            raise ValueError(f"Expected IntType, got {self._T}")

    @property
    def T(self) -> IntType:
        return tp.cast(IntType, self._T)

    @classmethod
    def make(cls, val: tp.Any) -> IntExpr:
        if isinstance(val, IntExpr):
            return tp.cast(IntExpr, val)
        try:
            val = int(val)
            node = ir.Lit(ir.IntT(), val)
            return IntExpr(node)
        except Exception as e:
            print(e)
            raise ValueError(f"Expected Int expression. Got {val}")

    def __add__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Add(ir.IntT(), self.node, other.node)
        return IntExpr(node)

    def __sub__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Sub(ir.IntT(), self.node, other.node)
        return IntExpr(node)

    def __neg__(self) -> IntExpr:
        node = ir.Neg(ir.IntT(), self.node)
        return IntExpr(node)

    def __abs__(self) -> IntExpr:
        node = ir.Abs(ir.IntT(), self.node)
        return IntExpr(node)

    def __mul__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mul(ir.IntT(), self.node, other.node)
        return IntExpr(node)

    def __floordiv__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Div(ir.IntT(), self.node, other.node)
        return IntExpr(node)

    def __mod__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mod(ir.IntT(), self.node, other.node)
        return IntExpr(node)

    def __gt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Gt(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __ge__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.GtEq(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __lt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Lt(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __le__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.LtEq(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __bool__(self) -> bool:
        raise TypeError("IntExpr cannot be used as a python boolean")

    def fin(self) -> SeqDomainExpr:
        T = ir.DomT.make(carT=ir.IntT(), fin=True, ord=True)
        node = ir.Fin(T, self.node)
        return SeqDomainExpr(node)

class EnumExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_EnumExpr(self.node):
            raise ValueError(f"Expected EnumExpr, got {self}")
        if not isinstance(self._T, EnumType):
            raise ValueError(f"Expected EnumType, got {self._T}")
    
    @property
    def T(self) -> EnumType:
        return tp.cast(EnumType, self._T)

    @classmethod
    def make(cls, val) -> EnumExpr:
        if isinstance(val, EnumExpr):
            return val
        raise NotImplementedError(f"cannot cast {val} to EnumExpr")

IntOrExpr = tp.Union[int, IntExpr, Expr]
BoolOrExpr = tp.Union[bool, BoolExpr, Expr]
EnumOrExpr = tp.Union[str, EnumExpr, Expr]


class TupleExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_TupleExpr(self.node):
            raise ValueError(f"Expected TupleExpr, got {self}")
        if not isinstance(self._T, TupleType):
            raise ValueError(f"Expected TupleType, got {self._T}")

    @property
    def T(self) -> TupleType:
        return tp.cast(TupleType, self._T)
   
    @classmethod
    def make(cls, vals: tp.Tuple[tp.Any, ...]=None) -> TupleExpr:
        if vals is None:
            vals = ()
        if isinstance(vals, TupleExpr):
            return vals
        try:
            vals = tuple(Expr.make(v) for v in vals)
            node = ir.TupleLit(ir.TupleT(*[e.T.node for e in vals]), *[e.node for e in vals])
            return TupleExpr(node)
        except ExprMakeError as e:
            raise e

    @classmethod
    def empty(cls):
        return cls.make()

    def __getitem__(self, idx: int) -> Expr:
        if idx < 0 or idx >= len(self):
            raise IndexError(f"Tuple index out of range: {idx}")
        node = ir.Proj(self.T[idx].node, self.node, idx)
        return wrap(node)

    def __len__(self) -> int:
        return len(self.T)

    # Nice unpacking
    def __iter__(self) -> None:
        for i in range(len(self)):
            yield self[i]

class SumExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_SumExpr(self.node):
            raise ValueError(f"Expected SumExpr, got {self}")
        if not isinstance(self._T, SumType):
            raise ValueError(f"Expected SumType, got {self._T}")

    @property
    def T(self) -> SumType:
        return tp.cast(SumType, self._T)
 
    def match(self, *branches) -> Expr:
        if len(branches) != len(self.T):
            raise ValueError(f"Need a branch for each element of the sum type, got {len(branches)} branches for {len(self.T)} elements")
        branch_exprs = [make_lambda(lam_expr, sort=T) for lam_expr, T in zip(branches, self.T.elemTs)]
        resT0 = branch_exprs[0].T.resT
        if not all(type(resT0) == type(e.T.resT) for e in branch_exprs):
            raise ValueError(f"Expected all branches to have result type {resT0}, got {', '.join([repr(e.T.resT) for e in branch_exprs])}")
        match_node = ir.Match(resT0.node, self.node, TupleExpr.make([e.node for e in branch_exprs]).node)
        # TODO probably should prove type equality for all result types
        return wrap(match_node)


class LambdaExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_LambdaExpr(self.node):
            raise ValueError(f"Expected LambdaExpr, got {self}")
        if not isinstance(self._T, LambdaType):
            raise ValueError(f"Expected LambdaType, got {self._T}")

    @property
    def T(self) -> LambdaType:
        return tp.cast(LambdaType, self._T)
 
    @property
    def argT(self) -> ir.Type:
        return self.T.argT

    @property
    def resT(self) -> ir.Type:
        return self.T.resT

    def __repr__(self):
        return f"{self.argT} -> {self.resT}"

def make_lambda(fn: tp.Callable, sort: TExpr, map_dom: DomainExpr=None) -> LambdaExpr:
    bv_node = ir._BoundVarPlaceholder(sort.node)
    bv_expr = wrap(bv_node)
    # 'Hack' to get fancy var constructors working
    bv_expr._set_map_dom(map_dom)
    ret_expr = fn(bv_expr)
    ret_expr = Expr.make(ret_expr)
    lamT = ir._LambdaTPlaceholder(bv_node, ret_expr._T.node)
    lambda_node = ir._LambdaPlaceholder(lamT, bv_node, ret_expr.node)
    return LambdaExpr(lambda_node)

class DomainExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_DomainExpr(self.node):
            raise ValueError(f"Domain must be a DomT, got {type(self.T)}")
        if not isinstance(self._T, DomainType):
            raise ValueError(f"Expected DomainType, got {self._T}")

    @property
    def T(self) -> DomainType:
        return tp.cast(DomainType, self._T)
 
    @classmethod
    def make(cls, val):
        raise NotImplementedError()
    
    def restrict(self, pred_fun: tp.Callable) -> DomainExpr:
        lambda_expr = make_lambda(pred_fun, sort=self.T.carT)
        if not isinstance(lambda_expr.T.resT, BoolType):
            raise ValueError(f"Restrict predicate must return Bool, got {lambda_expr.T.resT}")
        T = ir.DomT.make(carT=self.T.carT.node, fin=self.T.fin, ord=self.T.ord)
        node = ir.Restrict(T, self.node, lambda_expr.node)
        return DomainExpr(node)

    def map(self, fn: tp.Callable) -> FuncExpr:
        lambda_expr = make_lambda(fn, sort=self.T.carT, map_dom=self)
        lamT = lambda_expr.T
        T = ir.PiT(self.node, lamT.node)
        node = ir.Map(T, self.node, lambda_expr.node)
        return wrap(node)

    @classmethod
    def cartprod(cls, *doms: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(dom, DomainExpr) for dom in doms):
            raise ValueError(f"Expected all DomainExpr, got {doms}")
        carT = ir.TupleT(*[dom.T.carT.node for dom in doms])
        dom_nodes = tuple(dom.node for dom in doms)
        factors = ()
        fins = ()
        ords = ()
        axes = ()
        offset=0
        for dom in doms:
            # TODO START HERE need access to 'factors'
            factors += tuple(dom.T.factorT(i).node for i in range(dom.T.num_factors))
            axes += tuple(offset + ax for ax in dom.T.axes)
            fins += dom.T.fins
            ords += dom.T.ords
            offset += len(factors)
        T = ir.DomT(*factors, fins=fins, ords=ords, axes=axes)
        cartprod_node = ir.CartProd(T, *dom_nodes)
        return wrap(cartprod_node)

    def prod(self, *others: 'DomainExpr') -> 'DomainExpr':
        return DomainExpr.cartprod(self, *others)

    def coproduct(self, *others: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(other, DomainExpr) for other in others):
            raise ValueError(f"Expected list of DomainExpr, got {others}")
        doms: tp.List[DomainExpr] = [self, *others]
        carT = ir.SumT(*[dom.T.carT.node for dom in doms])
        T = ir.DomT.make(carT=carT, fin=self.T.fin and all(other.T.fin for other in others), ord=self.T.ord and all(other.T.ord for other in others))
        coprod_node = ir.DisjUnion(T, *[dom.node for dom in doms])
        return wrap(coprod_node)

    def forall(self, pred_fun: tp.Callable) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, sort=self.T.carT)
        if not isinstance(lambda_expr.T.resT, BoolType):
            raise ValueError(f"Forall predicate must return Bool, got {lambda_expr.T.resT}")
        node = ir.Forall(ir.BoolT(), self.node, lambda_expr.node)
        return BoolExpr(node)

    def exists(self, pred_fun: tp.Callable) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, sort=self.T.carT)
        if not isinstance(lambda_expr.T.resT, BoolType):
            raise ValueError(f"Exists predicate must return Bool, got {lambda_expr.T.resT}")
        node = ir.Exists(ir.BoolT(), self.node, lambda_expr.node)
        return BoolExpr(node)

    def dom_proj(self, idx: int) -> DomainExpr:
        if idx >= self.T.num_factors:
            raise ValueError(f"Cannot project to {idx}'th dim of {self}")
        facT = self.T.factorT(idx)
        T = ir.DomT.make(carT=facT.node, fin=self.T.fins[idx], ord=self.T.ords[idx])
        node = ir.DomProj(T, self.node, idx)
        return wrap(node)
    
    def restrictEq(self, val: Expr):
        val = Expr.make(val)
        if type(val.T) != type(self.T.carT):
            raise ValueError(f"{val} is wrong type for {self.T}")
        assert self.T.rank==1
        #factors = tuple(self.T.factorT(i).node for i in range(self.T.num_factors))
        T = ir.DomT(val.T.node, fins=(True,), ords=(True,), axes=())
        return wrap(ir.RestrictEq(T, self.node, val.node))

    @property
    def size(self) -> IntExpr:
        node = ir.Card(ir.IntT(), self.node)
        return IntExpr(node)

    @property
    def shape(self) -> tp.Tuple[IntExpr]:
        return tuple(self.dom_proj(ax).size for ax in self.T.axes)

    def __contains__(self, elem: Expr) -> BoolExpr:
        raise ValueError("Cannot use 'in'. Use dom.contains(val). Blame python for not being able to do this")

    def contains(self, elem: Expr):
        elem = Expr.make(elem)
        node = ir.IsMember(ir.BoolT(), self.node, elem.node)
        return BoolExpr(node)

    def __add__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.coproduct(other)
    
    def __mul__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.prod(other)


class _EnumAttrs:
    def __init__(self, enumT: EnumType):
        assert isinstance(enumT, EnumType)
        for label in enumT.node.labels:
            label_node = ir.EnumLit(enumT.node, label)
            label_expr = EnumExpr(label_node)
            setattr(self, label, label_expr)

class EnumDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_EnumDomainExpr(self.node):
            raise ValueError(f"Expected EnumDomainExpr, got {self}")
        if not isinstance(self.T.carT, EnumType):
            raise ValueError(f"Expected EnumType, got {self.T.carT.node}")
        self._members = _EnumAttrs(self.T.carT)


    @property
    def members(self) -> _EnumAttrs:
        return self._members

    @classmethod
    def make(cls, val: tp.Any) -> EnumDomainExpr:
        if isinstance(val, EnumDomainExpr):
            return val
        elif isinstance(val, _Enum):
            raise NotImplementedError()
        raise ValueError(f"Expected EnumDomainExpr, got {val}")

    @classmethod
    def make_from_labels(cls, *labels: str, name: str=None) -> EnumDomainExpr:
        if len(labels) == 0:
            raise NotImplementedError("cannot have a 0-label Enum")
        if name is None:
            name = "".join(labels)
        enumT = ir.EnumT(name, tuple(labels))
        node = ir.Universe(ir.DomT.make(carT=enumT, fin=True, ord=False))
        return EnumDomainExpr(node)

class SeqDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_SeqDomainExpr(self.node):
            raise ValueError(f"Expected SeqDomainExpr, got {self}")

    def slice(self, lo: IntExpr, hi: IntExpr):
        lo, hi = IntExpr.make(lo), IntExpr.make(hi)
        assert self.T.rank==1
        return wrap(ir.Slice(self.T.node, self.node, lo.node, hi.node))

    def elemAt(self, idx: IntOrExpr):
        idx = IntExpr.make(idx)
        node = ir.ElemAt(self.T.carT.node, self.node, idx.node)
        return wrap(node)

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> ArrayExpr:
        size = IntExpr.make(size)
        stride = IntExpr.make(stride)
        dom: DomainExpr = ((self.size-(size-stride))//stride).fin()
        wins = dom.map(
            lambda i: self[i*stride:i*stride+size] 
        )
        return wins
    
    def __getitem__(self, idx: tp.Any):
        if isinstance(idx, slice):
            start, step, stop = idx.start, idx.step, idx.stop
            if step is not None:
                raise ValueError("No step allowed in slices")
            if start is None:
                start = 0
            if stop is None:
                stop = self.size
            return self.slice(start, stop)
        else:
            return self.elemAt(idx)
            
 
class NDSeqDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_NDSeqDomainExpr(self.node):
            raise ValueError(f"Expected NDSeqDomainExpr, got {self}")

    def tiles(self, size: tp.Tuple[IntOrExpr, ...], stride: tp.Tuple[IntOrExpr, ...]=None) -> NDArrayExpr:
        rank = self.T.rank
        if stride == None:
            strides = [IntExpr.make(1) for _ in range(rank)]
        else:
            strides = [IntExpr.make(s) for s in stride]
        sizes = [IntExpr.make(s) for s in size]
        if len(sizes) != rank or len(strides) != rank:
            raise ValueError(f"Expected size and stride for all dimensions ({rank}), got {size} and {stride}")
        fins = [((self.doms[i].size-(sizes[i]-strides[i]))//strides[i]).fin() for i in range(rank)]
        dom = DomainExpr.cartprod(*fins)
        def tile_lam(idx):
            slices = [slice(idx[i]*strides[i], (idx[i]*strides[i])+sizes[i]) for i in range(rank)]
            return self[*slices]
        return dom.map(tile_lam)

    @property
    def doms(self) -> tp.Tuple[DomainExpr]:
        return tuple(self.dom_proj(i) for i in self.T.axes)

    def rows(self) -> ArrayExpr[SeqDomainExpr]:
        if not is_2DSeqDomainExpr(self.node):
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.doms[0].map(lambda r: self[r,:])

    def cols(self) -> ArrayExpr[SeqDomainExpr]:
        if not is_2DSeqDomainExpr(self.node):
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.doms[1].map(lambda c: self[:,c])

    def __getitem__(self, val: tp.Any):
        rank = self.T.rank
        if not isinstance(val, tuple) and len(val) != rank:
            raise ValueError(f"Getitem must have length {rank}")
        doms = []
        for dom, v in zip(self.doms, val):
            if isinstance(v, slice):
                new_dom = dom[v]
            else:
                v = IntExpr.make(v)
                new_dom = dom.restrictEq(dom.elemAt(v))
            doms.append(new_dom)
        return DomainExpr.cartprod(*doms)


class FuncExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_FuncExpr(self.node):
            raise ValueError(f"Expected FuncExpr, got {self.T}")

    @property
    def T(self) -> PiType:
        return tp.cast(PiType, self._T)

    @property
    def domain(self) -> DomainExpr:
        if isinstance(self.T.node, ir.PiT):
            return wrap(self.T.node.dom)
        domT = self.T.domT
        domain = ir.Domain(domT.node, self.node)
        return DomainExpr(domain)

    @property
    def image(self) -> DomainExpr:
        T = ir.DomT.make(carT=self.elemT, fin=True, ord=True)
        node = ir.Image(T, self.node)
        return wrap(node)

    def apply(self, arg: Expr) -> Expr:
        arg = Expr.make(arg)
        node = ir.Apply(self.T.elemT(arg).node, self.node, arg.node)
        return wrap(node)

    # Func[Dom(A) -> B] -> (B -> C) -> Func[Dom(A) -> C]
    def map(self, fn: tp.Callable) -> FuncExpr:
        return self.domain.map(lambda a: fn(self.apply(a)))

    # Func[Dom(A) -> B] -> Func[Dom(A) -> (A, B)]
    def enumerate(self) -> FuncExpr:
        return self.domain.map(lambda a: TupleExpr.make((a, self.apply(a))))

    # Func[Dom(A) -> B] -> ((A,B) -> C) -> Func[Dom(A) -> C]
    def imap(self, fn: tp.Callable) -> 'FuncExpr':
        return self.enumerate().map(fn)

    def forall(self, pred_fun: tp.Callable) -> BoolExpr:
        return self.domain.forall(lambda a: pred_fun(self.apply(a)))

    def exists(self, pred_fun: tp.Callable) -> BoolExpr:
        return self.domain.exists(lambda a: pred_fun(self.apply(a)))

    def size(self) -> IntExpr:
        return self.domain.size

    def sum(self) -> IntExpr:
        return IntExpr(ir.SumReduce(ir.IntT(), self.node))
    
    def __contains__(self, elem: Expr) -> BoolExpr:
        return elem in self.image

    def __call__(self, val: Expr) -> Expr:
        return self.apply(val)

    # Basically a 'gather'
    def __getitem__(self, dom: DomainExpr) -> FuncExpr:
        if not isinstance(dom, DomainExpr):
            raise ValueError(f"Can only index into funcs with a domain.\nFunc: {self}\n Got: {dom}")
        return dom.map(lambda v: self.apply(v))

class ArrayExpr(FuncExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_ArrayExpr(self.node):
            raise ValueError(f"Array domain must be enumerable with rank 1, got {self.T}")
  
    @classmethod
    def make(cls, val: tp.List[tp.Any]) -> ArrayExpr:
        if isinstance(val, ArrayExpr):
            return val
        try:
            vals = [Expr.make(v) for v in val]
        except:
            raise ValueError(f"Expected List of values, got {val}")
        if not all(v.T.eq(vals[0].T) for v in vals):
            raise ValueError(f"Expected List of values with the same type, got {vals}")
        node = ir.ListLit(vals[0].T, *[e.node for e in vals])
        return ArrayExpr(node)

    @property
    def domain(self) -> SeqDomainExpr:
        dom = super().domain
        return SeqDomainExpr(dom.node)

    @property
    def size(self) -> IntExpr:
        return self.domain.size

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> ArrayExpr:
        wins = self.domain.windows(size, stride) # Func[Fin(n) -> SeqDom(A)]
        return wins.map(lambda win: win.map(lambda i: self(i)))

    def __getitem__(self, k: tp.Any):
        if isinstance(k, (int, IntExpr)):
            k = Expr.make(k)
            v = self.apply(self.domain.elemAt(k))
            return v
        elif isinstance(k, DomainExpr):
            return super().__getitem__(k)
        raise NotImplementedError(f"Cannot handle {type(k)} in __getitem__")

    def __iter__(self) -> None:
        raise ValueError("ArrayExpr is not iterable at python runtime")

# Func[NDDom -> T]
class NDArrayExpr(FuncExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_NDArrayExpr(self.node):
            raise ValueError(f"NDSeq domain must be enumerable with rank 2, got {self.T}")

    @property
    def domain(self) -> NDSeqDomainExpr:
        dom = super().domain
        return NDSeqDomainExpr(dom.node)

    def rows(self) -> ArrayExpr:
        return self.domain.rows().map(lambda row_dom: self[row_dom])

    def cols(self) -> ArrayExpr:
        return self.domain.cols().map(lambda col_dom: self[col_dom])

    def tiles(self, size: tp.Tuple[IntOrExpr, ...], stride: tp.Tuple[IntOrExpr, ...]=None) -> ArrayExpr:
        return self.domain.tiles(size, stride).map(
            lambda tile_dom: tile_dom.map(lambda indices: self.apply(indices))
        )

    def __getitem__(self, v: tp.Any):
        if isinstance(v, DomainExpr):
            return super().__getitem__(v)
        raise NotImplementedError(f"Cannot handle {type(v)} in __getitem__")

def is_UnitExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.UnitT)

def is_BoolExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.BoolT)

def is_IntExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.IntT)

def is_EnumExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.EnumT)

def is_TupleExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.TupleT)

def is_SumExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.SumT)

def is_LambdaExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir._LambdaTPlaceholder)

def is_DomainExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.DomT)

def is_EnumDomainExpr(node: ir.Node) -> bool:
    return is_DomainExpr(node) and _is_kind(node.T.carT, ir.EnumT)

def is_SeqDomainExpr(node: ir.Node) -> bool:
    return is_DomainExpr(node) and node.T.ord and node.T.fin and node.T.rank==1

def is_2DSeqDomainExpr(node: ir.Node) -> bool:
    return is_NDSeqDomainExpr(node) and node.T.rank==2

def is_NDSeqDomainExpr(node: ir.Node) -> bool:
    return is_DomainExpr(node) and node.T.ord and node.T.fin and node.T.rank > 1

def is_FuncExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.PiT)

def is_ArrayExpr(node: ir.Node) -> bool:
    return is_FuncExpr(node) and is_SeqDomainExpr(node.T.dom)

def is_NDArrayExpr(node: ir.Node) -> bool:
    return is_FuncExpr(node) and is_NDSeqDomainExpr(node.T.dom)

def wrap(node: ir.Node) -> Expr:
    # Base theory types
    if is_UnitExpr(node):
        return UnitExpr(node)
    if is_BoolExpr(node):
        return BoolExpr(node)
    if is_IntExpr(node):
        return IntExpr(node)
    if is_EnumExpr(node):
        return EnumExpr(node)
    if is_LambdaExpr(node):
        return LambdaExpr(node)
    if is_TupleExpr(node):
        return TupleExpr(node)
    if is_SumExpr(node):
        return SumExpr(node)
    # Domain types
    if is_EnumDomainExpr(node):
        return EnumDomainExpr(node)
    if is_NDSeqDomainExpr(node):
        return NDSeqDomainExpr(node)
    if is_SeqDomainExpr(node):
        return SeqDomainExpr(node)
    if is_EnumDomainExpr(node):
        return EnumDomainExpr(node)
    if is_DomainExpr(node):
        return DomainExpr(node)
    # Func types
    if is_NDArrayExpr(node):
        return NDArrayExpr(node)
    if is_ArrayExpr(node):
        return ArrayExpr(node)
    if is_FuncExpr(node):
        return FuncExpr(node)
    raise NotImplementedError(f"Cannot cast node {node} with T={node.T} to Expr")
