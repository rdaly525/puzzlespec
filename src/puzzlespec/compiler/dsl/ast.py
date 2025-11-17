from __future__ import annotations
import typing as tp
from . import ir
from . import proof_lib as pf 
from dataclasses import dataclass, field
from enum import Enum as _Enum

@dataclass
class Expr:
    node: ir.Value

    def __post_init__(self):
        if not isinstance(self.node, ir.Value):
            raise ValueError("Expr must be an ir.Value, got {self.node}")

    @property
    def _T(self) -> ir.Type:
        return self.node.T

    @classmethod
    def make(cls, val: tp.Any) -> Expr:
        if isinstance(val, Expr):
            return val
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
        raise NotImplementedError(f"Cannot make Expr from {val}")

    def __repr__(self):
        return f"<{type(self).__name__} {self.node}>"

class UnitExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_UnitExpr(self.node, self.penv):
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
        node = ir.Not(self.node)
        return BoolExpr(node)

    def implies(self, other: BoolOrExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Implies(self.node, other.node)
        return BoolExpr(node)

    def __and__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.And(self.node, other.node)
        return BoolExpr(node)

    __rand__ = __and__

    def __or__(self, other: BoolExpr) -> BoolExpr:
        node = ir.Or(self.node, other.node)
        return BoolExpr(node)

    __ror__ = __or__

    def __eq__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Eq(self.node, other.node)
        return BoolExpr(node)
    
    def __ne__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Not(ir.Eq(self.node, other.node))
        return BoolExpr(node)

    def ite(self, t: Expr, f: Expr) -> Expr:
        t, f = Expr.make(t), Expr.make(f)
        node = ir.Ite(self.node, t.node, f.node)
        return Expr(node)

    def __bool__(self) -> bool:
        raise TypeError("BoolExpr cannot be used as a python boolean")
    
    def __int__(self) -> IntExpr:
        return self.ite(IntExpr.make(1), IntExpr.make(0))

    @staticmethod
    def all_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(True)
        node = ir.Conj(*[BoolExpr.make(a).node for a in args])
        return BoolExpr(node)

    @staticmethod
    def any_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(False)
        node = ir.Disj(*[BoolExpr.make(a).node for a in args])
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
        node = ir.Add(self.node, other.node)
        return IntExpr(node)

    def __sub__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Sub(self.node, other.node)
        return IntExpr(node)

    def __neg__(self) -> IntExpr:
        node = ir.Neg(self.node)
        return IntExpr(node)

    def __abs__(self) -> IntExpr:
        return (self >= 0).ite(self, -self)

    def __mul__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mul(self.node, other.node)
        return IntExpr(node)

    def __floordiv__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Div(self.node, other.node)
        return IntExpr(node)

    def __mod__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mod(self.node, other.node)
        return IntExpr(node)

    def __gt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Gt(self.node, other.node)
        return BoolExpr(node)

    def __ge__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.GtEq(self.node, other.node)
        return BoolExpr(node)

    def __lt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Lt(self.node, other.node)
        return BoolExpr(node)

    def __le__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.LtEq(self.node, other.node)
        return BoolExpr(node)

    def __eq__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Eq(self.node, other.node)
        return BoolExpr(node)

    def __ne__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        return ~ir.Eq(self.node, other.node)\

    def __bool__(self) -> bool:
        raise TypeError("IntExpr cannot be used as a python boolean")

    def fin(self) -> SeqDomainExpr:
        node = ir.Fin(self.node)
        return SeqDomainExpr(node)

    def __repr__(self):
        return f"Int({self.node})"

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
        node = ir.Eq(self.node, other.node)
        return BoolExpr(node)

    def __ne__(self, other: Expr) -> BoolExpr:
        other = EnumExpr.make(other)
        return ~ir.Eq(self.node, other.node)

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
        assert isinstance(self._T, ir.TupleT)
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
        except:
            raise ValueError(f"Expected Tuple of values, got {vals}")

    @classmethod
    def empty(cls):
        return cls.make()

    def __getitem__(self, idx: int) -> Expr:
        if idx < 0 or idx >= len(self):
            raise IndexError(f"Tuple index out of range: {idx}")
        node = ir.Proj(self.T[idx], self.node, idx)
        return Expr(node)

    def __len__(self) -> int:
        return len(self.node._children)

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
        assert isinstance(self._T, ir.SumT)
        return tp.cast(ir.SumT, self._T)
 
    def match(self, *branches) -> Expr:
        branch_exprs = [make_lambda(fn, sort=T) for fn, T in zip(branches, self.T.elemTs)]
        resT = branch_exprs[0].T.resT
        if not all(e.T.resT == resT for e in branch_exprs):
            raise ValueError(f"Expected all branches to have result type {resT}, got {', '.join([repr(e.T) for e in branch_exprs])}")
        T = branch_exprs[0].T
        match_node = ir.Match(T, self.node, TupleExpr.make([e.node for e in branch_exprs]))
        return wrap(match_node)


class LambdaExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_LambdaExpr(self.node):
            raise ValueError(f"Expected LambdaExpr, got {self}")

    @property
    def T(self) -> ir.ArrowT:
        assert isinstance(self._T, ir.ArrowT)
        return tp.cast(ir.ArrowT, self._T)
 
    @property
    def argT(self) -> ir.Type:
        return self.T.argT

    @property
    def resT(self) -> ir.Type:
        return self.T.resT

    def __repr__(self):
        return f"{self.argT} -> {self.resT}"


# Domain expresion is only passed in during tabulate (due to free var creation)
def make_lambda(fn: tp.Callable, sort: ir.Type) -> LambdaExpr:
    bv_node = ir._BoundVarPlaceholder(sort)
    bv_expr = wrap(bv_node)
    ret_expr = fn(bv_expr)
    ret_expr = Expr.make(ret_expr)
    lambda_node = ir._LambdaPlaceholder(ir.ArrowT(sort, ret_expr.T), bv_expr.node, ret_expr.node)
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
        return self.T.carT

    def restrict(self, pred_fun: tp.Callable) -> DomainExpr:
        lambda_expr = make_lambda(pred_fun, sort=self.carT)
        node = ir.Restrict(ir.DomT(self.T.carT), self.node, lambda_expr.node)
        return DomainExpr(node)

    def map(self, fn: tp.Callable) -> FuncExpr:
        lambda_expr = make_lambda(fn, sort=self.carT)
        node = ir.Map(self.node, lambda_expr.node)
        return wrap(node)

    @classmethod
    def cartprod(cls, *doms: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(dom, DomainExpr) for dom in doms):
            raise ValueError(f"Expected all DomainExpr, got {doms}")
        carT = ir.TupleT(*[dom.carT for dom in doms])
        dom_nodes = [dom.node for dom in doms]
        prod_doms = TupleExpr.make(*dom_nodes)
        cartprod_node = ir.CartProd(ir.DomT(carT,prod_doms=prod_doms), *dom_nodes)
        return wrap(cartprod_node)

    def prod(self, *others: 'DomainExpr') -> 'DomainExpr':
        return DomainExpr.cartprod(self, *others)

    def coproduct(self, *others: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(other, DomainExpr) for other in others):
            raise ValueError(f"Expected list of DomainExpr, got {others}")
        doms = [self, *others]
        carT = ir.SumT(*[dom.carT for dom in doms])
        coprod_node = ir.DisjUnion(ir.DomT(carT), self.node)
        return wrap(coprod_node)

    def forall(self, pred_fun: tp.Callable) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, dom=self)
        node = ir.Forall(self.node, lambda_expr.node)
        return BoolExpr(node)

    def exists(self, pred_fun: tp.Callable) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, dom=self)
        node = ir.Exists(self.node, lambda_expr.node)
        return BoolExpr(node)

    # TODO 
    #def partition(self, dom:DomainExpr, color_fun):
    #    #return dom.tabulate(lambda k: self.restrict(lambda c: color_fun(c)==k))
    #    ...

    #def quotent(self, eqrel):
    #    ...

    @property
    def size(self) -> IntExpr:
        node = ir.Card(self.node)
        return IntExpr(node)

    def __contains__(self, elem: Expr) -> BoolExpr:
        elem = Expr.make(elem)
        node = ir.IsMember(self.node, elem.node)
        return BoolExpr(node)

    def __add__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.coproduct(other)
    
    def __mul__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.cartprod(other)

    # Operators of subclasses of DomainExpr
    # TODO

