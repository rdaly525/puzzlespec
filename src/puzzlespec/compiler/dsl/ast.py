from __future__ import annotations
import typing as tp

from . import ir
from . import ir_types as irT
from dataclasses import dataclass

TExpr = tp.TypeVar('TExpr', bound="Expr")
KExpr = tp.TypeVar('KExpr', bound="Expr")
VExpr = tp.TypeVar('VExpr', bound="Expr")

def Param(name: str, T: irT.BaseType) -> Expr:
    assert T in (irT.Bool, irT.Int)
    node = ir._Param(name, T)
    return wrap(node, T)

def IntParam(name: str) -> IntExpr:
    return Param(name, irT.Int)

def BoolParam(name: str) -> BoolExpr:
    return Param(name, irT.Bool)

@dataclass
class Expr:
    node: ir.Node
    _T: irT.Type_

    @classmethod
    def make(cls, val: tp.Any) -> Expr:
        if isinstance(val, Expr):
            return val
        if isinstance(val, int):
            return IntExpr.make(val)
        if isinstance(val, bool):
            return BoolExpr.make(val)
        if isinstance(val, tp.Tuple):
            return TupleExpr.make(val)
        if isinstance(val, tp.List):
            return ListExpr.make(val)
        if isinstance(val, tp.Grid):
            return GridExpr.make(val)
        if isinstance(val, tp.Callable):
            raise NotImplementedError(f"make(Callable) not implemented")
        raise ValueError(f"Expected Expr or Node, got {type(val)}")

    def __repr__(self):
        return f"<{self.type} {self.node}>"

class UnitExpr(Expr):
    @property
    def T(self) -> irT.UnitType:
        assert self._T == irT.UnitType
        return tp.cast(irT.UnitType, self._T)
    
    @staticmethod
    def make(cls) -> UnitExpr:
        return UnitExpr(ir.Unit(), irT.UnitType)

