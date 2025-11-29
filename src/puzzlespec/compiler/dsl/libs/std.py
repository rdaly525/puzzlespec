from .. import ast, ir
import typing as tp


def Func(gen: tp.Generator):
    ...

def Enum(*labels: str, name: str=None) -> tp.Tuple[ast.EnumDomainExpr, ast._EnumAttrs]:
    expr = ast.EnumDomainExpr.make_from_labels(*labels, name=name)
    return expr, expr.members

def Fin(n:ast.IntOrExpr)-> ast.SeqDomainExpr:
    n = ast.IntExpr.make(n)
    return n.fin()

def Range(lo: ast.IntOrExpr, hi: ast.IntOrExpr) -> ast.SeqDomainExpr:
    lo = ast.IntExpr.make(lo)
    hi = ast.IntExpr.make(hi)
    T = ir.DomT.make(ir.IntT(), fin=True, ord=True)
    return ast.wrap(ir.Range(T, lo.node, hi.node))

def sum(func: ast.FuncExpr) -> ast.IntExpr:
    if not (isinstance(func, ast.FuncExpr) and isinstance(func.elemT, ir.IntT)):
        raise ValueError(f"Expected FuncExpr[IntExpr], got {func}")
    node = ir.SumReduce(ir.BoolT(), func.node)
    return ast.IntExpr(node)

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
    return func.map(lambda v: pred(v).to_int()).sum()

def combinations(dom: ast.DomainExpr, r: int) -> ast.DomainExpr:
    ...
