from __future__ import annotations
import typing as tp
from . import ir
from dataclasses import dataclass
from enum import Enum as _Enum
from .utils import _get_T, _is_kind, _is_same_kind, _simplify_T
class ExprMakeError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

@dataclass
class Expr:
    node: ir.Value

    def __post_init__(self):
        if not isinstance(self.node, ir.Value):
            raise ValueError("Expr must be an ir.Value, got {self.node}")

    @property
    def _T(self) -> ir.Type:
        return self.node.T
    
    @property
    def raw_T(self) -> ir.Type:
        return _get_T(self.T)


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
        

class UnitExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_UnitExpr(self.node):
            raise ValueError(f"Expected UnitExpr, got {self}")

    @property
    def T(self) -> ir.UnitT:
        return tp.cast(ir.UnitT, self._T)
    
    @staticmethod
    def make(cls) -> UnitExpr:
        return UnitExpr(ir.Unit())

class BoolExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_BoolExpr(self.node):
            raise ValueError(f"Expected BoolExpr, got {self}")

    @property
    def T(self) -> ir.BoolT:
        return tp.cast(ir.BoolT, self._T)

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

    def __eq__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Eq(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)
    
    def __ne__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Not(ir.Eq(ir.BoolT(), self.node, other.node))
        return BoolExpr(node)

    def ite(self, t: Expr, f: Expr) -> Expr:
        t, f = Expr.make(t), Expr.make(f)
        node = ir.Ite(t.T, self.node, t.node, f.node)
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

    @property
    def T(self) -> ir.IntT:
        return tp.cast(ir.IntT, self._T)

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
        return (self >= 0).ite(self, -self)

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

    def __eq__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Eq(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __ne__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        return ~ir.Eq(ir.BoolT(), self.node, other.node)\

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
    
    @property
    def T(self) -> ir.EnumT:
        return tp.cast(ir.EnumT, self._T)

    @classmethod
    def make(cls, val) -> EnumExpr:
        if isinstance(val, EnumExpr):
            return val
        raise NotImplementedError(f"cannot cast {val} to EnumExpr")

    def __eq__(self, other: Expr) -> BoolExpr:
        other = EnumExpr.make(other)
        node = ir.Eq(ir.BoolT(), self.node, other.node)
        return BoolExpr(node)

    def __ne__(self, other: Expr) -> BoolExpr:
        other = EnumExpr.make(other)
        return ~ir.Eq(ir.BoolT(), self.node, other.node)

IntOrExpr = tp.Union[int, IntExpr, Expr]
BoolOrExpr = tp.Union[bool, BoolExpr, Expr]
EnumOrExpr = tp.Union[str, EnumExpr, Expr]


class TupleExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_TupleExpr(self.node):
            raise ValueError(f"Expected TupleExpr, got {self}")

    @property
    def T(self) -> ir.TupleT:
        if not isinstance(self._T, ir.TupleT):
            raise ValueError()
        return tp.cast(ir.TupleT, self._T)
   
    @classmethod
    def make(cls, vals: tp.Tuple[tp.Any, ...]=None) -> TupleExpr:
        if vals is None:
            vals = ()
        if isinstance(vals, TupleExpr):
            return vals
        try:
            vals = tuple(Expr.make(v) for v in vals)
            node = ir.TupleLit(ir.TupleT(*[e.T for e in vals]), *[e.node for e in vals])
            return TupleExpr(node)
        except ExprMakeError as e:
            raise e

    @classmethod
    def empty(cls):
        return cls.make()

    def __getitem__(self, idx: int) -> Expr:
        if idx < 0 or idx >= len(self):
            raise IndexError(f"Tuple index out of range: {idx}")
        node = ir.Proj(self.T[idx], self.node, idx)
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

    @property
    def T(self) -> ir.SumT:
        assert _is_kind(self._T, ir.SumT)
        return tp.cast(ir.SumT, self._T)
 
    def match(self, *branches) -> Expr:
        branch_exprs = [make_lambda(fn, sort=T) for fn, T in zip(branches, self.raw_T.elemTs)]
        retT0 = branch_exprs[0].raw_T.retT
        if isinstance(retT0, ir.ApplyT):
            raise ValueError(f"Cannot have a dependent return type in a match")
        if not all(type(retT0) == type(e.T.retT) for e in branch_exprs):
            raise ValueError(f"Expected all branches to have result type {retT0}, got {', '.join([repr(e.T) for e in branch_exprs])}")
        match_node = ir.Match(retT0, self.node, TupleExpr.make([e.node for e in branch_exprs]).node)
        return wrap(match_node)


class LambdaExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_LambdaExpr(self.node):
            raise ValueError(f"Expected LambdaExpr, got {self}")

    @property
    def T(self) -> ir._LambdaTPlaceholder:
        assert isinstance(self._T, ir._LambdaTPlaceholder)
        return tp.cast(ir._LambdaTPlaceholder, self._T)
 
    @property
    def argT(self) -> ir.Type:
        return self.T.argT

    @property
    def resT(self) -> ir.Type:
        return self.T.retT

    def __repr__(self):
        return f"{self.argT} -> {self.resT}"

def make_lambda(fn: tp.Callable, sort: ir.Type, map_dom: DomainExpr=None) -> LambdaExpr:
    #if map_dom is not None:
    #    assert _is_kind(map_dom.T, ir.DomT)
    #    map_dom = map_dom.node
    #    is_map = True
    #else:
    #    map_dom = ir.Universe(ir.DomT.make(sort, False, False))
    #    is_map = False
    #bv_node = ir._BoundVarPlaceholder(sort, _map_dom=map_dom, _is_map=is_map)
    bv_node = ir._BoundVarPlaceholder(sort)
    bv_expr = wrap(bv_node)
    bv_expr._set_map_dom(map_dom)
    ret_expr = fn(bv_expr)
    ret_expr = Expr.make(ret_expr)
    lamT = ir._LambdaTPlaceholder(bv_node, ret_expr.T)
    lambda_node = ir._LambdaPlaceholder(lamT, bv_expr.node, ret_expr.node)
    return LambdaExpr(lambda_node)

class DomainExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_DomainExpr(self.node):
            raise ValueError(f"Domain must be a DomT, got {type(self.T)}")

    @property
    def T(self) -> ir.DomT:
        return tp.cast(ir.DomT, self._T)
 
    @classmethod
    def make(cls, val):
        raise NotImplementedError()
    
    @property
    def carT(self) -> ir.Type:
        def _carT(T: ir.Type):
            if isinstance(T, ir.DomT):
                return T.carT
            assert isinstance(T, ir.ApplyT)
            piT, arg = T.piT, T.arg
            dom, lam = piT._children
            bv, retT = lam._children
            appT = ir.ApplyT(
                ir.PiT(
                    dom,
                    ir._LambdaTPlaceholder(bv, _carT(retT))
                ),
                arg
            )
            return appT
        carT = _carT(self.T)
        #return carT
        simple_carT = _simplify_T(carT)
        return simple_carT

    def restrict(self, pred_fun: tp.Callable) -> DomainExpr:
        lambda_expr = make_lambda(pred_fun, sort=self.carT)
        if not _is_same_kind(lambda_expr.T.retT, ir.BoolT()):
            raise ValueError(f"Restrict predicate must return Bool, got {lambda_expr.T.retT}")
        T = ir.DomT.make(carT=self.carT, fin=self.T.fin, ord=self.T.ord)
        node = ir.Restrict(T, self.node, lambda_expr.node)
        return DomainExpr(node)

    def map(self, fn: tp.Callable) -> FuncExpr:
        lambda_expr = make_lambda(fn, sort=self.carT, map_dom=self)
        #lambda_expr = make_lambda(fn, sort=self.carT)
        lamT = lambda_expr.T
        T = ir.PiT(self.node, lamT)
        node = ir.Map(T, self.node, lambda_expr.node)
        return wrap(node)

    @classmethod
    def cartprod(cls, *doms: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(dom, DomainExpr) for dom in doms):
            raise ValueError(f"Expected all DomainExpr, got {doms}")
        carT = ir.TupleT(*[dom.carT for dom in doms])
        dom_nodes = tuple(dom.node for dom in doms)
        factors = ()
        fins = ()
        ords = ()
        axes = ()
        offset=0
        for dom in doms:
            factors += dom.T.factors
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
        doms = [self, *others]
        carT = ir.SumT(*[dom.carT for dom in doms])
        T = ir.DomT.make(carT=carT, fin=self.T.fin and all(other.T.fin for other in others), ord=self.T.ord and all(other.T.ord for other in others))
        coprod_node = ir.DisjUnion(T, *[dom.node for dom in doms])
        return wrap(coprod_node)

    def forall(self, pred_fun: tp.Callable) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, sort=self.carT)
        if not _is_same_kind(lambda_expr.T.retT, ir.BoolT()):
            raise ValueError(f"Forall predicate must return Bool, got {lambda_expr.T.retT}")
        node = ir.Forall(ir.BoolT(), self.node, lambda_expr.node)
        return BoolExpr(node)

    def exists(self, pred_fun: tp.Callable) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, sort=self.carT)
        if not _is_same_kind(lambda_expr.T.retT, ir.BoolT()):
            raise ValueError(f"Exists predicate must return Bool, got {lambda_expr.T.retT}")
        node = ir.Exists(ir.BoolT(), self.node, lambda_expr.node)
        return BoolExpr(node)

    def dom_proj(self, idx: int) -> DomainExpr:
        if idx >= len(self.T.factors):
            raise ValueError(f"Cannot project to {idx}'th dim of {self}")
        fac = self.T.factors[idx]
        T = ir.DomT.make(carT=fac, fin=self.T.fins[idx], ord=self.T.ords[idx])
        node = ir.DomProj(T, self.node, idx)
        return wrap(node)

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
    def __init__(self, enumT: ir.EnumT):
        assert isinstance(enumT, ir.EnumT)
        for label in enumT.labels:
            label_node = ir.EnumLit(enumT, label)
            label_expr = EnumExpr(label_node)
            setattr(self, label, label_expr)

class EnumDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_EnumDomainExpr(self.node):
            raise ValueError(f"Expected EnumDomainExpr, got {self}")
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
        assert self.raw_T.rank==1
        return wrap(ir.Slice(self.T, self.node, lo.node, hi.node))

    def index(self, idx: Expr):
        idx = Expr.make(idx)
        if idx.T != self.T.carT:
            raise ValueError(f"Cannot index into a {self.T} with {idx}")
        assert self.T.rank==1
        T = ir.DomT(*self.T.factors, fins=self.T.fins, ords=self.T.ords, axes=())
        return wrap(ir.Index(T, self.node, idx.node))

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> ArrayExpr:
        size = IntExpr.make(size)
        stride = IntExpr.make(stride)
        dom: DomainExpr = ((self.size-(size-stride))//stride).fin()
        return dom.map(
            lambda i: self[i*stride:i*stride+size] 
        )
    
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
            return self.index(idx)
            
 
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
        doms = [dom[v] for dom, v in zip(self.doms, val)]
        return DomainExpr.cartprod(*doms)


class FuncExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_FuncExpr(self.node):
            raise ValueError(f"Expected FuncExpr, got {self.T}")

    @property
    def T(self) -> ir.PiT:
        return tp.cast(ir.PiT, self._T)

    @property
    def domT(self) -> ir.DomT:
        return self.domain.T


    @property
    def domain(self) -> DomainExpr:
        if isinstance(self.T, ir.PiT):
            return wrap(self.T.dom)
        def _domainT(T: ir.Type):
            if isinstance(T, ir.PiT):
                return T.dom.T
            assert isinstance(T, ir.ApplyT)
            piT, arg = T.piT, T.arg
            dom, lam = piT._children
            bv, retT = lam._children
            domT = ir.ApplyT(
                ir.PiT(
                    dom,
                    ir._LambdaTPlaceholder(bv, _domainT(retT))
                ),
                arg
            )
            return domT
        domT = _domainT(self.T)
        domT_simple = _simplify_T(domT)
        domain = ir.Domain(domT_simple, self.node)
        return wrap(domain)

    #@property
    #def image(self) -> DomainExpr:
    #    T = ir.DomT.make(carT=self.elemT, fin=True, ord=True)
    #    node = ir.Image(T, self.node)
    #    return wrap(node)

    def elemT(self, arg: ir.Node) -> ir.Type:
        return _simplify_T(ir.ApplyT(self.T, arg))

    def carT(self) -> ir.Type:
        return self.domain.carT

    def apply(self, arg: Expr) -> Expr:
        arg = Expr.make(arg)
        node = ir.Apply(self.elemT(arg.node), self.node, arg.node)
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
        if not is_DomainExpr(dom.node):
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
    return is_DomainExpr(node) and _is_kind(_get_T(node.T).carT, ir.EnumT)

def is_SeqDomainExpr(node: ir.Node) -> bool:
    T = _get_T(node.T)
    return is_DomainExpr(node) and T.ord and T.fin and T.rank==1

def is_2DSeqDomainExpr(node: ir.Node) -> bool:
    return is_NDSeqDomainExpr(node) and _get_T(node.T).rank==2

def is_NDSeqDomainExpr(node: ir.Node) -> bool:
    T = _get_T(node.T)
    return is_DomainExpr(node) and T.ord and T.fin and T.rank > 1

def is_FuncExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and _is_kind(node.T, ir.PiT)

def is_ArrayExpr(node: ir.Node) -> bool:
    return is_FuncExpr(node) and is_SeqDomainExpr(_get_T(node.T).dom)

def is_NDArrayExpr(node: ir.Node) -> bool:
    return is_FuncExpr(node) and is_NDSeqDomainExpr(_get_T(node.T).dom)

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
