from __future__ import annotations
import typing as tp
range_ = range
from ..compiler.dsl import ir, ast, ast_nd as nd
from ..compiler.dsl.ast_nd import fin

#def affine(dom: nd.OrdDomainExpr, a: ast.IntExpr, b: ast.IntExpr) -> nd.OrdDomainExpr:
#    if not isinstance(dom, nd.OrdDomainExpr):
#        raise ValueError("Must be seq")
#    a, b = ast.IntExpr.make(a), ast.IntExpr(b)
#    node = ir.Affine(dom.T.node, dom.node, a.node, b.node)
#    return OrdDomainExpr(node)


def nd_dom(shape: tp.Tuple[ast.IntOrExpr]):
    return nd.nd_cartprod(*(fin(n) for n in shape))

def range(*args: ast.IntOrExpr) -> nd.NDDomainExpr:
    if len(args) not in (1,2,3):
        raise ValueError("Range expects 1-3 args")
    if len(args) == 1:
        return fin(args[0])
    if len(args) == 2:
        lo, hi, step = args[0], args[1], 1
    if len(args) == 3:
        lo, hi, step = args
    lo, hi, step = tuple(ast.IntExpr.make(v) for v in (lo, hi, step))
    node = ir.Range(ir.DomT(ir.IntT(), True), lo.node, hi.node, step.node)
    return ast.wrap(node)

ArrOrDom = tp.Union[nd.NDDomainExpr, nd.NDArrayExpr]

#def windows(dom: ArrOrDom, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> nd.NDArrayExpr:
#    return tiles(dom, (size,), (stride,))

def tiles(ndom: ArrOrDom, size: tp.Tuple[ast.IntOrExpr, ...], stride: tp.Tuple[ast.IntOrExpr, ...]=None) -> nd.NDArrayExpr:
    if isinstance(ndom, nd.NDArrayExpr):
        dom_tiles = tiles(ndom.domain, size, stride)
        return dom_tiles.map(
            lambda tile_dom: ndom[tile_dom]
        )
    if not isinstance(ndom, nd.NDDomainExpr):
        raise ValueError()
    rank = ndom.rank
    if stride == None:
        stride = [1 for _ in range_(rank)]
    if len(size) != rank or len(stride) != rank:
        raise ValueError(f"Expected size and stride for all dimensions ({rank}), got {size} and {stride}")    
    strides = [ast.IntExpr.make(s) for s in stride]
    sizes = [ast.IntExpr.make(s) for s in size]
    odoms = []
    for size, stride, dom in zip(sizes, strides, ndom.shape_doms):
        odom = fin((dom.size-(size-stride))/stride)
        odoms.append(odom)
    odom = nd.nd_cartprod(*odoms)
    def lam(oidx: ast.TupleExpr, ndom=ndom):
        slices = []
        for oi, size, stride in zip(oidx, sizes, strides):
            slices.append(slice(oi*stride, oi*stride+size))
        return ndom[*slices]
    return odom.map(lam, inj=True).image

def slices(dom: ArrOrDom, i: int) -> nd.NDDomainExpr | nd.NDArrayExpr:
    if isinstance(dom, nd.NDArrayExpr):
        s = slices(dom.domain, i)
        return s.map(lambda slice_dom: dom[slice_dom], inj=True)
    elif isinstance(dom, nd.NDDomainExpr):
        if i not in range_(dom.rank):
            raise ValueError("Invalid slices")
        domk = dom.shape_doms[i]
        rank = dom.rank
        def lam(idx: ast.IntExpr):
            slices = [slice(None) for _ in range_(rank)]
            slices[i] = idx
            slice_dom = dom[*slices]
            return slice_dom
        dom = domk.map(lam, inj=True).image
        return dom

def rows(dom: ArrOrDom) -> nd.NDArrayExpr:
    if dom.rank != 2:
        raise ValueError(f"Expected 2D, got {dom.rank}D")
    return slices(dom, 0)

def cols(dom: ArrOrDom) -> nd.NDArrayExpr:
    if dom.rank != 2:
        raise ValueError(f"Expected 2D array, got {dom.rank}D")
    return slices(dom, 1)
