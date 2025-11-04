from .. import ir, ast, ir_types as irT
import typing as tp
from . import count

def OptT(T: irT.Type_) -> irT.Type_:
    return irT.SumT(irT.UnitType, T)

def Optional(dom: ast.DomainExpr):
    if not isinstance(dom, ast.DomainExpr):
        raise ValueError(f"Expected DomainExpr, got {type(dom)}")
    # T = Unit | dom
    T = OptT(dom.T.carT)
    node = ir.DisjUnion(ir.Unit(), dom.node)
    return tp.cast(ast.SumExpr, ast.wrap(node, T))

def _check_optT(T: irT.Type_):
    if not isinstance(T, irT.SumT):
        raise ValueError(f"Expected SumT, got {type(T)}")
    if T.elemTs[0] is not irT.UnitType or len(T.elemTs) != 2:
        raise ValueError(f"Expected SumT of Unit and dom, got {T}")
    return T.elemTs[1]

def fold(val: ast.SumExpr, on_none: ast.Expr, on_some: tp.Callable[[ast.Expr], ast.Expr]) -> ast.Expr:
    if not isinstance(val, ast.SumExpr):
        raise ValueError(f"Expected SumExpr, got {type(val)}")
    if not isinstance(on_none, ast.Expr):
        raise ValueError(f"Expected Expr, got {type(on_none)}")
    if not isinstance(on_some, ast.LambdaExpr):
        raise ValueError(f"Expected LambdaExpr, got {type(on_some)}")
    sumT = val.T
    argT = _check_optT(sumT)
    resT = on_none.T
    some_lam_expr = ast.make_lambda(on_some, argT)
    if some_lam_expr.resT != resT:
        raise ValueError(f"Expected LambdaExpr with result type {resT}, got {some_lam_expr.res_type}")
    none_lam_expr = ast.make_lambda(lambda _: on_none, irT.UnitType)
    node = ir.Match(val.node, ir.TupleLit(none_lam_expr.node, some_lam_expr.node))
    return tp.cast(ast.Expr, ast.wrap(node, resT))

def count_some(func: ast.FuncExpr) -> ast.IntExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {type(func)}")
    funcT = tp.cast(irT.ArrowT, func.T)
    _check_optT(funcT.resT)
    return len(func.domain.restrict(lambda i: func(i).match(lambda _: False, lambda _: True)))