class _EnumAttrs:
    def __init__(self, enumT: ir.EnumT):
        assert isinstance(enumT, ir.EnumT)
        for label in enumT.labels:
            label_node = ir.EnumLit(enumT, label)
            label_expr = Expr(label_node)
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
        enumT = ir.EnumT(name, *labels)
        node = ir.Enum(enumT)
        return EnumDomainExpr(node)

class SeqDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_SeqDomainExpr(self.node, self.penv):
            raise ValueError(f"Expected SeqDomainExpr, got {self}")

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> ArrayExpr[SeqDomainExpr]:
        size = IntExpr.make(size)
        stride = IntExpr.make(stride)
        dom: DomainExpr = ((self.size-(size-stride))/stride).fin()
        T = ir.FuncT(dom, self.T)
        func_node = ir.Windows(T, self.node, size.node, stride.node)
        return ArrayExpr(func_node)
 
class NDSeqDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_NDSeqDomainExpr(self.node):
            raise ValueError(f"Expected NDSeqDomainExpr, got {self}")

    def tiles(self, size: tp.Tuple[IntOrExpr, ...], stride: tp.Tuple[IntOrExpr, ...]=None) -> NDArrayExpr:
        num_dims = len(self)
        if stride == None:
            strides = [IntExpr.make(1) for _ in range(num_dims)]
        else:
            strides = [IntExpr.make(s) for s in stride]
        sizes = [IntExpr.make(s) for s in size]
        if len(sizes) != num_dims or len(strides) != num_dims:
            raise ValueError(f"Expected size and stride for all dimensions ({num_dims}), got {size} and {stride}")
        fins = [((self.doms[i].size-(sizes[i]-strides[i]))/strides[i]).fin() for i in range(num_dims)]
        dom = DomainExpr.cartprod(*fins)
        T = ir.FuncT(dom, self.T)
        node = ir.Tiles(T, dom, sizes, strides)
        return NDArrayExpr(node)

    def dom_proj(self, idx: int) -> SeqDomainExpr:
        T = self.T.prod_doms.T[idx]
        node = ir.DomProj(T, self.node, idx)
        return wrap(node)

    @property
    def doms(self) -> tp.Tuple[DomainExpr]:
        return tuple(self.dom_proj(i) for i in range(len(self)))

    @property
    def dims(self) -> TupleExpr[IntExpr]:
        return tuple(dom.size for dom in self.doms)

    def slices(self, idx: int) -> ArrayExpr[DomainExpr]:
        dom = self.dom_proj(idx)
        T = ir.FuncT(dom, self.T)
        node = ir.Slices(T, dom, idx)
        return ArrayExpr(node)

    def rows(self) -> ArrayExpr[SeqDomainExpr]:
        if not is_2DSeqDomainExpr(self.node):
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.slices(0)

    def cols(self) -> ArrayExpr[SeqDomainExpr]:
        if not is_2DSeqDomainExpr(self.node):
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.slices(1)

    def __getitem__(self, idx: int):
        return self.dom_proj(idx)

    def __len__(self):
        return len(self.T)

class FuncExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_FuncExpr(self.node):
            raise ValueError(f"Expected FuncExpr, got {self.T}")

    @property
    def T(self) -> ir.FuncT:
        return tp.cast(ir.FuncT, self._T)

    @property
    def domT(self) -> ir.DomT:
        return self.T.dom.carT

    @property
    def domain(self) -> DomainExpr:
        return self.T.dom

    @property
    def image(self) -> DomainExpr:
        T = ir.DomT(self.elemT)
        node = ir.Image(T, self.node)
        return wrap(node)

    @property 
    def elemT(self) -> ir.Type:
        return self.T.retT

    @property
    def carT(self) -> ir.Type:
        return self.domain.carT

    def apply(self, arg: Expr) -> Expr:
        node = ir.Apply(self.elemT, self.node, arg.node)
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
        return self.domain.size()
    
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
        if not all(v.T == vals[0].T for v in vals):
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
        wins.map(lambda win: win.map(lambda i: self(i)))

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

    @property
    def dims(self) -> TupleExpr:
        return self.domain.dims()

    def rows(self) -> ArrayExpr:
        return self.domain.rows().map(lambda row: self[row])

    def cols(self) -> ArrayExpr:
        return self.domain.cols().map(lambda col: self[col])

    def tiles(self, size: tp.Tuple[IntOrExpr, ...], stride: tp.Tuple[IntOrExpr, ...]=None) -> ArrayExpr[TExpr]:
        return self.domain.tiles(size, stride).map(
            lambda tile_dom: tile_dom.map(lambda indices: self.apply(indices))
        )

def is_UnitExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.Unit)

def is_BoolExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.BoolT)

def is_IntExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.IntT)

def is_EnumExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.EnumT)

def is_TupleExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.TupleT)

def is_SumExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.SumT)

def is_LambdaExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.ArrowT)

def is_DomainExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.DomT)

def is_EnumDomainExpr(node: ir.Node) -> bool:
    return is_DomainExpr(node) and isinstance(node.T.carT, ir.EnumT)

def is_SeqDomainExpr(node: ir.Node) -> bool:
    return is_DomainExpr(node) and node.T.ord and node.T.fin

def is_2DSeqDomainExpr(node: ir.Node) -> bool:
    return is_NDSeqDomainExpr(node) and len(node.T.prod_doms) == 2

def is_NDSeqDomainExpr(node: ir.Node) -> bool:
    return is_SeqDomainExpr(node) and len(node.T.prod_doms) > 1

def is_FuncExpr(node: ir.Node) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.FuncT)

def is_ArrayExpr(node: ir.Node) -> bool:
    return is_FuncExpr(node) and is_SeqDomainExpr(node.T.dom)

def is_NDArrayExpr(node: ir.Node) -> bool:
    return is_ArrayExpr(node) and is_NDSeqDomainExpr(node.T.dom)

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
    raise NotImplementedError(f"Cannot cast node {node} to Expr")
