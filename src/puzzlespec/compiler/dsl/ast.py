from __future__ import annotations
import typing as tp
from . import ir
from dataclasses import dataclass
from enum import Enum as _Enum
from .utils import _is_kind, _is_same_kind, _applyT, _has_bv, _substitute
from ..passes.analyses.pretty_printer import pretty
from ..passes.analyses.kind_check import get_rawT

@dataclass
class TExpr:
    _node: ir.Type
    def __post_init__(self):
        assert isinstance(self._node, ir.Type)

    def __repr__(self):
        return pretty(self._node)

    @property
    def node(self):
        if self.is_ref:
            return self._node.T
        return self._node

    @property
    def is_ref(self):
        return isinstance(self._node, ir.RefT)
    
    @property
    def ref_dom(self):
        assert self.is_ref
        return DomainExpr(self.node.dom)

    def __str__(self):
        return pretty(self._node)

    def simplify(self) -> tp.Self:
        from ..passes.utils import simplify
        return type(self)(simplify(self.node))


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

    def make_sum(self, val: tp.Any) -> SumExpr:
        return SumExpr.make(self, val)

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
        if not isinstance(self.node, ir.LambdaTHOAS):
            raise ValueError(f"Expected LambdaType, got {self.node}")

    @property
    def argT(self) -> TExpr:
        return wrapT(self.node.argT)

    def resT(self, arg: Expr):
        return wrapT(_applyT(self.node, arg.node))

class _DomainType(TExpr): pass

class DomainType(_DomainType):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.DomT):
            raise ValueError(f"Expected DomainType, got {self.node}")

    @property
    def carT(self) -> TExpr:
        return wrapT(self.node.carT)

class ImageType(_DomainType):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.ImageT):
            raise ValueError(f"Expected DomainType, got {self.node}")

    @property
    def dom(self) -> DomainExpr:
        return DomainExpr(self.node.dom)

    @property
    def lamT(self) -> LambdaType:
        return LambdaType(self.node.lamT)

class FuncType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.FuncT):
            raise ValueError(f"Expected FuncType, got {self.node}")

    def elemT(self, arg: Expr) -> TExpr:
        return self.lamT.resT(arg)

    @property
    def domain(self) -> DomainExpr:
        return DomainExpr(self.node.dom)

    @property
    def lamT(self) -> LambdaType:
        return wrapT(self.node.lamT)

def wrapT(T: ir.Type):
    assert isinstance(T, ir.Type)
    if isinstance(T, ir.RefT):
        _T = T.T
    else:
        _T = T
    match type(_T):
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
        case ir.LambdaTHOAS:
            return LambdaType(T)
        case ir.DomT:
            return DomainType(T)
        case ir.FuncT:
            return FuncType(T)
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
    def T(self) -> TExpr:
        raise NotImplementedError()

    @property
    def _T(self) -> TExpr:
        return wrapT(self.node.T)
    
    @classmethod
    def make(cls, val: tp.Any) -> Expr:
        if isinstance(val, Expr):
            if type(val)==Expr:
                raise ValueError("Raw Expr found!!", val)
            return val
        #if val is None:
        #    return UnitExpr.make()
        if isinstance(val, ir.Value):
            return wrap(val)
        if isinstance(val, bool):
            return BoolExpr.make(val)
        if isinstance(val, int):
            return IntExpr.make(val)
        if isinstance(val, tp.Tuple):
            return TupleExpr.make(val)
        raise ExprMakeError(f"Cannot make Expr from {val}")

    def __eq__(self, other):
        other = Expr.make(other)
        if not _is_same_kind(self.T.node, other.T.node):
            raise ValueError(f"Cannot compare {self.T} and {other.T}")
        return wrap(ir.Eq(ir.BoolT(), self.node, other.node))
        
    def __ne__(self, other):
        return ~(self == other)

    def __repr__(self):
        return pretty(self.node)

    @property
    def simplify(self) -> tp.Self:
        from ..passes.utils import simplify
        simp = simplify(self.node)
        return wrap(simp)


class UnitExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, UnitType):
            raise ValueError(f"Expected UnitType, got {self._T}")

    @property
    def T(self) -> UnitType:
        return tp.cast(UnitType, self._T)
    
    @classmethod
    def make(cls) -> UnitExpr:
        node = ir.Unit(ir.UnitT())
        return UnitExpr(node)

class BoolExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
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
        if not isinstance(self._T, IntType):
            raise ValueError(f"Expected IntType, got {self._T}")

    @property
    def T(self) -> IntType:
        return tp.cast(IntType, self._T)

    @classmethod
    def make(cls, val: tp.Any) -> IntExpr:
        if isinstance(val, IntExpr):
            return tp.cast(IntExpr, val)
        if isinstance(val, int):
            node = ir.Lit(ir.IntT(), val)
            return IntExpr(node)
        raise ValueError(f"Expected Int expression. Got {val}")

    #def fin(self):
    #    return DomainExpr(ir.Fin(ir.DomT(ir.IntT()), self.node), _fin=True)

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

class EnumExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
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
        if isinstance(vals, tp.Tuple):
            vals = tuple(Expr.make(v) for v in vals)
            node = ir.TupleLit(ir.TupleT(*[e.T.node for e in vals]), *[e.node for e in vals])
            return TupleExpr(node)
        raise ExprMakeError(f"Cannot make TupleExpr from {vals}")

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
        if not isinstance(self._T, SumType):
            raise ValueError(f"Expected SumType, got {self._T}")

    @classmethod
    def make(cls, T: SumType, val: tp.Any):
        val = Expr.make(val)
        idx = None
        for i, eT in enumerate(T.elemTs):
            if type(val.T)==type(eT):
                idx = i
        if idx is None:
            raise ValueError(f"Cannot make SumExpr from {val} with type {T}")
        node = ir.Inj(T.node, val.node, idx=idx)
        return SumExpr(node)

    @property
    def T(self) -> SumType:
        return tp.cast(SumType, self._T)
 
    def match(self, *branches) -> Expr:
        if len(branches) != len(self.T):
            raise ValueError(f"Need a branch for each element of the sum type, got {len(branches)} branches for {len(self.T)} elements")
        branch_exprs = [make_lambda(lam_expr, sort=T.node) for lam_expr, T in zip(branches, self.T.elemTs)]
        lamTs = [e.T for e in branch_exprs]
        bv = wrap(ir.BoundVarHOAS(lamTs[0].argT.node))
        match_T = lamTs[0].resT(bv)
        if _has_bv(bv, match_T.node):
            raise NotImplementedError("Dependently typed match")
        match_node = ir.Match(match_T.node, self.node, *[e.node for e in branch_exprs])
        return wrap(match_node)


class LambdaExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, LambdaType):
            raise ValueError(f"Expected LambdaType, got {self._T}")

    @property
    def T(self) -> LambdaType:
        return tp.cast(LambdaType, self._T)

def make_lambda(fn: tp.Callable, sort: ir.Type) -> LambdaExpr:
    bv_node = ir.BoundVarHOAS(sort)
    bv_expr = wrap(bv_node)
    ret_expr = fn(bv_expr)
    ret_expr = Expr.make(ret_expr)
    # new bound_var for T
    #t_bv_node = ir.BoundVarHOAS(sort)
    #retT = _substitute(ret_expr.T.node, bv_node, t_bv_node)
    #lamT = ir.LambdaTHOAS(t_bv_node, retT)
    retT = ret_expr.T.node
    lamT = ir.LambdaTHOAS(bv_node, retT)
    lambda_node = ir.LambdaHOAS(lamT, bv_node, ret_expr.node)
    return LambdaExpr(lambda_node)

def cartprod(*doms: DomainExpr) -> DomainExpr:
    # TODO handle images
    if not all(isinstance(dom, DomainExpr) for dom in doms):
        raise ValueError(f"Expected all DomainExpr, got {doms}")
    carT = ir.TupleT(*[dom.T.carT.node for dom in doms])
    dom_nodes = tuple(dom.node for dom in doms)
    T = ir.DomT(carT)
    cartprod_node = ir.CartProd(T, *dom_nodes)
    return wrap(cartprod_node)

def coproduct(*doms: DomainExpr) -> DomainExpr:
    # TODO HANDLE IMAGES
    if not all(isinstance(other, DomainExpr) for other in doms):
        raise ValueError(f"Expected list of DomainExpr, got {doms}")
    if not all(isinstance(d.T, DomainType) for d in doms):
        raise NotImplementedError("Images not implemented for coproduct")
    carT = ir.SumT(*[dom.T.carT.node for dom in doms])
    T = ir.DomT(carT)
    coprod_node = ir.DisjUnion(T, *[dom.node for dom in doms])
    return wrap(coprod_node)

