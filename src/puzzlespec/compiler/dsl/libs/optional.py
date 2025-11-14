from .. import ir, ast, ir_types as irT
import typing as tp

def OptT(T: irT.Type_) -> irT.Type_:
    return irT.SumT(irT.UnitType, T)

def Optional(dom: ast.DomainExpr):
    if not isinstance(dom, ast.DomainExpr):
        raise ValueError(f"Expected DomainExpr, got {type(dom)}")
    # domT = Universe(Unit) | dom
    node = ir.DisjUnion(ir.Universe(irT.UnitType), dom.node)
    return tp.cast(ast.SumExpr, ast.wrap(node))

def _check_optT(T: irT.Type_):
    if not isinstance(T, irT.SumT):
        raise ValueError(f"Expected SumT, got {type(T)}")
    if T.elemTs[0] is not irT.UnitType or len(T.elemTs) != 2:
        raise ValueError(f"Expected SumT of Unit and dom, got {T}")
    return T.elemTs[1]

def fold(val: ast.SumExpr, on_none: ast.Expr, on_some: tp.Callable[[ast.Expr], ast.Expr]) -> ast.Expr:
    return val.match(lambda _: on_none, on_some)

def count_some(func: ast.FuncExpr) -> ast.IntExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {type(func)}")
    funcT = tp.cast(irT.ArrowT, func.T)
    _check_optT(funcT.resT)
    some_dom = func.domain.restrict(lambda i: func(i).match(lambda _: False, lambda _: True))
    return some_dom.size
