from ..compiler.dsl import ast, ir, utils
import typing as tp
from ..compiler.passes.analyses.getter import get_closed_vars
from ..compiler.passes.transforms.resolve_vars import close_bound_vars

#def var(sort: ast.TExpr, name=None, **kwargs):
#    metadata = frozenset(kwargs.items())
#    var_node = ir.VarHOAS(sort.node, name, metadata=metadata)
#    return ast.wrap(var_node)

def param(sort: ast.TExpr, name=None):
    return var(sort=sort, name=name, role='P')

def gen_var(sort: ast.TExpr, name=None):
    return var(sort=sort, name=name, role='G')

def decision_var(sort: ast.TExpr, name=None):
    return var(sort=sort, name=name, role='D')

_cnt = 0
def var(
    dom: ast.TExpr | ast.DomainExpr,
    name: tp.Optional[str]=None, 
    indices: tp.Optional[tp.Tuple[ast.Expr, ...]]=None,
    **kwargs
) -> ast.Expr:
    metadata = frozenset(kwargs.items())
    global _cnt
    if name is None:
        name = f"v{_cnt}"
        _cnt +=1
    err_prefix=f"ERROR In var {name}: "
    if isinstance(dom, ast.TExpr):
        dom = dom.U
    if not isinstance(dom, ast.DomainExpr):
        raise ValueError(f"{err_prefix}var type must be a Type or a refinement dom")
    if indices is None:
        indices = ()
        bv_exprs = ()
    elif not isinstance(indices, tp.Tuple):
        bv_exprs = (indices,)
    else:
        bv_exprs = indices
    bvs = [e.node for e in bv_exprs]
    if not all(isinstance(bv, ir.BoundVarHOAS) for bv in bvs):
        raise ValueError(f"{err_prefix}indices must be bound variables, got {indices}")
    if not all(e.T.is_ref is not None for e in bv_exprs):
        raise ValueError(f"{err_prefix}indices must be 'mapped' bound variables, got {indices}")
    
    dom_bvs = get_closed_vars(dom.node)
    if any(bv in dom_bvs for bv in bvs):
        raise ValueError(f"{err_prefix}refinement domain {dom} must only depend on {indices}, got {diff}")

    ## Do dependency analysis
    # indices = (i, j, k)
    # dom(i) and i.T must *only* depend on()
    # dom(j) and j.T must *only* depend on (i)
    # dom(k) and k.T must *only* depend on (i)
    # ...
    for i, cur_bv in enumerate(bv_exprs):
        i_dep_bvs = utils._get_bvs(cur_bv.T.node)
        pre_i_bvs = set(bvs[:i])
        diff = i_dep_bvs - pre_i_bvs
        if len(diff) > 0:
            raise ValueError(f"{err_prefix}indices[{i}] must only depend on {pre_i_bvs}, got {diff}")
    
    def make_sort(bvs: tp.Tuple[ir.BoundVarHOAS,...]) -> ir.Type:
        if len(bvs)==0:
            return ir.RefT(dom.T.carT.node, dom.node)
        bv0 = bvs[0]
        bv_dom = bv0.T.dom
        # THIS CURRENTLY DEPENDS ON BV0
        sort_nest = make_sort(bvs[1:])
        new_bv = ir.BoundVarHOAS(bv0.T.T, closed=False)
        new_sort_nest = utils._substitute(sort_nest, bv0, new_bv)
        new_sort_nest = close_bound_vars(new_sort_nest, new_bv)
        T = ir.FuncT(
            bv_dom,
            ir.LambdaTHOAS(
                new_bv,
                new_sort_nest
            )
        )
        return T
    full_sort = make_sort(bvs)
    var = ir.VarHOAS(full_sort, name=name, metadata=metadata)
    var = ast.wrap(var)
    # add dom constraint
    for e in bv_exprs:
        var = var(e)
    return var

def func_var(
    dom: tp.Optional[ast.DomainExpr],
    sort: ir.Type=None,
    codom: tp.Optional[ast.DomainExpr]=None,
    indices: tp.Tuple[ast.Expr]=None,
    name: tp.Optional[str]=None,
    **kwargs
):

    if indices is None:
        indices = ()
    return dom.map(lambda i: var(
        sort=sort,
        dom=codom,
        name=name,
        indices=indices + (i,),
        **kwargs
    ))

