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
    T: irT.Type_

    def __repr__(self):
        return f"<{self.type} {self.node}>"

class IntExpr(Expr):
    @classmethod
    def make(cls, val: tp.Any) -> IntExpr:
        if isinstance(val, IntExpr):
            return val
        if isinstance(val, Expr):
            if val.T is irT.Int:
                return val
            else:
                raise ValueError(f"Expected int or Lit, got {val}")
        try:
            val = int(val)
            return IntExpr(ir.Lit(val, irT.Int), irT.Int)
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
    @classmethod
    def make(cls, val: tp.Any) -> BoolExpr:
        if isinstance(val, BoolExpr):
            return val
        if isinstance(val, Expr):
            if val.T is irT.Bool:
                return val
            else:
                raise ValueError(f"Expected bool or Lit, got {val}")
        if isinstance(val, (bool, int)):
            val = bool(val)
            return BoolExpr(ir.Lit(val, irT.Bool), irT.Bool)
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

class CellIdxExpr(Expr): ...


def make_lambda(fn: tp.Callable[[TExpr], VExpr], paramT: irT.Type_) -> 'LambdaExpr[TExpr, VExpr]':
    bv_node = ir._BoundVarPlaceholder()
    bv_expr = tp.cast(paramT, wrap(bv_node, paramT))
    ret_expr = fn(bv_expr)
    lambda_node = ir._LambdaPlaceholder(bv_node, ret_expr.node, paramT)
    return tp.cast(LambdaExpr, wrap(lambda_node, irT.ArrowT(paramT, ret_expr.T)))

def make_lambda_dict(fn: tp.Callable[[KExpr, VExpr], TExpr], keyT: irT.Type_, valT: irT.Type_) -> 'LambdaExpr[irT.TupleT[KExpr, VExpr], TExpr]':
    bv_node = ir._BoundVarPlaceholder()
    paramT = irT.TupleT(keyT, valT)
    bv_expr = tp.cast(paramT, wrap(bv_node, paramT))
    bv_k_expr = bv_expr[0]
    bv_v_expr = bv_expr[1]
    ret_expr = fn(bv_k_expr, bv_v_expr)
    lambda_node = ir._LambdaPlaceholder(bv_node, ret_expr.node, paramT)
    return tp.cast(LambdaExpr, wrap(lambda_node, irT.ArrowT(paramT, ret_expr.T)))

