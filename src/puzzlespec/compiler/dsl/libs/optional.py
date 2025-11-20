from .. import ir, ast
import typing as tp

def OptT(T: ir.Type) -> ir.Type:
    return ir.SumT(ir.UnitT(), T)

def Optional(dom: ast.DomainExpr):
    if not isinstance(dom, ast.DomainExpr):
        raise ValueError(f"Expected DomainExpr, got {type(dom)}")
    # domT = Universe(Unit) | dom
    T = ir.DomT.make(carT=ir.SumT(ir.UnitT(), dom.carT), fin=dom.T.fin, ord=dom.T.ord)
    univ = ir.Universe(ir.DomT.make(carT=ir.UnitT(),fin=True, ord=True))
    node = ir.DisjUnion(T, univ, dom.node)
    return tp.cast(ast.SumExpr, ast.wrap(node))

def _check_optT(T: ir.Type):
    if not isinstance(T, ir.SumT):
        raise ValueError(f"Expected SumT, got {type(T)}")
    if not isinstance(T[0], ir.UnitT) or len(T) != 2:
        raise ValueError(f"Expected SumT of Unit and T, got {T}")
    return T[1]

def fold(val: ast.SumExpr, on_none: ast.Expr, on_some: tp.Callable[[ast.Expr], ast.Expr]) -> ast.Expr:
    return val.match(lambda _: on_none, on_some)

def count_some(func: ast.FuncExpr) -> ast.IntExpr:
    if not isinstance(func, ast.FuncExpr):
        raise ValueError(f"Expected FuncExpr, got {type(func)}")
    _check_optT(func.T.retT)
    some_dom = func.domain.restrict(lambda i: func(i).match(lambda _: False, lambda _: True))
    return some_dom.size
