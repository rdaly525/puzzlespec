from .. import ast, ir, ir_types as irT
from .. import proof_lib as pf
import typing as tp
from enum import Enum as _Enum


def Enum(*labels: str, name: str=None) -> tp.Tuple[ast.EnumDomainExpr, ast._EnumAttrs]:
    expr = ast.EnumDomainExpr.make_from_labels(*labels, name=name)
    return expr, expr.members

def Fin(n:ast.IntOrExpr)-> ast.SeqDomainExpr:
    return ast.SeqDomainExpr.make(n)

def Range(lo: ast.IntOrExpr, hi: ast.IntOrExpr) -> ast.SeqDomainExpr:
    return Fin(hi-lo).map(lambda i: i+lo).image

def sum(func: ast.FuncExpr) -> ast.IntExpr:
    if not (isinstance(func, ast.FuncExpr) and func.elemT == irT.Int):
        raise ValueError(f"Expected FuncExpr[IntExpr], got {func}")
    node = ir.SumReduce(func.node)
    penv = pf.inference(node, func.penv)
    return tp.cast(ast.IntExpr, ast.wrap(node, penv))

def distinct(func: ast.FuncExpr) -> ast.BoolExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {func}")
    node = ir.AllDistinct(func.node)
    penv = pf.inference(node, func.penv)
    return tp.cast(ast.BoolExpr, ast.wrap(node, penv))

def all_same(func) -> ast.BoolExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {func}")
    node = ir.AllSame(func.node)
    penv = pf.inference(node, func.penv)
    return tp.cast(ast.BoolExpr, ast.wrap(node, penv))

def count(func: ast.FuncExpr, pred: tp.Callable) -> ast.IntExpr:
    return sum(func.map(lambda v: pred(v).ite(1,0)))

def combinations(dom: ast.DomainExpr, r: int) -> ast.DomainExpr:
    ...
