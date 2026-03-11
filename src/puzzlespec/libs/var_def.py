from ..compiler.dsl import ast, ir
import typing as tp

_name_cnt = 0
def _func_var(
    kind : str,
    doms: tp.Tuple[ast.TExpr | ast.DomainExpr | tp.Callable],
    **kwargs
) -> ast.FuncExpr:
    assert kind in "ea"
    if len(doms)==0:
        raise ValueError("Must provide at least one domain for variables")
    name = kwargs.get('name', None)
    global _name_cnt
    if name is None:
        prefix = "v" if kind=='e' else 'p'
        name = f"{prefix}{_name_cnt}"
        _name_cnt +=1
    metadata = frozenset(kwargs.items())

    def make_sort(doms, bvs: tp.Tuple[ast.Expr, ...]=None):
        if len(doms)==0:
            return None
        if bvs is None:
            bvs = ()
        if isinstance(doms[0], (ast.TExpr, ast.DomainExpr)):
            dom = doms[0]
        else:
            assert isinstance(doms[0], tp.Callable)
            if len(bvs)==1:
                bv_tup = bvs[0]
            else:
                bv_tup = ast.TupleExpr.make(tuple(bvs))
            dom = ast._call_fn(doms[0], bv_tup)
        if isinstance(dom, ast.DomainExpr):
            T = dom.as_refT()
        else:
            T = dom
        bv = dom._bound_var()
        resT = make_sort(doms[1:], (*bvs, bv))
        if resT is None:
            return T.node
        return ir.PiTHOAS(
            argT=T.node,
            resT=resT,
            bv_name=bv.node.name
        )
    full_sort = make_sort(doms)
    var = ir.VarHOAS(full_sort, name=name, kind=kind, metadata=metadata)
    var = ast.wrap(var)
    return var

def func_var(
    *doms: ast.TExpr | ast.DomainExpr | tp.Callable,
    **kwargs
):
    return _func_var('e', doms, **kwargs)

def func_param(
    *doms: ast.TExpr | ast.DomainExpr | tp.Callable,
    **kwargs
):
    return _func_var('a', doms, **kwargs)

def var(
    dom: ast.DomainExpr | ast.TExpr,
    **kwargs
):
    return _func_var('e', (dom,), **kwargs)

def param(
    dom: ast.DomainExpr | ast.TExpr,
    **kwargs
):
    return _func_var('a', (dom,), **kwargs)
