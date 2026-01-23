from ..compiler.dsl import ast, ir
import typing as tp


_name_cnt = 0
def func_var(
    *doms: ast.TExpr | ast.DomainExpr | tp.Callable,
    **kwargs
) -> ast.FuncExpr:
    if len(doms)==0:
        raise ValueError("Must provide at least one domain for variables")
    name = kwargs.get('name', None)
    global _name_cnt
    if name is None:
        name = f"v{_name_cnt}"
        _name_cnt +=1
    metadata = frozenset(kwargs.items())

    doms = [dom.U if isinstance(dom, ast.TExpr) else dom for dom in doms]
    doms = [doms[0]] + [(lambda _,dom=dom: dom) if isinstance(dom, ast.DomainExpr) else (lambda indices,dom=dom: dom(*indices)) for dom in doms[1:]]
    assert isinstance(doms[0], ast.DomainExpr)
    assert all(isinstance(dom, tp.Callable) for dom in doms[1:])
    N = len(doms)
    def make_sort(doms, bvs: tp.Tuple[ast.Expr, ...]=None, tupT: ast.TupleType=None):
        if bvs is None:
            bvs = ()
        if tupT is None:
            tupT = ast.wrapT(ir.TupleT())
        dom = doms[0]
        if len(bvs)==0:
            assert len(doms)==N
            assert isinstance(doms[0], ast.DomainExpr)
        else:
            assert len(bvs) == len(tupT)
            bv_multi = tupT._bound_var()
            assert isinstance(dom, tp.Callable)
            lam_expr = ast.LambdaExpr.make(dom, bv_multi)
            dom = lam_expr.apply(bvs)
        if len(doms)==1:
            codom = dom
            assert isinstance(codom, ast.DomainExpr)
            T = ir.RefT(codom.T.carT.node, codom.node)
            return T
        else:
            bv_uni = dom._bv
            new_bvs = bvs + (bv_uni,)
            new_tupT = ast.wrapT(ir.TupleT(*tupT._node.elemTs, bv_uni.T._node))
            T = ir.FuncT(
                dom=dom.node,
                lamT = ir.PiTHOAS(
                    bv_uni.T.node,
                    make_sort(doms[1:], new_bvs, new_tupT),
                    bv_name=bv_uni.node.name
                )
            )
        return T
    full_sort = make_sort(doms)
    var = ir.VarHOAS(full_sort, name=name, metadata=metadata)
    var = ast.wrap(var)
    return var
    
def var(
    dom: ast.DomainExpr | ast.TExpr,
    **kwargs
):
    return func_var(dom, **kwargs)