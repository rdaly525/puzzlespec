from __future__ import annotations
import typing as tp

from . import ir
from dataclasses import dataclass
from .utils import _has_bv, _is_value
from ..passes.analyses.pretty_printer import pretty
from ..passes.analyses.free_vars import get_free_vars
from ..passes.analyses.type_check import type_check
from ..passes.analyses.ast_printer import print_ast
from ..passes.analyses.ssa_printer import print_ssa
from ..passes.analyses.info import count
from ..utils import BoolLat
import inspect

@dataclass
class Expr:
    node: ir.Node

    def __repr__(self):
        return pretty(self.node)

    @property
    def _freevars(self):
        return get_free_vars(self.node)

    def _print_ast(self):
        print(print_ast(self.node))

    def _print_ssa(self):
        print_ssa(self.node)

    def _size(self, unique=True):
        return count(self.node, unique)

    @property
    def obl(self) -> tp.Optional[BoolExpr]:
        raw = self.node.obl
        if raw is None:
            return None
        return BoolExpr(raw)

class TExpr(Expr):
    node: ir.Type

    def __post_init__(self):
        assert isinstance(self.node, ir.Type)
        if self.is_ref:
            if self.ref_dom.T.carT != self:
                raise ValueError()

    def __repr__(self):
        return pretty(self.node)

    # Strip named children (ref, view, obl) to get the raw base type
    @property
    def _node(self):
        return self.node.rawT

    @property
    def is_ref(self):
        return self.node.ref is not None

    @property
    def ref_dom(self) -> tp.Optional[DomainExpr]:
        if self.is_ref:
            return wrap(self.node.ref)
        return None

    @property
    def has_view(self):
        return self.node.view is not None

    def forget_view(self):
        if self.has_view:
            return wrapT(self.node.replace(*self.node.children, ref=self.node.ref, view=None, obl=self.node.obl))
        return self

    @property
    def view(self) -> tp.Optional[ViewExpr]:
        if self.has_view:
            return wrap(self.node.view)
        return None

    def with_view(self, view: ViewExpr):
        assert not self.has_view
        node = self.node.replace(*self.node.children, ref=self.node.ref, view=view.node, obl=self.node.obl)
        return wrapT(node)

    @property
    def U(self) -> DomainExpr:
        if self.is_ref:
            return self.ref_dom
        return wrap(ir.Universe(ir.DomT(self.node)))

    @property
    def DomT(self) -> DomainType:
        return wrapT(ir.DomT(self.node))

    # Create a PiType
    def to(self, T: TExpr):
        piT = ir.PiTHOAS(self.node, T.node, bv_name="_")
        return wrapT(piT)

    def refine(self, dom: DomainExpr| tp.Callable) -> TExpr:
        if not isinstance(dom, DomainExpr):
            assert isinstance(dom, tp.Callable)
            dom = self.U.restrict(dom)
        if self.is_ref:
            new_dom = dom & self.ref_dom
        else:
            new_dom = dom
        return new_dom.as_refT()

    def guard(self, p: BoolExpr):
        p = BoolExpr.make(p)
        new_obl = (self.obl & p).node if self.obl is not None else p.node
        node = self.node.replace(*self.node.children, ref=self.node.ref, view=self.node.view, obl=new_obl)
        return wrapT(node)

    def choose(self, plam: tp.Callable) -> VExpr:
        lam = FuncExpr.make(self, plam)
        node = ir.Choose(self.node, lam.node)
        return wrap(node)

    def simplify(self) -> TExpr:
        from ..passes.utils import simplify
        return type(self)(simplify(self.node, hoas=True, verbose=0))

    def _bound_var(self, name=None):
        new_bv = ir.BoundVarHOAS(self.node, False, name)
        return wrap(new_bv)

    def __eq__(self, other):
        if isinstance(other, TExpr):
            return self._rawT == other._rawT
        return False

    @property
    def _rawT(self) -> ir.Node:
        return self.node.rawT


class UnitType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.UnitT):
            raise ValueError(f"Expected UnitType, got {self.node}")
Unit = UnitType(ir.UnitT())

class BoolType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.BoolT):
            raise ValueError(f"Expected BoolType, got {self.node}")
Bool = BoolType(ir.BoolT())

class IntType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.IntT):
            raise ValueError(f"Expected IntType, got {self.node}")
Int = IntType(ir.IntT())

class EnumType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.EnumT):
            raise ValueError(f"Expected EnumType, got {self.node}")