class ListExpr(Expr, tp.Generic[TExpr]):
    @property
    def elem_type(self) -> irT.Type_:
        return tp.cast(irT.ListT, self.T).elemT

    def windows(self, size: IntOrExpr, stride: IntOrExpr=1) -> 'ListExpr[ListExpr[TExpr]]':
        size = IntExpr.make(size)
        stride = IntExpr.make(stride)
        node = ir.ListWindow(self.node, size.node, stride.node)
        T = irT.ListT(irT.ListT(self.elem_type))
        return tp.cast(ListExpr[ListExpr[TExpr]], wrap(node, T))

    def map(self, fn: tp.Callable[[TExpr], TExpr]) -> 'ListExpr[TExpr]':
        lambda_expr = make_lambda(fn, self.elem_type)
        node = ir.Map(self.node, lambda_expr.node)
        retT = irT.ListT(lambda_expr.res_type)
        return tp.cast(ListExpr, wrap(node, retT))

    def sum(self) -> IntExpr:
        node = ir.SumReduce(self.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def forall(self, fn: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        lambda_expr = make_lambda(fn, self.elem_type)
        node = ir.Forall(self.node, lambda_expr.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def exists(self, fn: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        lambda_expr = make_lambda(fn, self.elem_type)
        node = ir.Exists(self.node, lambda_expr.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def all(self, fn: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        return self.forall(fn)

    def any(self, fn: tp.Callable[[TExpr], BoolExpr]) -> BoolExpr:
        return self.exists(fn)


    def distinct(self) -> BoolExpr:
        node = ir.Distinct(self.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def concat(self, vals: 'ListExpr[TExpr]') -> 'ListExpr[TExpr]':
        if self.elem_type is not vals.elem_type:
            raise TypeError(f"Cannot concat lists with different element types: {self.elem_type} and {vals.elem_type}")
        node = ir.ListConcat(self.node, vals.node)
        return tp.cast(ListExpr[TExpr], wrap(node, self.T))

    def contains(self, elem: TExpr) -> 'BoolExpr':
        node = ir.ListContains(self.node, elem.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __getitem__(self, idx: IntOrExpr) -> TExpr:
        idx = IntExpr.make(idx)
        node = ir.ListGet(self.node, idx.node)
        return tp.cast(TExpr, wrap(node, self.elem_type))

    def __len__(self) -> IntExpr:
        node = ir.ListLength(self.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def __iter__(self) -> tp.Iterator[TExpr]:
        raise ValueError("ListExpr is not iterable at python runtime")

    # TODO
    #def __len__(self) -> IntExpr:
    #    node = ir.ListLen(self.node)
    #    return tp.cast(IntExpr, wrap(node, irT.Int))


class DictExpr(Expr, tp.Generic[KExpr, VExpr]):
    @property
    def key_type(self) -> irT.Type_:
        return tp.cast(irT.DictT, self.T).keyT

    @property
    def val_type(self) -> irT.Type_:
        return tp.cast(irT.DictT, self.T).valT

    def map(self, fn: tp.Callable[[KExpr, VExpr], TExpr]) -> 'DictExpr[KExpr, TExpr]':
        lambda_expr = make_lambda_dict(fn, self.key_type, self.val_type)
        node = ir.DictMap(self.node, lambda_expr.node)
        return tp.cast(DictExpr[KExpr, TExpr], wrap(node, irT.DictT(self.key_type, lambda_expr.res_type)))

    def forall(self, fn: tp.Callable[[KExpr, VExpr], BoolExpr]) -> BoolExpr:
        lambda_expr = make_lambda_dict(fn, self.key_type, self.val_type)
        node = ir.Forall(self.node, lambda_expr.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def __invert__(self) -> 'DictExpr[KExpr, VExpr]':
        if self.val_type is not irT.Bool:
            raise ValueError(f"Cannot invert non-bool dict")
        # Map the invert over the expression
        map_node = self.map(lambda k, v: ~v)
        return tp.cast(DictExpr[KExpr, VExpr], wrap(map_node.node, self.T))

    def __getitem__(self, key: KExpr) -> VExpr:
        # If getitem is a list, perform a Map over the keys
        if isinstance(key, ListExpr):
            return key.map(lambda k: self[k])
        elif key.T is self.key_type:
            node = ir.DictGet(self.node, key.node)
            return tp.cast(VExpr, wrap(node, self.val_type))
        else:
            raise ValueError(f"key must be Type {self.key_type} or [{self.key_type}], but is {key.T}")

    def __len__(self) -> IntExpr:
        node = ir.DictLength(self.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))


class LambdaExpr(Expr, tp.Generic[TExpr, VExpr]):
    @property
    def arg_type(self) -> irT.Type_:
        return tp.cast(irT.ArrowT, self.T).argT

    @property
    def res_type(self) -> irT.Type_:
        return tp.cast(irT.ArrowT, self.T).resT

    def __repr__(self):
        return f"lambda {self.arg_type}: {self.res_type}"

class GridExpr(Expr, tp.Generic[TExpr]):
    @property
    def value_type(self) -> irT.Type_:
        return tp.cast(irT.GridT, self.T).valueT

    @property
    def nR(self) -> IntExpr:
        node = ir.GridNumRows(self.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    @property
    def nC(self) -> IntExpr:
        node = ir.GridNumCols(self.node)
        return tp.cast(IntExpr, wrap(node, irT.Int))

    def C(self) -> ListExpr[TExpr]:
        return self.enumerate("C")

    def enumerate(self, mode: str="C") -> ListExpr[TExpr]:
        node = ir.GridEnumNode(self.nR.node, self.nC.node, mode)
        return tp.cast(ListExpr[TExpr], wrap(node, irT.ListT(self.value_type)))

    def forall(self, fn: tp.Callable[[TExpr], BoolExpr], mode: str="C") -> BoolExpr:
        lambda_expr = make_lambda(fn, self.value_type)
        node = ir.Forall(self.enumerate(mode), lambda_expr.node)
        return tp.cast(BoolExpr, wrap(node, irT.Bool))

    def rows(self) -> ListExpr[ListExpr[TExpr]]:
        return self.enumerate("Rows")

    def cols(self) -> ListExpr[ListExpr[TExpr]]:
        return self.enumerate("Cols")

    # as_grid=True means return a list of grids, as_grid=False means return a list of lists of elems
    def tiles(self, size: tp.Tuple[IntOrExpr, IntOrExpr], stride: tp.Tuple[IntOrExpr, IntOrExpr], as_grid: bool=False) -> ListExpr[GridExpr[TExpr]]:
        size_r = IntExpr.make(size[0])
        size_c = IntExpr.make(size[1])
        stride_r = IntExpr.make(stride[0])
        stride_c = IntExpr.make(stride[1])
        node = ir.GridWindowNode(self.node, size_r.node, size_c.node, stride_r.node, stride_c.node)
        T = irT.ListT(irT.GridT(self.value_type, "C"))
        return tp.cast(ListExpr[GridExpr[TExpr]], wrap(node, T))

    def flat(self):
        node = ir.GridFlatNode(self.node)
        T = irT.ListT(self.value_type)
        return tp.cast(ListExpr[TExpr], wrap(node, T))

    # Ergonomic: get row i or col j as a list of cells using existing enumeration
    def row(self, i: IntOrExpr) -> ListExpr[TExpr]:
        i = IntExpr.make(i)
        # rows() returns a list of lists; index into it
        return self.rows()[i]

    def col(self, j: IntOrExpr) -> ListExpr[TExpr]:
        j = IntExpr.make(j)
        return self.cols()[j]

    def cell_at(self, i: IntOrExpr, j: IntOrExpr) -> TExpr:
        # Cell at row i, col j can be expressed by indexing row i's list at j
        return self.row(i)[IntExpr.make(j)]

def wrap(node: ir.Node, T: irT.Type_) -> Expr:
    if T is irT.Int:
        return IntExpr(node, T)
    if T is irT.Bool:
        return BoolExpr(node, T)
    if T is irT.CellIdxT:
        return CellIdxExpr(node, T)
    if isinstance(T, irT.ListT):
        return ListExpr(node, T)
    if isinstance(T, irT.DictT):
        return DictExpr(node, T)
    if isinstance(T, irT.ArrowT):
        return LambdaExpr(node, T)
    if isinstance(T, irT.GridT):
        return GridExpr(node, T)
    raise ValueError(f"Unknown type: {T}")
