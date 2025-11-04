from .. import ast, ir, ir_types as irT
import typing as tp
from enum import Enum as _Enum

def count(dom: ast.DomainExpr, pred: tp.Callable) -> ast.IntExpr:
    return len(dom.restrict(pred))

def all_same(func) -> ast.BoolExpr:
    ...

def Fin(n:ast.IntOrExpr)-> ast.IterDomainExpr:
    return ast.IterDomainExpr.make(n)

def Range(lo: ast.IntOrExpr, hi: ast.IntOrExpr) -> ast.IterDomainExpr:
    return Fin(hi-lo).tabulate(lambda i: i+lo).image

def Enum(*labels: str) -> tp.Tuple[ast.DomainExpr, _Enum]:
    if not all(isinstance(str, l) for l in labels):
        raise ValueError("Labels must be strings")
    enum_val = _Enum('_custom_enum', [(l, i) for i, l in enumerate(labels)])
    dom = Fin(len(labels))
    return dom, enum_val

def sum(func: ast.FuncExpr) -> ast.IntExpr:
    if not (isinstance(func, ast.FuncExpr) and func.elemT == irT.Int):
        raise ValueError(f"Expected FuncExpr[IntExpr], got {func}")
    node = ir.SumReduce(func.node)
    return tp.cast(ast.IntExpr, ast.wrap(node, irT.Int))

def distinct(func: ast.FuncExpr) -> ast.BoolExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {func}")
    node = ir.Distinct(func.node)
    return tp.cast(ast.BoolExpr, ast.wrap(node, irT.Bool))