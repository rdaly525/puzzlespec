from ..compiler.dsl import ast, ast_nd, ir
import typing as tp

def U(carT: ast.TExpr):
    return ast.DomainExpr(ir.Universe(ir.DomT(carT).node))

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
    T = enumT(*labels, name=name)
    enum_attrs = _EnumAttrs(T.node)
    dom_node = ir.Universe(ir.DomT(T.node))
    dom = ast.DomainExpr(dom_node)
    return dom, enum_attrs

