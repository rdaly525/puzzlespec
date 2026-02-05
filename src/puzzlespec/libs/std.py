from ..compiler.dsl import ast, ast_nd, ir
from .var_def import var
import typing as tp


Nat = ast.Int.refine(lambda i: i>0)
Nat0 = ast.Int.refine(lambda i: i>=0)

def isqrt(v: ast.IntExpr, _name=None) -> ast.IntExpr:
    return Nat0.choose(lambda i: i*i==v)

def U(carT: ast.TExpr):
    return carT.U

def sum(func: ast.FuncExpr | tp.Iterable) -> ast.IntExpr:
    if isinstance(func, ast.FuncExpr):
        if not isinstance(func.T._raw_resT(), ir.IntT):
            raise ValueError(f"Expected FuncExpr[IntExpr], got {func}")
        return ast.IntExpr(ir.SumReduce(ir.IntT(), func.node))
    assert isinstance(tp.Iterable)
    vals = [ast.IntExpr.make(v).node for v in func]
    return ast.IntExpr(ir.Sum(ir.IntT(), *vals))

def prod(func: ast.FuncExpr | tp.Iterable) -> ast.IntExpr:
    if isinstance(func, ast.FuncExpr):
        if not isinstance(func.T._raw_resT(), ir.IntT):
            raise ValueError(f"Expected FuncExpr[IntExpr], got {func}")
        return ast.IntExpr(ir.ProdReduce(ir.IntT(), func.node))
    assert isinstance(tp.Iterable)
    vals = [ast.IntExpr.make(v).node for v in func]
    return ast.IntExpr(ir.Prod(ir.IntT(), *vals))

def all(func: ast.FuncExpr | tp.Iterable) -> ast.BoolExpr:
    if isinstance(func, ast.FuncExpr):
        if not isinstance(func.T._raw_resT(), ir.BoolT):
            raise ValueError(f"Expected FuncExpr[BoolExpr], got {func}")
        return func.forall()
    assert isinstance(func, tp.Iterable)
    vals = [ast.BoolExpr.make(v).node for v in func]
    return ast.BoolExpr(ir.Conj(ir.BoolT(), *vals))

def any(func: ast.FuncExpr | tp.Iterable) -> ast.BoolExpr:
    if isinstance(func, ast.FuncExpr):
        if not isinstance(func.T._raw_resT(), ir.BoolT):
            raise ValueError(f"Expected FuncExpr[BoolExpr], got {func}")
        return func.exists()
    assert isinstance(func, tp.Iterable)
    vals = [ast.BoolExpr.make(v).node for v in func]
    return ast.BoolExpr(ir.Disj(ir.BoolT(), *vals))

def distinct(func: ast.FuncExpr) -> ast.BoolExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {func}")
    node = ir.AllDistinct(ir.BoolT(), func.node)
    return ast.BoolExpr(node)

def all_same(func) -> ast.BoolExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {func}")
    node = ir.AllSame(ir.BoolT(), func.node)
    return ast.BoolExpr(node)

def count(func: ast.FuncExpr, pred: tp.Callable) -> ast.IntExpr:
    assert isinstance(func, ast.FuncExpr)
    return func.domain.restrict(lambda i: pred(func(i))).size
    #return func.map(lambda v: pred(v).to_int()).sum()

class _EnumAttrs:
    def __init__(self, enumT: ir.EnumT):
        assert isinstance(enumT, ir.EnumT)
        for label in enumT.labels:
            label_node = ir.Lit(enumT, val=label)
            label_expr = ast.EnumExpr(label_node)
            setattr(self, label, label_expr)

def enumT(*labels: str, name: str=None) -> ast.EnumType:
    if len(labels) == 0:
        raise NotImplementedError("cannot have a 0-label Enum")
    if len(set(labels)) != len(labels):
        raise ValueError("Labels must be unique")
    if name is None:
        name = "".join(labels)
    enumT = ir.EnumT(name, tuple(labels))
    return ast.EnumType(enumT)

def make_enum(*labels: str, name: str=None) -> tp.Tuple[ast.DomainExpr, _EnumAttrs]:
    if len(labels)==1:
        labels = [l for l in labels[0]]
    T = enumT(*labels, name=name)
    enum_attrs = _EnumAttrs(T.node)
    dom_node = ir.Universe(ir.DomT(T.node, ord=False))
    dom = ast.DomainExpr(dom_node)
    return dom, enum_attrs