class TupleType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.TupleT):
            raise ValueError(f"Expected TupleType, got {self.node}")

    def elemT(self, i: int) -> TExpr:
        if not isinstance(i, int):
            raise ValueError("Tuple index must be concrete (python) int")
        return wrapT(self._node[i])

    def __getitem__(self, i: int):
        return self.elemT(i)

    def elemTs(self) -> tp.Tuple[TExpr]:
        return tuple(self.elemT(i) for i in range(len(self)))

    def __len__(self):
        return len(self._node)


class SumType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.SumT):
            raise ValueError(f"Expected SumType, got {self.node}")

    def make_sum(self, val: tp.Any) -> SumExpr:
        return SumExpr.make(self, val)

    def elemT(self, i: int) -> TExpr:
        if not isinstance(i, int):
            raise ValueError("Tuple index must be concrete (python) int")
        return wrapT(self._node[i])

    def __len__(self):
        return len(self._node)

    @property
    def elemTs(self) -> tp.Tuple[TExpr]:
        return tuple(self.elemT(i) for i in range(len(self)))

    def __getitem__(self, i: int):
        return self.elemT(i)

class DomainType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.DomT):
            raise ValueError(f"Expected DomainType, got {type(self.node)}")

    @property
    def carT(self) -> TExpr:
        return wrapT(self._node.carT)

    @property
    def _caps(self) -> tp.Set[ir.DomainCapability]:
        if self.ref_dom is None:
            return set()
        if isinstance(self.ref_dom.node, ir.DomainCapability):
            return set((self.ref_dom.node,))
        if isinstance(self.ref_dom.node, ir.Intersection):
            caps = set()
            for dom in self.ref_dom.node.children:
                if isinstance(dom, ir.DomainCapability):
                    caps.add(dom)
            return caps
        else:
            raise set()

class FuncType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.PiTHOAS):
            raise ValueError(f"Expected PiT, got {self.node}")
    
    @property
    def argT(self) -> TExpr:
        return wrapT(self.node.argT)

    def resT(self, arg: VExpr):
        from ..passes.transforms.beta_reduction import applyT
        rT_node = applyT(self.node, arg.node)
        rT = wrapT(rT_node)
        return rT

    @property
    def _raw_resT(self):
        return wrapT(self._rawT.resT)

    #@property
    #def inj_known(self):
    #    return self.node.inj

    @property
    def domain(self) -> DomainExpr:
        if self.argT.is_ref:
            return self.argT.ref_dom
        else:
            return self.argT.U

class ViewType(TExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.node, ir.ViewT):
            raise ValueError(f"Expected ViewT, got {self.node}")

    def make_expr(self, node: ir.Node) -> ViewExpr:
        return self.node.make_ast(node)
    
def wrapT(T: ir.Type):
    assert isinstance(T, ir.Type)
    _T = T.rawT
    if isinstance(_T, ir.ViewT):
        return ViewType(T)
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
        case ir.DomT:
            domT = DomainType(T)
            return domT
        case ir.PiTHOAS:
            return FuncType(T)
        case ir.ViewT:
            return ViewType(T)
        case _:
            raise ValueError(f"Expected Type, got {T}")

