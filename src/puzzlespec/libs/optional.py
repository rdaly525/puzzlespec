from ..compiler.dsl import ast, ir, utils
import typing as tp

def optional(T: ast.TExpr) -> ast.TExpr:
    sumT = ir.SumT(ir.UnitT(), T.node)
    return ast.SumType(sumT)

def optional_dom(dom: ast.DomainExpr) -> ast.DomainExpr:
    if not isinstance(dom, ast.DomainExpr):
        raise ValueError(f"Expected DomainExpr, got {type(dom)}")
    return ast.Unit.U + dom

def _check_optT(T: ir.Type):
    if not utils._is_kind(T, ir.SumT):
        raise ValueError(f"Expected SumT, got {type(T)}")
    if not utils._is_kind(T[0], ir.UnitT) or len(T) != 2:
        raise ValueError(f"Expected SumT of Unit and T, got {T}")
    return T[1]

def fold(val: ast.SumExpr, on_none: ast.Expr, on_some: tp.Callable[[ast.Expr], ast.Expr]) -> ast.Expr:
    return val.match(lambda _: on_none, on_some)

def count_some(func: ast.FuncExpr) -> ast.IntExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {type(func)}")
    arrT = func.T._rawT
    _check_optT(arrT.resT)
    some_dom = func.domain.restrict(lambda i: func(i).match(lambda _: False, lambda _: True))
    return some_dom.size