class IntExpr(Expr):
    @property
    def T(self) -> irT._Int:
        assert self._T == irT.Int
        return tp.cast(irT._Int, self._T)

    @classmethod
    def make(cls, val: tp.Any) -> IntExpr:
        if isinstance(val, IntExpr):
            return tp.cast(IntExpr, val)
        try:
            val = int(val)
            node = ir.Lit(val, irT.Int)
            return tp.cast(IntExpr, wrap(node, irT.Int))
        except:
            raise ValueError(f"Expected Int expression. Got {val}")

    def __add__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Add(self.node, other.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def __sub__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Sub(self.node, other.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def __neg__(self) -> IntExpr:
        return tp.cast(IntExpr, wrap(ir.Neg(self.node), irT.Int))

    def __abs__(self) -> IntExpr:
        return (self >= 0).ite(self, -self)

    def __mul__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mul(self.node, other.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def __floordiv__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Div(self.node, other.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def __mod__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mod(self.node, other.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def __gt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Gt(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __ge__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.GtEq(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __lt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Lt(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __le__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.LtEq(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __eq__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Eq(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __ne__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Not(ir.Eq(self.node, other.node))
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __bool__(self) -> bool:
        raise TypeError("IntExpr cannot be used as a python boolean")

    def __repr__(self):
        return f"Int({self.node})"

    # Inclusive bounds
    def between(self, lo: IntOrExpr, hi: IntOrExpr) -> BoolExpr:
        return (self >= lo) & (self <= hi)

class BoolExpr(Expr):
    @property
    def T(self) -> irT._Bool:
        assert self._T == irT.Bool
        return tp.cast(irT._Bool, self._T)

    @classmethod
    def make(cls, val: tp.Any) -> BoolExpr:
        if isinstance(val, BoolExpr):
            return tp.cast(BoolExpr, val)
        try:
            val = bool(val)
            node = ir.Lit(val, irT.Bool)
            return tp.cast(BoolExpr, wrap(node, irT.Bool))
        except:
            raise ValueError(f"Expected Bool expression. Got {val}")

    def __invert__(self) -> BoolExpr:
        node = ir.Not(self.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def implies(self, other: BoolOrExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Implies(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __and__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        # Build a binary and which upstream passes may fold into Conj
        node = ir.And(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    __rand__ = __and__

    def __or__(self, other: BoolExpr) -> BoolExpr:
        # Build a binary or which upstream passes may fold into Disj
        node = ir.Or(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    __ror__ = __or__

    def __eq__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Eq(self.node, other.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))
    
    def __ne__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Not(ir.Eq(self.node, other.node))
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def ite(self, t: Expr, f: Expr) -> Expr:
        if t.T is not f.T:
            raise ValueError(f"t and f must have the same type, got {t.T} and {f.T}")
        node = ir.Ite(self.node, t.node, f.node)
        return tp.cast(Expr, wrap(node, t.T))

    def __bool__(self) -> bool:
        raise TypeError("BoolExpr cannot be used as a python boolean")

    @staticmethod
    def all_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(True)
        nodes = [BoolExpr.make(a).node for a in args]
        return tp.cast(BoolExpr, wrap(ir.Conj(*nodes), irT.Bool))

    @staticmethod
    def any_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(False)
        nodes = [BoolExpr.make(a).node for a in args]
        return tp.cast(BoolExpr, wrap(ir.Disj(*nodes), irT.Bool))


IntOrExpr = tp.Union[int, IntExpr, Expr]
BoolOrExpr = tp.Union[bool, BoolExpr, Expr]


class TupleExpr(Expr):
    @property
    def T(self) -> irT.TupleT:
        assert isinstance(self._T, irT.TupleT)
        return tp.cast(irT._Bool, self._T)
   
    @classmethod
    def make(cls, vals: tp.Tuple[tp.Any, ...]) -> TupleExpr:
        if isinstance(vals, TupleExpr):
            return tp.cast(TupleExpr, vals)
        try:
            vals = tuple(Expr.make(v) for v in vals)
            T = irT.TupleT(*[e.T for e in vals])
            return tp.cast(TupleExpr, wrap(ir.TupleLit(*[e.node for e in vals]), T))
        except:
            raise ValueError(f"Expected Tuple of values, got {vals}")

    def __getitem__(self, idx: int) -> Expr:
        node = ir.TupleGet(idx, self.node)
        return tp.cast(Expr, wrap(node, self.T.elemTs[idx]))

    def __len__(self) -> int:
        return len(self.node._children)

    def __iter__(self) -> tp.Iterator[Expr]:
        for i in range(len(self)):
            yield self[i]

class SumExpr(Expr):
    @property
    def T(self) -> irT.SumT:
        assert isinstance(self.T, irT.SumT)
        return tp.cast(irT.SumT, self._T)
 
    def match(self, *branches) -> Expr:
        if len(branches) != len(self.T.elemTs):
            raise ValueError(f"Requires lambda for each Type in Sum type {self.T}")
        branch_exprs = [make_lambda(fn, T) for fn, T in zip(branches, self.T.elemTs)]
        ret_type = branch_exprs[0].T
        if not all(e.T == ret_type for e in branch_exprs):
            raise ValueError(f"Expected all branches to have result type {ret_type}, got {", ".join([repr(e.T) for e in branch_exprs])}")
        match_node = ir.Match(self.node, ir.TupleLit(*[e.node for e in branch_exprs]))
        return tp.cast(Expr, wrap(match_node, ret_type))


class LambdaExpr(Expr, tp.Generic[TExpr, VExpr]):
    @property
    def T(self) -> irT.ArrowT:
        assert isinstance(self._T, irT.ArrowT)
        return tp.cast(irT.ArrowT, self._T)
 
    @property
    def arg_type(self) -> irT.Type_:
        return tp.cast(irT.ArrowT, self.T).argT

    @property
    def res_type(self) -> irT.Type_:
        return tp.cast(irT.ArrowT, self.T).resT

    def __repr__(self):
        return f"lambda {self.arg_type}: {self.res_type}"


def make_lambda(fn: tp.Callable[[TExpr], VExpr], paramT: irT.Type_, dom: DomainExpr=None) -> 'LambdaExpr[TExpr, VExpr]':
    if dom is None:
        dom = UnitExpr.make()
    bv_node = ir._BoundVarPlaceholder(dom.node, dom.T)
    bv_expr = tp.cast(paramT, wrap(bv_node, paramT))
    ret_expr = Expr.make(fn(bv_expr))
    lambda_node = ir._LambdaPlaceholder(bv_node, ret_expr.node, paramT)
    return tp.cast(LambdaExpr, wrap(lambda_node, irT.ArrowT(paramT, ret_expr.T)))

#def make_lambda_dict(fn: tp.Callable[[KExpr, VExpr], TExpr], keyT: irT.Type_, valT: irT.Type_) -> 'LambdaExpr[irT.TupleT[KExpr, VExpr], TExpr]':
#    bv_node = ir._BoundVarPlaceholder()
#    paramT = irT.TupleT(keyT, valT)
#    bv_expr = tp.cast(paramT, wrap(bv_node, paramT))
#    bv_k_expr = bv_expr[0]
#    bv_v_expr = bv_expr[1]
#    ret_expr = fn(bv_k_expr, bv_v_expr)
#    lambda_node = ir._LambdaPlaceholder(bv_node, ret_expr.node, paramT)
#    return tp.cast(LambdaExpr, wrap(lambda_node, irT.ArrowT(paramT, ret_expr.T)))

class DomainExpr(Expr, tp.Generic[TExpr]):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.T, irT.DomT):
            raise ValueError(f"Domain must be a DomT, got {type(self.T)}")

    @property
    def T(self) -> irT.DomT:
        assert isinstance(self._T, irT.DomT)
        return tp.cast(irT.DomT, self._T)
 
    @classmethod
    def make(cls, val):
        ...
    
    @property
    def carT(self):
        return tp.cast(irT.DomT, self.T).carT

    def restrict(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> 'DomainExpr[TExpr]':
        lambda_expr = make_lambda(pred_fun, self.carT)
        if lambda_expr.T is not irT.ArrowT(self.carT, irT.Bool):
            raise ValueError(f"pred fun must be {self.carT}")
        node = ir.Restrict(self.node, lambda_expr.node)
        return tp.cast(DomainExpr, wrap(node, self.T))

    def tabulate(self, fn: tp.Callable[[TExpr], TExpr]) -> 'FuncExpr[TExpr]':
        lambda_expr = make_lambda(fn, self.carT)
        node = ir.Tabulate(self.node, lambda_expr.node)
        T = irT.FuncT(self.T, lambda_expr.res_type)
        return tp.cast(FuncExpr[TExpr], wrap(node, T))

    def cartprod(self, *others: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(other, DomainExpr) for other in others):
            raise ValueError(f"Expected list of DomainExpr, got {others}")
        cartprod_node = ir.CartProd(self.node, *[other.node for other in others])
        #TODO check calc of enumerable and ordered
        T = irT.DomT(self.carT, irT.DomCap(finite=True, enumerable=len(others)+1, ordered=True))
        return tp.cast(DomainExpr, wrap(cartprod_node, T))

    def coproduct(self, *others: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(other, DomainExpr) for other in others):
            raise ValueError(f"Expected list of DomainExpr, got {others}")
        coprod_node = ir.DisjUnion(self.node, *[other.node for other in others])
        T = irT.DomT(self.carT, irT.DomCap(finite=True, enumerable=len(others)+1, ordered=True))
        return tp.cast(DomainExpr, wrap(coprod_node, T))

    def forall(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, self.carT)
        if lambda_expr.T is not irT.ArrowT(self.carT, irT.Bool):
            raise ValueError(f"pred fun must be {self.carT}->Bool, got {lambda_expr.T}")
        node = ir.Forall(self.node, lambda_expr.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def exists(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, self.carT)
        if lambda_expr.T is not irT.ArrowT(self.carT, irT.Bool):
            raise ValueError(f"pred fun must be {self.carT}->Bool, got {lambda_expr.T}")
        node = ir.Exists(self.node, lambda_expr.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __len__(self) -> IntExpr:
        if not self.T.cap.finite:
            raise ValueError(f"Domain {self.T} is not finite")
        node = ir.Card(self.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def __contains__(self, elem: TExpr) -> BoolExpr:
        if elem.T is not self.carT:
            raise ValueError(f"elem must be of type {self.carT}, got {elem.T}")
        node = ir.IsMember(self.node, elem.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __add__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.coproduct(other)
    
    def __mul__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.cartprod(other)

class IterDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if self.T.cap.enumerable != 1:
            raise ValueError(f"Domain must be enumerable with rank 1, got {self.T.cap.enumerable}")

    @classmethod
    def make(cls, n: IntOrExpr):
        n = IntExpr.make(n)
        node = ir.Fin(n)
        T = irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True))
        return IterDomainExpr(node, T)

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> 'ListExpr[IterDomainExpr[TExpr]]':
        size = IntExpr.make(size)
        stride = IntExpr.make(stride)
        func_node = ir.Windows(self.node, size.node, stride.node)
        T = irT.FuncT(irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True)), self.T)
        return tp.cast(ListExpr[IterDomainExpr[TExpr]], wrap(func_node, T))
 
 
class GridDomExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if self.T.cap.enumerable != 2:
            raise ValueError(f"Domain must be enumerable with rank 2, got {self.T.cap.enumerable}")

    @classmethod
    def make(cls, nR: IntOrExpr, nC: IntExpr):
        nR = IntExpr.make(nR)
        nC = IntExpr.make(nC)
        node = ir.CartProd(ir.Fin(nR.node), ir.Fin(nC.node))
        T = irT.DomT(irT.TupleT(irT.Int, irT.Int))
        return GridDomExpr(node, T)

    def tiles(self, size: tp.Tuple[IntOrExpr, IntOrExpr], stride: tp.Tuple[IntOrExpr, IntOrExpr]) -> ListExpr[GridExpr[TExpr]]:
        size_r = IntExpr.make(size[0])
        size_c = IntExpr.make(size[1])
        stride_r = IntExpr.make(stride[0])
        stride_c = IntExpr.make(stride[1])
        node = ir.Tiles(self.node, size_r.node, size_c.node, stride_r.node, stride_c.node)
        T = irT.ArrowT(irT.TupleT(irT.Int, irT.Int), self.T)
        return GridExpr(node, T)

    def dom_proj(self, idx: int) -> IterDomainExpr:
        assert self.T.cap.enumerable == 2
        node = ir.DomProj(self.node, idx)
        T = irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True))
        return tp.cast(IterDomainExpr, wrap(node, T))

    def doms(self) -> tp.Tuple[IterDomainExpr, IterDomainExpr]:
        return (self.dom_proj(0), self.dom_proj(1))

    def rows(self) -> ListExpr[IterDomainExpr]:
        return self.dom_proj(0).tabulate(lambda r: self.restrict(lambda rc: rc[0]==r))

    def cols(self) -> ListExpr[IterDomainExpr]:
        return self.dom_proj(1).tabulate(lambda c: self.restrict(lambda rc: rc[1]==c))


class FuncExpr(Expr, tp.Generic[TExpr]):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.T, irT.FuncT):
            raise ValueError(f"Func must be a FuncT, got {self.T}")

    @property
    def T(self) -> irT.FuncT:
        return tp.cast(irT.FuncT, self._T)

    @property
    def domT(self) -> irT.DomT:
        return self.T.domT

    @property
    def domain(self) -> DomainExpr:
        return tp.cast(DomainExpr, wrap(ir.DomOf(self.node), self.T.domT))

    @property
    def image(self) -> DomainExpr:
        node = ir.ImageOf(self.node)
        T = irT.DomT(self.T.resT, self.T.domT.cap)
        return tp.cast(DomainExpr, wrap(node, T))

    @property 
    def elemT(self) -> irT.Type_:
        return self.T.resT

    @property
    def carT(self) -> irT.Type_:
        return self.T.domT.carT

    def apply(self, arg: TExpr) -> TExpr:
        if arg.T is not self.carT:
            raise ValueError(f"arg must be of type {self.carT}, got {arg.T}")
        node = ir.Apply(self.node, arg.node)
        return tp.cast(TExpr, wrap(node, self.elemT))

    # Func[Dom(A) -> B] -> (B -> C) -> Func[Dom(A) -> C]
    def map(self, fn: tp.Callable[[TExpr], TExpr]) -> 'FuncExpr[TExpr]':
        return self.domain.tabulate(lambda a: fn(self.apply(a)))

    def enumerate(self) -> 'FuncExpr[TExpr]':
        return self.domain.tabulate(lambda a: (a, self.apply(a)))

    # Func[Dom(A) -> B] -> ((A,B) -> C) -> Func[Dom(A) -> C]
    def imap(self, fn: tp.Callable[[TExpr, TExpr], TExpr]) -> 'FuncExpr[TExpr]':
        return self.enumerate().map(fn)

    def forall(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        applied_fun = lambda a: pred_fun(self.apply(a))
        return self.domain.forall(applied_fun)

    def exists(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        applied_fun = lambda a: pred_fun(self.apply(a))
        return self.domain.exists(applied_fun)

    def all(self, fn: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        return self.forall(fn)

    def any(self, fn: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        return self.exists(fn)

    def distinct(self) -> BoolExpr:
        node = ir.Distinct(self.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __len__(self) -> IntExpr:
        return len(self.domain)
    
    def __contains__(self, elem: TExpr) -> BoolExpr:
        return elem in self.image

    def __call__(self, val) -> TExpr:
        return self.apply(val)

    def __getitem__(self, func: FuncExpr) -> FuncExpr:
        return func.map(lambda v: self.apply(v))

class ListExpr(FuncExpr, tp.Generic[TExpr]):
    def __post_init__(self):
        super().__post_init__()
        if self.T.domT.cap.enumerable != 1:
            raise ValueError(f"List domain must be enumerable with rank 1, got {self.T.domT}")
  
    @classmethod
    def make(cls, val: tp.List[tp.Any]) -> ListExpr[TExpr]:
        if isinstance(val, ListExpr[TExpr]):
            return tp.cast(ListExpr[TExpr], val)
        try:
            vals = [Expr.make(v) for v in val]
        except:
            raise ValueError(f"Expected List of values, got {val}")
        if len(vals) == 0:
            raise NotImplementedError("Empty lists are not supported")
        if not all(v.T == vals[0].T for v in vals):
            raise TypeError(f"Expected List of values with the same type, got {vals}")
        node = ir.ListLit(*[e.node for e in vals])
        T = irT.FuncT(irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True)), vals[0].T)
        return cls(node, T)

    @property
    def T(self) -> irT.FuncT[IterDomainExpr[TExpr], TExpr]:
        return tp.cast(irT.FuncT[IterDomainExpr[TExpr], TExpr], self._T)

    @property
    def domain(self) -> IterDomainExpr:
        return IterDomainExpr(ir.DomOf(self.node), self.domT)

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> 'ListExpr[ListExpr[TExpr]]':
        wins = self.domain.windows(size, stride) # Func[Fin(n) -> SeqDom(A)]
        wins.map(lambda win: win.tabulate(lambda i: self[i]))

    def concat(self, vals: 'ListExpr[TExpr]') -> 'ListExpr[TExpr]':
        if self.elemT is not vals.elemT:
            raise TypeError(f"Cannot concat lists with different element types: {self.elemT} and {vals.elemT}")
        if self.domain.T is not irT.DomT(irT.Int):
            raise NotImplementedError(f"Cannot concat lists with non-integer domain: {self.domain.T}")
        new_dom = IterDomainExpr.make(len(self) + len(vals))
        return new_dom.tabulate(lambda i: (i<len(self)).ite(self[i], vals[i-len(self)]))

    def __getitem__(self, idx: tp.Optional[IntOrExpr, FuncExpr]) -> TExpr:
        if isinstance(idx, FuncExpr):
            return super().__getitem__(idx)
        idx = IntExpr.make(idx)
        return self.apply(idx)

    def __len__(self) -> IntExpr:
        return len(self.domain)

    def __iter__(self) -> tp.Iterator[TExpr]:
        raise ValueError("ListExpr is not iterable at python runtime")


# Func[GridDom -> T]
class GridExpr(FuncExpr[TExpr]):
    def __post_init__(self):
        super().__post_init__()
        if self.T.domT.cap.enumerable != 2:
            raise ValueError(f"Grid domain must be enumerable with rank 2, got {self.T.domT}")

    @property
    def T(self) -> irT.FuncT:
        return tp.cast(irT.FuncT, self._T)

    @property
    def domain(self) -> GridDomExpr:
        return GridDomExpr(ir.DomOf(self.node), self.domT)

    @property
    def dims(self) -> tp.Tuple[IntExpr, IntExpr]:
        doms = self.domain.doms()
        return (len(doms[0]), len(doms[1]))

    @property
    def nR(self) -> IntExpr:
        return self.dims[0]

    @property
    def nC(self) -> IntExpr:
        return self.dims[1]

    def enumerate(self, mode: str="C") -> ListExpr[TExpr]:
        node = ir.GridEnumNode(self.nR.node, self.nC.node, mode)
        return tp.cast(ListExpr[TExpr], wrap(node, irT.ListT(self.value_type)))

    def forall(self, fn: tp.Callable[[TExpr], BoolExpr], mode: str="C") -> BoolExpr:
        lambda_expr = make_lambda(fn, self.value_type)
        node = ir.Forall(self.enumerate(mode), lambda_expr.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def rows(self) -> ListExpr[ListExpr[TExpr]]:
        return self.domain.rows().map(lambda row: row.tabulate(lambda rc: self.apply(rc)))

    def cols(self) -> ListExpr[ListExpr[TExpr]]:
        return self.domain.cols().map(lambda col: col.tabulate(lambda rc: self.apply(rc)))

    # as_grid=True means return a list of grids, as_grid=False means return a list of lists of elems
    def tiles(self, size: tp.Tuple[IntOrExpr, IntOrExpr], stride: tp.Tuple[IntOrExpr, IntOrExpr]) -> ListExpr[GridExpr[TExpr]]:
        return self.domain.tiles(size, stride).map(lambda tile_dom: tile_dom.tabulate(lambda rc: self.apply(rc)))

    def row(self, r: IntOrExpr) -> ListExpr[TExpr]:
        return self.rows()[r]

    def col(self, c: IntOrExpr) -> ListExpr[TExpr]:
        j = IntExpr.make(c)
        return self.cols()[c]

def wrap(node: ir.Node, T: irT.Type_) -> Expr:
    if T is irT.Int:
        return IntExpr(node, T)
    if T is irT.Bool:
        return BoolExpr(node, T)
    if T is irT.CellIdxT:
        return CellIdxExpr(node, T)
    if isinstance(T, irT.TupleT):
        return TupleExpr(node, T)
    if isinstance(T, irT.DomT):
        cap = tp.cast(irT.DomCap, T.cap)
        if not cap.finite:
            raise NotImplementedError("Infinite domains are not supported")
        if cap.ordered:
            match cap.enumerable:
                case 1:
                    return IterDomainExpr(node, T)
                case 2:
                    return GridDomExpr(node, T)
                case _:
                    raise NotImplementedError(f"Enumerable domains of rank {cap.enumerable} are not supported")
        else:
            return DomainExpr(node, T)
    if isinstance(T, irT.FuncT):
        cap = tp.cast(irT.DomCap, T.domT.cap)
        if not cap.finite:
            raise NotImplementedError("Infinite domains are not supported")
        if cap.ordered:
            match cap.enumerable:
                case 1:
                    return ListExpr(node, T)
                case 2:
                    return GridExpr(node, T)
                case _:
                    raise NotImplementedError(f"Enumerable domains of rank {cap.enumerable} are not supported")
    if isinstance(T, irT.ArrowT):
        return LambdaExpr(node, T)
    raise ValueError(f"Unknown type: {T}")