class VExprMakeError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class VExpr(Expr):
    def __post_init__(self):
        if not isinstance(self.node, ir.Value):
            raise ValueError(f"Expr must be an ir.Value, got {self.node}")
        #self.type_check()

    @property
    def T(self) -> TExpr:
        return wrapT(self.node.T)

    # raw T, no refinement
    @property
    def _T(self) -> TExpr:
        return wrapT(self.T._node)
    
    # raw node, no obligations
    @property
    def _node(self) -> ir.Node:
        return self.node

    @classmethod
    def make(cls, val: tp.Any) -> VExpr:
        if isinstance(val, VExpr):
            if type(val)==VExpr:
                raise ValueError("Raw VExpr found!!", val)
            return val
        if isinstance(val, bool):
            return BoolExpr.make(val)
        if isinstance(val, int):
            return IntExpr.make(val)
        if isinstance(val, tp.Tuple):
            return TupleExpr.make(val)
        if isinstance(val, set):
            return DomainExpr.make(val)
        raise VExprMakeError(f"Cannot make VExpr from {val}")

    def __eq__(self, other):
        other = VExpr.make(other)
        if self.T != other.T:
            raise ValueError(f"Cannot compare {self.T} and {other.T}")
        return BoolExpr(ir.Eq(ir.BoolT(), self.node, other.node))
        
    def __ne__(self, other):
        return ~(self == other)



    def refine(self, v: DomainExpr | tp.Callable):
        if isinstance(v, DomainExpr):
            dom = v
        else:
            dom = self.T.U.restrict(v)
        new_T = self.T.refine(dom)
        new_node = self.node.replace(*self.node.children, T=new_T.node, obl=self.node.obl)
        return type(self)(new_node)

    def guard(self, p: BoolExpr):
        p = BoolExpr.make(p)
        new_obl = (self.obl & p).node if self.obl is not None else p.node
        node = self.node.replace(*self.node.children, T=self.node.T, obl=new_obl)
        return wrap(node)

    @property
    def view(self):
        return self.T.view

    def with_view(self, view: ViewExpr):
        assert isinstance(view, ViewExpr)
        T = self.T.with_view(view)
        node = self.node.replace(*self.node.children, T=T.node, obl=self.node.obl)
        return wrap(node)

    def forget_view(self):
        if self.T.has_view:
            newT = self.T.forget_view().node
            node = self.node.replace(*self.node.children, T=newT, obl=self.node.obl)
            return wrap(node)
        return self

    @property
    def singleton(self):
        T = self.T.DomT
        cap_s = wrap(ir.SqueezableDomain(T.DomT.node))
        cap_e = wrap(ir.EnumerableDomain(T.DomT.node))
        node = ir.Singleton(T.refine(cap_s & cap_e).node, self.node)
        return wrap(node)

    def simplify(self, verbose=0, strip_guards=False, max_iter=5) -> tp.Self:
        from ..passes.utils import simplify
        simp = simplify(self.node, hoas=True, strip_guards=strip_guards, verbose=verbose, max_iter=max_iter)
        return wrap(simp)

    def type_check(self) -> ir.Type:
        return type_check(self.node)


class UnitExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, UnitType):
            raise ValueError(f"Expected UnitType, got {self._T}")

    @property
    def T(self) -> UnitType:
        return tp.cast(UnitType, super().T)
    
    @classmethod
    def make(cls) -> UnitExpr:
        node = ir.Unit(ir.UnitT())
        return UnitExpr(node)

class BoolExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, BoolType):
            raise ValueError(f"Expected BoolType, got {self._T}")

    @property
    def T(self) -> BoolType:
        return tp.cast(BoolType, super().T)

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
        node = ir.Conj(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    __rand__ = __and__

    def __or__(self, other: BoolExpr) -> BoolExpr:
        node = ir.Disj(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    __ror__ = __or__

    def ite(self, t: VExpr, f: VExpr) -> VExpr:
        t, f = VExpr.make(t), VExpr.make(f)
        node = ir.Ite(t.T._node, self.node, t.node, f.node)
        return type(t)(node)

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

class IntExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, IntType):
            raise ValueError(f"Expected IntType, got {self._T}")

    @property
    def T(self) -> IntType:
        return tp.cast(IntType, super().T)

    @classmethod
    def make(cls, val: tp.Any) -> IntExpr:
        if isinstance(val, IntExpr):
            return tp.cast(IntExpr, val)
        if isinstance(val, int):
            node = ir.Lit(ir.IntT(), val)
            return IntExpr(node)
        raise ValueError(f"Expected Int expression. Got {val}")

    def fin(self):
        T = Int.DomT
        dom: DomainExpr = wrap(ir.Fin(T.node, self.node))
        return dom

    def __add__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Sum(ir.IntT(), self.node, other.node)
        return IntExpr(node)

    def __sub__(self, other: IntOrExpr) -> IntExpr:
        return self + (-other)

    def __neg__(self) -> IntExpr:
        node = ir.Neg(ir.IntT(), self.node)
        return IntExpr(node)

    def __abs__(self) -> IntExpr:
        node = ir.Abs(ir.IntT(), self.node)
        return IntExpr(node)

    def __mul__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Prod(ir.IntT(), self.node, other.node)
        return IntExpr(node)

    def __pow__(self, other: int):
        other = IntExpr.make(other)
        from .ast_nd import fin
        node = ir.ProdReduce(ir.IntT(), fin(other).map(lambda i: self).node)
        return IntExpr(node)

    def __floordiv__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.FloorDiv(ir.IntT(), self.node, other.node)
        #return IntExpr(node).guard(other!=0)
        return IntExpr(node)

    def ceildiv(self, other: IntOrExpr):
        return -(-self//other)

    #def __truediv__(self, other: IntOrExpr) -> IntExpr:
    #    return Int.choose(lambda v: v*other==self)

    def __truediv__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.TrueDiv(ir.IntT(), self.node, other.node)
        #return IntExpr(node)
        return IntExpr(node).guard(other!=0)

    def __mod__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mod(ir.IntT(), self.node, other.node)
        #return IntExpr(node).guard(other !=0)
        return IntExpr(node)

    def __gt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        return other < self

    def __ge__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        return other <= self

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

class EnumExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, EnumType):
            raise ValueError(f"Expected EnumType, got {self._T}")
    
    @property
    def T(self) -> EnumType:
        return tp.cast(EnumType, super().T)

    @classmethod
    def make(cls, val) -> EnumExpr:
        if isinstance(val, EnumExpr):
            return val
        raise NotImplementedError(f"cannot cast {val} to EnumExpr")

IntOrExpr = tp.Union[int, IntExpr]
BoolOrExpr = tp.Union[bool, BoolExpr, VExpr]
EnumOrExpr = tp.Union[str, EnumExpr, VExpr]


class TupleExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, TupleType):
            raise ValueError(f"Expected TupleType, got {self._T}")

    @property
    def T(self) -> TupleType:
        return tp.cast(TupleType, super().T)
   
    @classmethod
    def make(cls, vals: tp.Tuple[tp.Any, ...]=None) -> TupleExpr:
        if vals is None:
            vals = ()
        if isinstance(vals, TupleExpr):
            return vals
        if isinstance(vals, tp.Tuple):
            vals = tuple(VExpr.make(v) for v in vals)
            node = ir.TupleLit(ir.TupleT(*[e.T._node for e in vals]), *[e.node for e in vals])
            return TupleExpr(node)
        raise VExprMakeError(f"Cannot make TupleExpr from {vals}")

    @classmethod
    def empty(cls):
        return cls.make()

    def __getitem__(self, idx: int|slice) -> VExpr:
        if isinstance(idx, int):
            if idx < 0 or idx >= len(self):
                raise IndexError(f"Tuple index out of range: {idx}")
            node = ir.Proj(self.T[idx].node, self.node, idx)
            return wrap(node)
        elif isinstance(idx, slice):
            lo, hi, step = idx.start, idx.stop, idx.step
            if lo is None:
                lo = 0
            if hi is None:
                hi = len(self)
            if step is None:
                step = 1
            return tuple(self[i] for i in range(lo, hi, step))
        else:
            raise ValueError("Cannot dynamically index tuples")

    def __len__(self) -> int:
        return len(self._T)

    # Nice unpacking
    def __iter__(self) -> None:
        for i in range(len(self)):
            yield self[i]

class SumExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, SumType):
            raise ValueError(f"Expected SumType, got {self._T}")

    @classmethod
    def make(cls, T: SumType, val: tp.Any):
        val = VExpr.make(val)
        idx = None
        for i, eT in enumerate(T.elemTs):
            if type(val.T)==type(eT):
                idx = i
        if idx is None:
            raise ValueError(f"Cannot make SumExpr from {val} with type {T}")
        node = ir.Inj(T._node, val.node, idx=idx)
        return SumExpr(node)

    @property
    def T(self) -> SumType:
        return tp.cast(SumType, super().T)
 
    def match(self, *branches: tp.Callable) -> VExpr:
        if len(branches) != len(self.T):
            raise ValueError(f"Need a branch for each element of the sum type, got {len(branches)} branches for {len(self.T)} elements")
        branch_exprs = []
        for lam_fn, T in zip(branches, self.T.elemTs):
            lam_expr = FuncExpr.make(T, lam_fn)
            branch_exprs.append(lam_expr)
        lamTs = [e.T for e in branch_exprs]
        bv = lamTs[0].argT._bound_var()
        match_T = lamTs[0].resT(bv)
        if _has_bv(bv, match_T.node):
            raise NotImplementedError("Dependently typed match")
        match_node = ir.Match(match_T._node, self.node, *[e.node for e in branch_exprs])
        return wrap(match_node)

def cartprod(*doms: DomainExpr) -> DomainExpr:
    if not all(isinstance(dom, DomainExpr) for dom in doms):
        raise ValueError(f"Expected all DomainExpr, got {doms}")
    if all(dom.T.has_view for dom in doms):
        from . import ast_nd
        return ast_nd.nd_cartprod(*doms)
    carT = ir.TupleT(*[dom.T.carT._node for dom in doms])
    dom_nodes = tuple(dom.node for dom in doms)
    T = ir.DomT(carT)
    cartprod_node = ir.CartProd(T, *dom_nodes)
    return wrap(cartprod_node)