class DomainExpr(Expr):
    def __init__(self, node: ir.Value):
        super().__init__(node)
        self._fin = isinstance(node, ir.Fin)

    @property
    def T(self) -> _DomainType:
        return self._T

    @property
    def size(self) -> IntExpr:
        node = ir.Card(ir.IntT(), self.node)
        return IntExpr(node)

    def restrict(self, pred_fun: tp.Callable) -> DomainExpr:
        func_expr = self.map(pred_fun)
        node = ir.Restrict(self.T.node, func_expr.node)
        return DomainExpr(node)

    def contains(self, elem: Expr):
        elem = Expr.make(elem)
        node = ir.IsMember(ir.BoolT(), self.node, elem.node)
        return BoolExpr(node)

    def dom_proj(self, idx: int) -> DomainExpr:
        assert isinstance(idx, int)
        if isinstance(self.T, ImageType):
            raise NotImplementedError("Cannot project into an image")
        assert isinstance(self.T, DomainType)
        if not isinstance(self.T.carT, TupleType):
            raise NotImplementedError("cannot project to non-tuple carT")
        if idx not in range(len(self.T.carT)):
            raise IndexError(f"Index {idx} out of range for tuple of length {len(self.T.carT)}")
        if isinstance(self.node, ir.CartProd):
            return DomainExpr(self.node._children[1:][idx])
        proj_T = ir.DomT(self.T.carT[idx].node)
        node = ir.DomProj(proj_T, self.node, idx)
        return DomainExpr(node)
        
    def __add__(self, other: 'DomainExpr') -> 'DomainExpr':
        return coproduct(self, other)
    
    def __mul__(self, other: 'DomainExpr') -> 'DomainExpr':
        return cartprod(self, other)

    def __contains__(self, elem: Expr) -> BoolExpr:
        raise ValueError("Cannot use 'in'. Use dom.contains(val). Blame python for not being able to do this")

    def map(self, fn: tp.Callable) -> FuncExpr:
        if isinstance(self.T, ImageType):
            raise NotImplementedError("Cannot map over an image")
        carT_ref = ir.RefT(self.T.carT.node, self.node)
        lambda_expr = make_lambda(fn, sort=carT_ref)
        lamT = lambda_expr.T
        T = ir.FuncT(self.node, lamT.node)
        node = ir.Map(T, self.node, lambda_expr.node)
        return FuncExpr(node)

    @property
    def identity(self):
        return self.map(lambda i: i)

    def forall(self, pred_fun: tp.Callable) -> BoolExpr:
        func_expr = self.map(pred_fun)
        #if not isinstance(func_expr.T.lamT.resT, BoolType):
        #    raise ValueError(f"Forall predicate must return Bool, got {func_expr.T.lamT.resT}")
        node = ir.Forall(ir.BoolT(), func_expr.node)
        return BoolExpr(node)

    def exists(self, pred_fun: tp.Callable) -> BoolExpr:
        func_expr = self.map(pred_fun)
        #if not isinstance(func_expr.T.lamT.resT, BoolType):
        #    raise ValueError(f"Exists predicate must return Bool, got {func_expr.T.piT.resT}")
        node = ir.Exists(ir.BoolT(), func_expr.node)
        return BoolExpr(node)


class FuncExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, FuncType):
            raise ValueError(f"Expected FuncExpr, got {self.T}")

    @property
    def T(self) -> FuncType:
        return tp.cast(FuncType, self._T)

    @property
    def domain(self) -> DomainExpr:
        return DomainExpr(self.T.node.dom)

    @property
    def image(self) -> DomainExpr:
        T = ir.ImageT(
            self.domain.node,
            self.T.lamT
        )
        node = ir.Image(T, self.node)
        return wrap(node)

    def apply(self, arg: Expr) -> Expr:
        arg = Expr.make(arg)
        node = ir.ApplyFunc(self.T.elemT(arg).node, self.node, arg.node)
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
    
    # dom_row = ND({r} -> r, Fin(nC)-> Int)
    def gather(self, ndarr: NDArrayExpr):
        return ndarr.domain.map(lambda dom_idx: self.apply(dom_idx))

    # Basically a 'gather'
    def __getitem__(self, dom: DomainExpr) -> FuncExpr:
        if not isinstance(dom, DomainExpr):
            raise ValueError(f"Can only index into funcs with a domain.\nFunc: {self}\n Got: {dom}")
        return dom.map(lambda v: self.apply(v))

def wrap(node: ir.Node) -> Expr:
    T = wrapT(node.T)
    # Base theory types
    if isinstance(T, UnitType):
        return UnitExpr(node)
    if isinstance(T, BoolType):
        return BoolExpr(node)
    if isinstance(T, IntType):
        return IntExpr(node)
    if isinstance(T, EnumType):
        return EnumExpr(node)
    if isinstance(T, LambdaType):
        return LambdaExpr(node)
    if isinstance(T, TupleType):
        return TupleExpr(node)
    if isinstance(T, SumType):
        return SumExpr(node)
    if isinstance(T, (DomainType, ImageType)):
        return DomainExpr(node)
    if isinstance(T, FuncType):
        return FuncExpr(node)
    raise NotImplementedError(f"Cannot cast node {node} with T={T} to Expr")
