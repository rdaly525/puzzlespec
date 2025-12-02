from ..compiler.dsl import ast, ir
import typing as tp

def var(sort: ast.TExpr, name=None, **kwargs):
    metadata = frozenset(kwargs.items())
    var_node = ir.VarHOAS(sort.node, name, metadata=metadata)
    return ast.wrap(var_node)

def param(sort: ast.TExpr, name=None):
    return var(sort, name, role='P')

def gen_var(sort: ast.TExpr, name=None):
    return var(sort, name, role='G')

def decision_var(sort: ast.TExpr, name=None):
    return var(sort, name, role='D')

def enum(*labels: str, name: str=None) -> tp.Tuple[ast.EnumDomainExpr, ast._EnumAttrs]:
    expr = ast.EnumDomainExpr.make_from_labels(*labels, name=name)
    return expr, expr.members

def fin(n:ast.IntOrExpr)-> ast.SeqDomainExpr:
    n = ast.IntExpr.make(n)
    return n.fin()

def interval(lo: ast.IntOrExpr, hi: ast.IntOrExpr) -> ast.SeqDomainExpr:
    lo = ast.IntExpr.make(lo)
    hi = ast.IntExpr.make(hi)
    T = ir.DomT.make(ir.IntT(), fin=True, ord=True)
    return ast.wrap(ir.Range(T, lo.node, hi.node))

def range(*args: ast.IntOrExpr) -> ast.SeqDomainExpr:
    if len(args) ==0:
        raise ValueError("Range expects at least one argument")
    if len(args) == 1:
        return fin(args[0])
    if len(args) == 2:
        return interval(args[0], args[1])
    if len(args) == 3:
        raise NotImplementedError("Range with step is not implemented")
    raise ValueError("Range expects one to three arguments")

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