def coproduct(*doms: DomainExpr) -> DomainExpr:
    if not all(isinstance(other, DomainExpr) for other in doms):
        raise ValueError(f"Expected list of DomainExpr, got {doms}")
    carT = ir.SumT(*[dom.T.carT._node for dom in doms])
    T = ir.DomT(carT)
    coprod_node = ir.DisjUnion(T, *[dom.node for dom in doms])
    return wrap(coprod_node)


class DomainExpr(VExpr):
    def __init__(self, node: ir.Value):
        super().__init__(node)

    @classmethod
    def make(cls, val: tp.Any) -> DomainExpr:
        if isinstance(val, DomainExpr):
            return val
        if isinstance(val, set):
            vals = [Expr.make(v) for v in val]
            if not all(isinstance(v.T, vals[0].T) for v in vals):
                raise ValueError(f"Cannot make DomainExpr from {val}")
            return DomainExpr(ir.DomLit(ir.DomT(vals[0].T._node), *vals))
        raise ValueError(f"Cannot make DomainExpr from {val}")

    @property
    def T(self) -> DomainType:
        return tp.cast(DomainType, super().T)

    def as_refT(self) -> TExpr:
        baseT = self.T.carT.node
        return wrapT(baseT.replace(*baseT.children, ref=self.node, view=baseT.view, obl=baseT.obl))

    def as_nd(self) -> DomainExpr:
        if self.T.has_view:
            return self
        from .ast_nd import fin
        if isinstance(self.node, ir.Fin):
            return fin(self.size)
        else:
            raise NotImplementedError()

    @property
    def size(self) -> IntExpr:
        node = ir.Card(ir.IntT(), self.node)
        return IntExpr(node)

    @property
    def unique_elem(self) -> bool:
        # TODO add Guard that size == 1
        return wrap(ir.Unique(self.T.carT._node, self.node))

    def restrict(self, pred_fun: tp.Callable) -> DomainExpr:
        func_expr = self.map(pred_fun)
        if func_expr.T.argT != self.T.carT or func_expr.T._raw_resT != Bool:
            raise ValueError(f"Cannot restrict {self.T} with func typed: {func_expr.T}")
        node = ir.Restrict(self.T._node, func_expr.node)
        d = wrap(node)
        return d

    def dom_proj(self, i: int) -> DomainExpr:
        if not (isinstance(self.T.carT, TupleType) and i in range(len(self.T.carT))):
            raise ValueError(f"Cannot project {i} into value with type {self.T}")
        node = ir.DomProj(self.T.carT[i].DomT.node, self.node, i)
        return wrap(node)

    def contains(self, elem: VExpr):
        elem = VExpr.make(elem)
        node = ir.IsMember(ir.BoolT(), self.node, elem.node)
        return BoolExpr(node)

    def __add__(self, other: 'DomainExpr') -> 'DomainExpr':
        return coproduct(self, other)
    
    def __mul__(self, other: 'DomainExpr') -> 'DomainExpr':
        return cartprod(self, other)

    def subset_of(self, other: DomainExpr) -> BoolExpr:
        other = DomainExpr.make(other)
        node = ir.Subset(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def proper_subset_of(self, other: DomainExpr) -> BoolExpr:
        other = DomainExpr.make(other)
        node = ir.ProperSubset(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __gt__(self, other: DomainExpr) -> BoolExpr:
        return other.proper_subset_of(self)

    def __ge__(self, other: DomainExpr) -> BoolExpr:
        return other.subset_of(self)

    def __lt__(self, other: DomainExpr) -> BoolExpr:
        return self.proper_subset_of(other)

    def __le__(self, other: DomainExpr) -> BoolExpr:
        return self.subset_of(other)

    def union(self, other: DomainExpr) -> DomainExpr:
        if self.T.carT != other.T.carT:
            raise ValueError(f"Cannot union domains with different carrier types: {self.T.carT} != {other.T.carT}")
        node = ir.Union(self.T._node, self.node, other.node)
        return DomainExpr(node)

    def intersect(self, *others: DomainExpr) -> DomainExpr:
        for other in others:
            if self.T.carT != other.T.carT:
                raise ValueError(f"Cannot intersect domains with different carrier types: {self.T.carT} != {other.T.carT}")
        node = ir.Intersection(self.T._node, self.node, *(other.node for other in others))
        return DomainExpr(node)

    def __and__(self, other: DomainExpr) -> DomainExpr:
        return self.intersect(other)

    def __or__(self, other: DomainExpr) -> DomainExpr:
        return self.union(other)

    def __contains__(self, elem: VExpr) -> BoolExpr:
        raise ValueError("Cannot use 'in'. Use dom.contains(val). Blame python for not being able to do this")
    
    #def gather(self, dom: DomainExpr) -> DomainExpr:
    #    if dom.T != self.T:
    #        raise ValueError()
    #    assert isinstance(dom, DomainExpr)
    #    return dom
    #    #return dom & self
    #    #return dom.guard(dom <= self)

    #def __getitem__(self, dom: DomainExpr) -> DomainExpr:
    #    if not isinstance(dom, DomainExpr):
    #        raise ValueError(f"Expected domain, got {dom}")
    #    if dom.T != self.T:
    #        raise ValueError()
    #    if not isinstance(dom, DomainExpr):
    #        raise ValueError()
    #    return dom

    def _bound_var(self):
        bv = self.T.carT._bound_var()
        return bv.refine(self)

    def __iter__(self):
        yield self._bound_var()

    def map(self, fn: tp.Callable | FuncExpr, inj=False) -> FuncExpr:
        if isinstance(fn, FuncExpr):
            return FuncExpr.make(self, lambda v: fn(v), inj)
        else:
            return FuncExpr.make(self, fn, inj)

    @property
    def identity(self):
        return self.map(lambda i: i)

    def forall(self, pred_fun: tp.Callable) -> BoolExpr:
        func_expr = self.map(pred_fun)
        node = ir.Forall(ir.BoolT(), func_expr.node)
        return BoolExpr(node)

    def exists(self, pred_fun: tp.Callable) -> BoolExpr:
        func_expr = self.map(pred_fun)
        node = ir.Exists(ir.BoolT(), func_expr.node)
        return BoolExpr(node)

    def empty_func(self) -> EmptyFuncExpr:
        return EmptyFuncExpr(self)

        
def _num_fn_args(fn: tp.Callable):
    # Calculate number of non-default args
    sig = inspect.signature(fn)
    fn_args = sum(v.default is inspect.Parameter.empty for v in sig.parameters.values())
    return fn_args

def _call_fn(fn: tp.Callable, expr: VExpr) -> VExpr:
    fn_args = _num_fn_args(fn)
    if fn_args==1:
        ret = fn(expr)
    elif isinstance(expr.T, TupleType) and len(expr.T)==fn_args:
        args = [expr[i] for i in range(fn_args)]
        ret = fn(*args)
    else:
        raise ValueError(f"Function has wrong number of arguments for sort. Expected {fn_args}, got {len(expr.T)}")
    return VExpr.make(ret)

def _make_lambda(argT: TExpr, body: VExpr, bv_name, inj=False) -> FuncExpr:
    assert isinstance(argT, TExpr)
    retT = body.T.node
    lamT = ir.PiTHOAS(argT.node, retT, bv_name=bv_name)
    lambda_node = ir.LambdaHOAS(lamT, body.node, bv_name=bv_name)
    if inj:
        lambda_node._metadata['inj'] = BoolLat.T
    return lambda_node

class FuncExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._T, FuncType):
            raise ValueError(f"Expected FuncExpr, got {self.T}")
    
    @classmethod
    def make(cls, TorDom: TExpr|DomainExpr, fn: tp.Callable, inj=False) -> FuncExpr:
        if isinstance(TorDom, TExpr):
            argT = TorDom
        elif isinstance(TorDom, DomainExpr):
            argT = TorDom.as_refT()
        bv = TorDom._bound_var()
        assert isinstance(bv.node, ir.BoundVarHOAS)
        assert not bv.node.closed
        body_expr = _call_fn(fn, bv)
        bv.node.closed=True
        #TODO if inj, add a guard with injective proof
        return wrap(_make_lambda(argT, body_expr, bv.node.name, inj))

    @property
    def T(self) -> FuncType:
        return tp.cast(FuncType, super().T)

    @property
    def domain(self) -> DomainExpr:
        return self.T.domain

    @property
    def known_inj(self) -> bool:
        inj = self.node._metadata.get('inj', None)
        if inj is not None:
            return inj == BoolLat.T
        # TODO maybe try to infer?
        return False

    @property
    def image(self) -> DomainExpr:
        resT = self.T._raw_resT
        imgT = resT.DomT
        node = ir.Image(imgT.node, self.node)
        return wrap(node)

    def apply(self, arg: VExpr) -> VExpr:
        arg = VExpr.make(arg)
        if self.T.argT != arg.T:
            raise ValueError(f"Cannot apply a {arg.T} to {self._T.argT}")
        node = ir.Apply(
            T = self.T.resT(arg).node,
            func = self.node,
            arg = arg.node
        )
        if arg.T.ref_dom is not None and arg.T.ref_dom.node==self.domain.node:
            return wrap(node)
        return wrap(node).guard(self.domain.contains(arg))
        #return wrap(node)

    # Func[Dom(A) -> B] -> (B -> C) -> Func[Dom(A) -> C]
    def map(self, fn: tp.Callable) -> FuncExpr:
        return self.domain.map(lambda a: _call_fn(fn, self.apply(a)))


    #def compose(self, other: FuncExpr):
    #    if not isinstance(other, FuncExpr):
    #        raise ValueError(f"Expected LambdaExpr, got {other}")
    #    if self.T.argT != other.T._raw_resT:
    #        raise ValueError(f"Composition {self.T} @ {other.T} is not valid")
    #    def lam(a: VExpr):
    #        b = other.apply(a)
    #        c = self.apply(b)
    #        return c
    #    inj = self.known_inj and other.known_inj
    #    return FuncExpr.make(other.T.argT, lam, inj)

    def __matmul__(self, other: FuncExpr):
        return compose(self, other)

    def __mul__(self, other: FuncExpr):
        return funcprod(self, other)
    
    # Func[Dom(A) -> B] -> Func[Dom(A) -> (A, B)]
    def enumerate(self) -> FuncExpr:
        return self.domain.map(lambda a: TupleExpr.make((a, self.apply(a))))

    # Func[Dom(A) -> B] -> ((A,B) -> C) -> Func[Dom(A) -> C]
    def imap(self, fn: tp.Callable) -> 'FuncExpr':
        return self.enumerate().map(fn)

    def forall(self, pred_fun: tp.Callable=None) -> BoolExpr:
        if pred_fun is None:
            return self.domain.forall(lambda a: self.apply(a))
        else:
            return self.map(pred_fun).forall()

    def exists(self, pred_fun: tp.Callable=None) -> BoolExpr:
        if pred_fun is None:
            return self.domain.forall(lambda a: self.apply(a))
        else:
            return self.map(pred_fun).forall()

    def size(self) -> IntExpr:
        return self.domain.size

    def sum(self) -> IntExpr:
        return IntExpr(ir.SumReduce(ir.IntT(), self.node))
    
    def __call__(self, *vals: tp.Any) -> VExpr:
        if len(vals) ==1:
            val = vals[0]
        elif len(vals) > 1:
            val = VExpr.make(tuple(vals))
        else:
            raise ValueError()
        return self.apply(val)
    
    def gather(self, dom: DomainExpr):
        return dom.map(lambda elem: self.apply(elem))

    # Basically a 'gather'
    def __getitem__(self, dom: DomainExpr) -> FuncExpr:
        if not isinstance(dom, DomainExpr):
            raise ValueError(f"Can only index into funcs with a domain (i.e., a gather).\nFunc: {self}\n Got: {dom}")
        return self.gather(dom)

# TN-1 -> TN, ..., T1 -> T2, T0 -> T1
def compose(*lams: FuncExpr, guard=False):
    if not all(isinstance(lam, FuncExpr) for lam in lams):
        raise ValueError(f"Expected FuncExpr, got {lams}")
    if len(lams) == 1:
        return lams[0]
    if len(lams)==0:
        raise ValueError("Must provide at least one function")

    # Check compatibility of all underlying types
    for f, g in zip(lams[:-1], lams[1:]):
        if f.T.argT != g.T._raw_resT:
            raise ValueError(f"Composition {f.T} @ {g.T} is not valid")
    inj = all(lam.known_inj for lam in lams)

    # Construct obligation guard (B -> C) -> (A -> B') => (B' ⊆ B)
    guards = []
    for f, g in zip(lams[:-1], lams[1:]):
        guards.append(g.image <= f.domain)

    # Construct new Pi type for composition
    def compose_lam(arg):
        for lam in reversed(lams):
            arg = lam(arg)
        return arg
    _lam = FuncExpr.make(lams[-1].domain, compose_lam, inj=inj)
    node = ir.Compose(
        _lam.T.node,
        *(lam.node for lam in lams)
    )
    lam = wrap(node)
    if guard:
        from ...libs import std
        return lam.guard(std.all(guards))
    return lam

class EmptyFuncExpr(FuncExpr):
    def __init__(self, dom: DomainExpr):
        self.empty = False
        super().__init__(dom.identity.node)
        self.dom = dom
    
    def __post_init__(self):
        return super().__post_init__()
        self.empty = True

    @property
    def T(self) -> FuncType:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().T

    def __setitem__(self, k, val):
        val = VExpr.make(val)
        if (isinstance(k, VExpr) and isinstance(k.node, ir.BoundVarHOAS)):
            # verify it came from correct dom
            T = k.node.T
            if T.ref is not None and T.ref._key == self.dom.node._key:
                lam_e = _make_lambda(k, val)
                funcT = ir.FuncT(self.dom.node, lam_e.T._node)
                func_node = ir.Map(funcT, self.dom.node, lam_e.node)
                self.node = func_node
                self.empty = False
                return
        raise ValueError(f"Must only set with iterator var produced from {self.dom}")


    @property
    def domain(self) -> DomainExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().domain

    @property
    def image(self) -> DomainExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().image

    def apply(self, arg: VExpr) -> VExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().apply(arg)

    # Func[Dom(A) -> B] -> (B -> C) -> Func[Dom(A) -> C]
    def map(self, fn: tp.Callable) -> FuncExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().map(fn)

    # Func[Dom(A) -> B] -> Func[Dom(A) -> (A, B)]
    def enumerate(self) -> FuncExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().enumerate()

    # Func[Dom(A) -> B] -> ((A,B) -> C) -> Func[Dom(A) -> C]
    def imap(self, fn: tp.Callable) -> 'FuncExpr':
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().imap(fn)

    def forall(self, pred_fun: tp.Callable=None) -> BoolExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().forall(pred_fun)

    def exists(self, pred_fun: tp.Callable=None) -> BoolExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().exists(pred_fun)

    def size(self) -> IntExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().size()

    def sum(self) -> IntExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().sum()
    
    def __contains__(self, elem: VExpr) -> BoolExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().__contains__(elem)

    def __call__(self, val: VExpr) -> VExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().__call__(val)
    
    def gather(self, dom: DomainExpr):
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().gather(dom)

    # Basically a 'gather'
    def __getitem__(self, dom: DomainExpr) -> FuncExpr:
        if self.empty:
            raise ValueError("Must set EmptyFunc before using")
        return super().__getitem__(dom)

# product of functions
# (A -> B) -> (C -> D) -> AxC -> BxD
def funcprod(*funcs: FuncExpr) -> FuncExpr:
    if not all(isinstance(f, FuncExpr) for f in funcs):
        raise ValueError(f"Expected FuncExpr, got {funcs}")
    if len(funcs) == 1:
        return funcs[0]
    new_dom = cartprod(*[f.domain for f in funcs])
    def prod(nidx: TupleExpr):
        results = [func[nidx[i]] for i, func in enumerate(funcs)]
        return TupleExpr.make(results)
    inj = all(f.known_inj for f in funcs)
    return FuncExpr.make(new_dom, prod, inj)

class ViewExpr(VExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.T, ViewType):
            raise ValueError(f"Expected ViewType, got {self.T}")
 
    def promote(self, node: ir.Node):
        raise NotImplementedError()

def wrap(node: ir.Node) -> VExpr:
    T = wrapT(node.T)
    if T.has_view:
        return T.view.promote(node)
    # Base theory types
    if isinstance(T, UnitType):
        return UnitExpr(node)
    if isinstance(T, BoolType):
        return BoolExpr(node)
    if isinstance(T, IntType):
        return IntExpr(node)
    if isinstance(T, EnumType):
        return EnumExpr(node)
    if isinstance(T, TupleType):
        return TupleExpr(node)
    if isinstance(T, SumType):
        return SumExpr(node)
    if isinstance(T, ViewType):
        return T.make_expr(node)
    if isinstance(T, DomainType):
        return DomainExpr(node)
    if isinstance(T, FuncType):
        f = FuncExpr(node)
        if f.domain.T.has_view:
            return f.domain.T.view.promote_func(node)
        return f

    raise NotImplementedError(f"Cannot cast node {node} with T={T} to VExpr")
