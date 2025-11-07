from __future__ import annotations
import typing as tp


from . import ir
from . import ir_types as irT
from .proof import ProofState, inference
from . import proof as pf
from dataclasses import dataclass, field
from enum import Enum as _Enum

TExpr = tp.TypeVar('TExpr', bound="Expr")
KExpr = tp.TypeVar('KExpr', bound="Expr")
VExpr = tp.TypeVar('VExpr', bound="Expr")

def _mix_envs(*exprs: Expr) -> tp.Dict[ir.Node, ProofState]:
    if len(exprs)==0:
        return {}
    else:
        env1 = exprs[0].penv
        env2 = _mix_envs(*exprs[1:])
        env = {}
        for n in (set(env1.keys()) | set((env2.keys()))):
            ps1 = env1.get(n, None)
            ps2 = env2.get(n, None)
            match (ps1, ps2):
                case (None, ps2):
                    env[n] = ps2
                case (ps1, None):
                    env[n] = ps1
                case (ps1, ps2):
                    env[n] = ps1 + ps2
                case _:
                    raise ValueError(f"Expected ProofState, got {type(ps1)} and {type(ps2)}")
        return env


@dataclass
class Expr:
    node: ir.Node
    penv: tp.Dict[ir.Node, ProofState] = field(default_factory=dict)

    @property
    def _T(self) -> irT.Type_:
        return self.penv[self.node].T

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
    def T(self) -> irT.UnitType:
        return tp.cast(irT.UnitType, self._T)
    
    @staticmethod
    def make(cls) -> UnitExpr:
        node = ir.Unit()
        penv = inference(node)
        return UnitExpr(node, penv)

class BoolExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_BoolExpr(self.node, self.penv):
            raise ValueError(f"Expected BoolExpr, got {self}")

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
            return BoolExpr(node)
        except:
            raise ValueError(f"Cannot make BoolExpr from {val}")

    def __invert__(self) -> BoolExpr:
        node = ir.Not(self.node)
        penv = inference(node, self.penv)
        return BoolExpr(node, penv)

    def implies(self, other: BoolOrExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Implies(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def __and__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.And(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    __rand__ = __and__

    def __or__(self, other: BoolExpr) -> BoolExpr:
        node = ir.Or(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    __ror__ = __or__

    def __eq__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Eq(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)
    
    def __ne__(self, other: BoolExpr) -> BoolExpr:
        other = BoolExpr.make(other)
        node = ir.Not(ir.Eq(self.node, other.node))
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def ite(self, t: Expr, f: Expr) -> Expr:
        node = ir.Ite(self.node, t.node, f.node)
        penv = inference(node, _mix_envs(self, t, f))
        return wrap(node, penv)

    def __bool__(self) -> bool:
        raise TypeError("BoolExpr cannot be used as a python boolean")
    
    def __int__(self) -> IntExpr:
        return self.ite(IntExpr.make(1), IntExpr.make(0))

    @staticmethod
    def all_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(True)
        node = ir.Conj(*[BoolExpr.make(a).node for a in args])
        penv = inference(node, _mix_envs(*args))
        return BoolExpr(node, penv)

    @staticmethod
    def any_of(*args: 'BoolExpr') -> 'BoolExpr':
        if len(args) == 0:
            return BoolExpr.make(False)
        node = ir.Disj(*[BoolExpr.make(a).node for a in args])
        penv = inference(node, _mix_envs(*args))
        return BoolExpr(node, penv)

class IntExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_IntExpr(self.node, self.penv):
            raise ValueError(f"Expected IntExpr, got {self}")

    @property
    def T(self) -> irT._Int:
        return tp.cast(irT._Int, self._T)

    @classmethod
    def make(cls, val: tp.Any) -> IntExpr:
        if isinstance(val, IntExpr):
            return tp.cast(IntExpr, val)
        try:
            val = int(val)
            node = ir.Lit(val, irT.Int)
            return IntExpr(node)
        except:
            raise ValueError(f"Expected Int expression. Got {val}")

    def __add__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Add(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return IntExpr(node, penv)

    def __sub__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Sub(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return IntExpr(node, penv)

    def __neg__(self) -> IntExpr:
        node = ir.Neg(self.node)
        penv = inference(node, self.penv)
        return IntExpr(node, penv)

    def __abs__(self) -> IntExpr:
        return (self >= 0).ite(self, -self)

    def __mul__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mul(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return IntExpr(node, penv)

    def __floordiv__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Div(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return IntExpr(node, penv)

    def __mod__(self, other: IntOrExpr) -> IntExpr:
        other = IntExpr.make(other)
        node = ir.Mod(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return IntExpr(node, penv)

    def __gt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Gt(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def __ge__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.GtEq(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def __lt__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Lt(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def __le__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.LtEq(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def __eq__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Eq(self.node, other.node)
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def __ne__(self, other: IntOrExpr) -> BoolExpr:
        other = IntExpr.make(other)
        node = ir.Not(ir.Eq(self.node, other.node))
        penv = inference(node, _mix_envs(self, other))
        return BoolExpr(node, penv)

    def __bool__(self) -> bool:
        raise TypeError("IntExpr cannot be used as a python boolean")

    def fin(self) -> IterDomainExpr:
        node = ir.Fin(self.node)
        penv = inference(node, self.penv)
        return IterDomainExpr(node, penv)

    def __repr__(self):
        return f"Int({self.node})"

class EnumExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_EnumExpr(self.node, self.penv):
            raise ValueError(f"Expected EnumExpr, got {self}")
    
    @property
    def T(self) -> irT.EnumT:
        return tp.cast(irT.EnumT, self._T)


class TupleExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_TupleExpr(self.node, self.penv):
            raise ValueError(f"Expected TupleExpr, got {self}")

    @property
    def T(self) -> irT.TupleT:
        assert isinstance(self._T, irT.TupleT)
        return tp.cast(irT._Bool, self._T)
   
    @classmethod
    def make(cls, vals: tp.Tuple[tp.Any, ...]) -> TupleExpr:
        if isinstance(vals, TupleExpr):
            return vals
        try:
            vals = tuple(Expr.make(v) for v in vals)
            node = ir.TupleLit(*[e.node for e in vals])
            penv = inference(node, _mix_envs(*vals))
            return TupleExpr(node, penv)
        except:
            raise ValueError(f"Expected Tuple of values, got {vals}")

    def __getitem__(self, idx: int) -> Expr:
        node = ir.Proj(self.node, idx)
        penv = inference(node, self.penv)
        return wrap(node, penv)

    def __len__(self) -> int:
        return len(self.node._children)

    # Nice unpacking
    def __iter__(self) -> None:
        for i in range(len(self)):
            yield self[i]

class SumExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_SumExpr(self.node, self.penv):
            raise ValueError(f"Expected SumExpr, got {self}")

    @property
    def T(self) -> irT.SumT:
        assert isinstance(self.T, irT.SumT)
        return tp.cast(irT.SumT, self._T)
 
    def match(self, *branches) -> Expr:
        branch_exprs = [make_lambda(fn, T) for fn, T in zip(branches, self.T.elemTs)]
        ret_type = branch_exprs[0].T
        if not all(e.T == ret_type for e in branch_exprs):
            raise ValueError(f"Expected all branches to have result type {ret_type}, got {', '.join([repr(e.T) for e in branch_exprs])}")
        match_node = ir.Match(self.node, ir.TupleLit(*[e.node for e in branch_exprs]))
        return tp.cast(Expr, wrap_base(match_node, ret_type))


class LambdaExpr(Expr, tp.Generic[TExpr, VExpr]):
    @property
    def T(self) -> irT.ArrowT:
        assert isinstance(self._T, irT.ArrowT)
        return tp.cast(irT.ArrowT, self._T)
 
    @property
    def arg_type(self) -> irT.Type_:
        return self.T.argT

    @property
    def res_type(self) -> irT.Type_:
        return self.T.resT

    def __repr__(self):
        return f"lambda {self.arg_type}: {self.res_type}"


# Domain expresion is only passed in during tabulate (due to free var creation)
def make_lambda(fn: tp.Callable[[TExpr], VExpr], paramT: irT.Type_, dom: DomainExpr=None) -> 'LambdaExpr[TExpr, VExpr]':
    if dom is None:
        dom = UnitExpr.make()
    bv_node = ir._BoundVarPlaceholder(paramT=paramT)
    bv_penv = inference(bv_node)
    bv_expr = wrap(bv_node, bv_penv)
    ret_expr = fn(bv_expr)
    lambda_node = ir._LambdaPlaceholder(bv_expr.node, ret_expr.node, paramT)
    lam_penv = _mix_envs(bv_expr, ret_expr)
    return LambdaExpr(lambda_node, lam_penv)

IntOrExpr = tp.Union[int, IntExpr, Expr]
BoolOrExpr = tp.Union[bool, BoolExpr, Expr]
EnumOrExpr = tp.Union[str, EnumExpr, Expr]

class DomainExpr(Expr):
    def __post_init__(self):
        super().__post_init__()
        if not is_DomainExpr(self.node, self.penv):
            raise ValueError(f"Domain must be a DomT, got {type(self.T)}")

    @property
    def T(self) -> irT.DomT:
        return tp.cast(irT.DomT, self._T)
 
    @classmethod
    def make(cls, val):
        raise NotImplementedError()
    
    @property
    def carT(self) -> irT.Type_:
        return self.T.carT

    def restrict(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> 'DomainExpr[TExpr]':
        lambda_expr = make_lambda(pred_fun, self.carT)
        node = ir.Restrict(self.node, lambda_expr.node)
        penv = inference(node, _mix_envs(self, lambda_expr))
        return tp.cast(DomainExpr, wrap(node, penv))

    def tabulate(self, fn: tp.Callable[[TExpr], TExpr]) -> 'FuncExpr[TExpr]':
        lambda_expr = make_lambda(fn, self.carT)
        node = ir.Tabulate(self.node, lambda_expr.node)
        penv = inference(node, _mix_envs(self, lambda_expr))
        return tp.cast(FuncExpr[TExpr], wrap(node, penv))

    def cartprod(self, *others: 'DomainExpr') -> 'DomainExpr':
        if not all(isinstance(other, DomainExpr) for other in others):
            raise ValueError(f"Expected list of DomainExpr, got {others}")
        cartprod_node = ir.CartProd(self.node, *[other.node for other in others])
        penv = inference(cartprod_node, _mix_envs(self, *others))
        return tp.cast(DomainExpr, wrap(cartprod_node, penv))

    def coproduct(self, *others: 'DomainExpr') -> 'DomainExpr':
        coprod_node = ir.DisjUnion(self.node, *[other.node for other in others])
        penv = inference(coprod_node, _mix_envs(self, *others))
        return tp.cast(DomainExpr, wrap(coprod_node, penv))

    def forall(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, self.carT)
        node = ir.Forall(self.node, lambda_expr.node)
        penv = inference(node, _mix_envs(self, lambda_expr))
        return tp.cast(BoolExpr, wrap(node, penv))

    def exists(self, pred_fun: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        lambda_expr = make_lambda(pred_fun, self.carT)
        node = ir.Exists(self.node, lambda_expr.node)
        penv = inference(node, _mix_envs(self, lambda_expr))
        return tp.cast(BoolExpr, wrap(node, penv))

    def __len__(self) -> IntExpr:
        node = ir.Card(self.node)
        penv = inference(node, self.penv)
        return tp.cast(IntExpr, wrap(node, penv))

    def __contains__(self, elem: TExpr) -> BoolExpr:
        node = ir.IsMember(self.node, elem.node)
        penv = inference(node, _mix_envs(self, elem))
        return tp.cast(BoolExpr, wrap(node, penv))

    def __add__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.coproduct(other)
    
    def __mul__(self, other: 'DomainExpr') -> 'DomainExpr':
        return self.cartprod(other)

    # Operators of subclasses of DomainExpr
    # TODO

class _EnumAttrs:
    def __init__(self, enumT: irT.EnumT):
        assert isinstance(enumT, irT.EnumT)
        for label in enumT.labels:
            label_node = ir.EnumLit(enumT, label)
            label_penv = inference(label_node)
            label_expr = wrap(label_node, label_penv)
            setattr(self, label, label_expr)

class EnumDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_EnumDomainExpr(self.node, self.penv):
            raise ValueError(f"Expected EnumDomainExpr, got {self}")
        self._members = _EnumAttrs(self.T.carT)

    @property
    def members(self) -> _EnumAttrs:
        return self._members

    @property
    def T(self) -> irT.DomT[irT.EnumT]:
        return tp.cast(irT.DomT[irT.EnumT], self._T)

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
        enumT = irT.EnumT(name, *labels)
        node = ir.Enum(enumT)
        penv = inference(node)
        return EnumDomainExpr(node, penv)

class IterDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_IterDomainExpr(self.node, self.penv):
            raise ValueError(f"Expected IterDomainExpr, got {self}")

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> ArrayExpr[IterDomainExpr[TExpr]]:
        size = IntExpr.make(size)
        stride = IntExpr.make(stride)
        func_node = ir.Windows(self.node, size.node, stride.node)
        penv = inference(func_node, _mix_envs(self, size, stride))
        return ArrayExpr(func_node, penv)
 
class NDIterDomainExpr(DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not is_NDIterDomainExpr(self.node, self.penv):
            raise ValueError(f"Expected NDIterDomainExpr, got {self}")

    def tiles(self, size: tp.Tuple[IntOrExpr, ...], stride: tp.Tuple[IntOrExpr, ...]) -> NDArrayExpr[NDIterDomainExpr[TExpr]]:
        node = ir.Tiles(self.node, *[IntExpr.make(s) for s in size], *[IntExpr.make(s) for s in stride])
        penv = inference(node, _mix_envs(self, *[IntExpr.make(s) for s in size], *[IntExpr.make(s) for s in stride]))
        return NDArrayExpr(node, penv)

    def dom_proj(self, idx: int) -> IterDomainExpr:
        node = ir.DomProj(self.node, idx)
        penv = inference(node, self.penv)
        return IterDomainExpr(node, penv)

    def doms(self) -> TupleExpr[DomainExpr]:
        return TupleExpr.make([self.dom_proj(i) for i in range(len(self))])

    def dims(self) -> TupleExpr[IntExpr]:
        return TupleExpr.make([len(self.dom_proj(i)) for i in range(len(self))])

    def slices(self, idx: int) -> ArrayExpr[DomainExpr]:
        node = ir.Slices(self.node, idx)
        penv = inference(node, self.penv)
        return ArrayExpr(node, penv)

    def rows(self) -> ArrayExpr[IterDomainExpr]:
        if not is_2DArrayExpr(self.node, self.penv):
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.slices(0)

    def cols(self) -> ArrayExpr[IterDomainExpr]:
        if not is_2DArrayExpr(self.node, self.penv):
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.slices(1)

# Texpr represents the carrier type of the function domain
# Vexpr represents the carrier type of the function image
class FuncExpr(Expr, tp.Generic[TExpr, VExpr]):
    def __post_init__(self):
        super().__post_init__()
        if not is_FuncExpr(self.node, self.penv):
            raise ValueError(f"Expected FuncExpr, got {self.T}")

    @property
    def T(self) -> irT.FuncT:
        return tp.cast(irT.FuncT, self._T)

    @property
    def domT(self) -> irT.DomT:
        return self.T.domT

    @property
    def domain(self) -> DomainExpr:
        node = ir.DomOf(self.node)
        penv = inference(node, self.penv)
        return tp.cast(DomainExpr, wrap(node, penv))

    @property
    def image(self) -> DomainExpr:
        node = ir.ImageOf(self.node)
        penv = inference(node, self.penv)
        return tp.cast(DomainExpr, wrap(node, penv))

    @property 
    def elemT(self) -> irT.Type_:
        return self.T.resT

    @property
    def carT(self) -> irT.Type_:
        return self.T.domT.carT

    def apply(self, arg: Expr) -> Expr:
        node = ir.Apply(self.node, arg.node)
        penv = inference(node, _mix_envs(self, arg))
        return wrap(node, penv)

    # Func[Dom(A) -> B] -> (B -> C) -> Func[Dom(A) -> C]
    def map(self, fn: tp.Callable[[TExpr], TExpr]) -> 'FuncExpr[TExpr]':
        return self.domain.tabulate(lambda a: fn(self.apply(a)))

    def enumerate(self) -> 'FuncExpr[TExpr]':
        return self.domain.tabulate(lambda a: TupleExpr.make((a, self.apply(a))))

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
        penv = inference(node, self.penv)
        return wrap(node, penv)

    def __len__(self) -> IntExpr:
        return len(self.domain)
    
    def __contains__(self, elem: TExpr) -> BoolExpr:
        return elem in self.image

    def __call__(self, val) -> TExpr:
        return self.apply(val)

    def __getitem__(self, func: FuncExpr) -> FuncExpr:
        return func.map(lambda v: self.apply(v))

class ArrayExpr(FuncExpr, tp.Generic[TExpr]):
    def __post_init__(self):
        super().__post_init__()
        if not is_ArrayExpr(self.node, self.penv):
            raise ValueError(f"Array domain must be enumerable with rank 1, got {self.T.domT}")
  
    @classmethod
    def make(cls, val: tp.List[tp.Any]) -> ArrayExpr[TExpr]:
        if isinstance(val, ArrayExpr[TExpr]):
            return val
        try:
            vals = [Expr.make(v) for v in val]
        except:
            raise ValueError(f"Expected List of values, got {val}")
        node = ir.ListLit(*[e.node for e in vals])
        penv = inference(node, _mix_envs(*vals))
        return ArrayExpr(node, penv)

    @property
    def T(self) -> irT.FuncT[IterDomainExpr[TExpr], TExpr]:
        return tp.cast(irT.FuncT[IterDomainExpr[TExpr], TExpr], self._T)

    @property
    def domain(self) -> IterDomainExpr:
        node = ir.DomOf(self.node)
        penv = inference(node, self.penv)
        return ArrayExpr(node, penv)

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> ArrayExpr[ArrayExpr[TExpr]]:
        wins = self.domain.windows(size, stride) # Func[Fin(n) -> SeqDom(A)]
        wins.map(lambda win: win.tabulate(lambda i: self[i]))

    def __getitem__(self, idx: tp.Optional[IntOrExpr, FuncExpr]) -> TExpr:
        if isinstance(idx, FuncExpr):
            return super().__getitem__(idx)
        idx = IntExpr.make(idx)
        return self.apply(idx)

    def __len__(self) -> IntExpr:
        return len(self.domain)

    def __iter__(self) -> None:
        raise ValueError("ArrayExpr is not iterable at python runtime")

# Func[NDDom -> T]
class NDArrayExpr(FuncExpr[TExpr]):
    def __post_init__(self):
        super().__post_init__()
        if not is_NDVecExpr(self.node, self.penv):
            raise ValueError(f"NDVec domain must be enumerable with rank 2, got {self.T.domT}")

    @property
    def T(self) -> irT.FuncT:
        return tp.cast(irT.FuncT, self._T)

    @property
    def dims(self) -> TupleExpr[IntExpr]:
        return self.domain.dims()

    def rows(self) -> ArrayExpr[ArrayExpr[TExpr]]:
        if not is_2DArrayExpr(self.node, self.penv):
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.domain.rows().map(lambda row: row.tabulate(lambda rc: self.apply(rc)))

    def cols(self) -> ArrayExpr[ArrayExpr[TExpr]]:
        return self.domain.cols().map(lambda col: col.tabulate(lambda rc: self.apply(rc)))

    def tiles(self, size: tp.Tuple[IntOrExpr, ...], stride: tp.Tuple[IntOrExpr, ...]=None) -> ArrayExpr[TExpr]:
        return self.domain.tiles(size, stride).map(lambda tile_dom: tile_dom.tabulate(lambda indices: self.apply(indices)))

# TODO START HERE TOMORROW
def is_UnitExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return penv[node].T == irT.UnitType

def as_Unit(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> UnitExpr:
    if is_UnitExpr(node, penv):
        return UnitExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to UnitExpr")

def is_BoolExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return penv[node].T == irT.Bool

def as_Bool(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> BoolExpr:
    if is_BoolExpr(node, penv):
        return BoolExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to BoolExpr")

def is_IntExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return penv[node].T == irT.Int

def as_Int(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> IntExpr:
    if is_IntExpr(node, penv):
        return IntExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to IntExpr")

def is_EnumExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.EnumT)

def as_Enum(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> EnumExpr:
    if is_EnumExpr(node, penv):
        return EnumExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to EnumExpr")

def is_TupleExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.TupleT)

def as_Tuple(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> TupleExpr:
    if is_TupleExpr(node, penv):
        return TupleExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to TupleExpr")

def is_SumExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.SumT)

def as_Sum(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> SumExpr:
    if is_SumExpr(node, penv):
        return SumExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to SumExpr")

def is_LambdaExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.ArrowT)

def as_Lambda(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> LambdaExpr:
    if is_LambdaExpr(node, penv):
        return LambdaExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to LambdaExpr")

def is_DomainExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.DomT)

def as_Domain(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> DomainExpr:
    if is_DomainExpr(node, penv):
        return DomainExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to DomainExpr")

def is_EnumDomainExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.DomT[irT.EnumT])

def as_EnumDomain(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> EnumDomainExpr:
    if is_EnumDomainExpr(node, penv):
        return EnumDomainExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to EnumDomainExpr")

def is_IterDomainExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.DomT) and penv[node].T.cap.enumerable == 1

def as_IterDomain(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> IterDomainExpr:
    if is_IterDomainExpr(node, penv):
        return IterDomainExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to IterDomainExpr")

def is_2DArrayExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.FuncT) and isinstance(T.domT, irT.DomT) and T.domT.cap.enumerable == 2

def is_NDIterDomainExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.DomT) and penv[node].T.cap.enumerable == 2

def as_NDIterDomain(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> NDIterDomainExpr:
    if is_NDIterDomainExpr(node, penv):
        return NDIterDomainExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to NDIterDomainExpr")

def is_FuncExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    return isinstance(penv[node].T, irT.FuncT)

def as_Func(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> FuncExpr:
    if is_FuncExpr(node, penv):
        return FuncExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to FuncExpr")

def is_ArrayExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    T = penv[node].T
    return isinstance(T, irT.FuncT) and isinstance(T.domT, irT.DomT) and T.domT.cap.enumerable == 1

def as_Array(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> ArrayExpr:
    if is_ArrayExpr(node, penv):
        return ArrayExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to ArrayExpr")

def is_NDArrayExpr(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> bool:
    T = penv[node].T
    return isinstance(T, irT.FuncT) and isinstance(T.domT, irT.DomT) and T.domT.cap.enumerable == 2

def as_NDArray(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> NDArrayExpr:
    if is_NDArrayExpr(node, penv):
        return NDArrayExpr(node, penv)
    raise ValueError(f"Cannot cast node {node} to NDArrayExpr")

def wrap(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> Expr:
    if is_UnitExpr(node, penv):
        return as_Unit(node, penv)
    if is_BoolExpr(node, penv):
        return as_Bool(node, penv)
    if is_IntExpr(node, penv):
        return as_Int(node, penv)
    if is_EnumExpr(node, penv):
        return as_Enum(node, penv)
    if is_LambdaExpr(node, penv):
        return as_Lambda(node, penv)
    if is_TupleExpr(node, penv):
        return as_Tuple(node, penv)
    if is_SumExpr(node, penv):
        return as_Sum(node, penv)
    if is_NDVecExpr(node, penv):
        return as_NDVec(node, penv)
    if is_ArrayExpr(node, penv):
        return as_Array(node, penv)
    if is_DomainExpr(node, penv):
        return as_Domain(node, penv)
    raise NotImplementedError(f"Cannot cast node {node} to Expr")
