from __future__ import annotations
import typing as tp
from functools import cached_property

from . import ir, ast
#from ..passes.analyses.type_check import get_rawT
#from ..passes.analyses.nd_axis import get_info, DomInfo

def fin(n: ast.IntOrExpr):
    n = ast.IntExpr.make(n).refine(lambda i: i>0)
    T = ir.DomT(carT=ir.IntT(), ord=True)
    node = ir.Fin(T, n.node)
    return OrdDomainExpr(node)

# ND Types
class OrdDomainType(ast.DomainType):
    def __post_init__(self):
        super().__post_init__()
        if not (isinstance(self._node, ir.DomT) and self._node.ord):
            raise ValueError(f"Expected Ord, got {self.node}")

   

def _make_slice(N: ast.IntExpr, s: slice):
    lo, hi, step = s.start, s.stop, s.step
    if lo is None:
        lo = 0
    if hi is None:
        hi = N
    if step is None:
        step = 1
    lo, hi, step = tuple(ast.IntExpr.make(_v) for _v in (lo, hi, step))
    return lo, hi, step

class OrdDomainExpr(ast.DomainExpr):
    def __init__(self, dom: ir.Node):
        if not isinstance(ast.wrapT(dom.T), OrdDomainType):
            raise NotImplementedError()
        super().__init__(dom)
    
    def slice(self, lo: ast.IntExpr, hi: ast.IntExpr, step: ast.IntExpr) -> OrdDomainExpr:
        lo, hi, step = ast.IntExpr.make(lo), ast.IntExpr.make(hi), ast.IntExpr.make(step)
        node = ir.Slice(self.T._node, self.node, lo.node, hi.node, step.node)
        return OrdDomainExpr(node)

    def elemAt(self, idx: ast.IntOrExpr) -> ast.IntExpr:
        idx = ast.IntExpr.make(idx)
        node = ir.ElemAt(self.T.carT._node, self.node, idx.node)
        return ast.wrap(node)

    # Exact windows
    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1, _exact=True) -> OrdDomainExpr:
        if not _exact:
            raise NotImplementedError()
        size = ast.IntExpr.make(size)
        stride = ast.IntExpr.make(stride)
        #[0,1,2,3,4]
        #5,2,2
        #[0,1], [2,3], [4]
        if _exact:
            dom = fin((self.size-(size-stride))/stride)
        else:
            dom = fin((self.size+1-(size-stride))//stride)
        wins = dom.map(
            lambda i: self.slice(lo=i*stride, hi=i*stride+size, step=1), _inj=True
        ).image
        assert isinstance(wins.T.carT, ast.DomainType)
        return wins

    def map(self, fn: tp.Callable, _inj=False) -> NDArrayExpr:
        func = super().map(fn, _inj=_inj)
        return ArrayExpr(func.node)
    
    def __getitem__(self, idx: tp.Any) -> OrdDomainExpr | ast.IntExpr:
        if isinstance(idx, slice):
            lo, hi, step = _make_slice(self.size, idx)
            return self.slice(lo, hi, step)
        elif isinstance(idx, (int, ast.IntExpr)):
            idx = ast.IntExpr.make(idx)
            return self.elemAt(idx)
        else:
            return super().__getitem__(idx)

class ArrayExpr(ast.FuncExpr):
    def __post_init__(self):
        super().__post_init__()
        if self.domain.T.is_ord is not True:
            raise ValueError("Array's must have ord domains")

    @property
    def domain(self) -> OrdDomainExpr:
        return OrdDomainExpr(super().domain.node)

    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> ArrayExpr:
        wins = self.domain.windows(size, stride) # Array[Array]
        return wins.map(lambda win: win.map(lambda i: self[i]))

    def __getitem__(self, k: tp.Any) -> ast.Expr:
        if isinstance(k, (int, ast.IntExpr)):
            k = ast.IntExpr.make(k)
            return self.apply(self.domain.elemAt(k))
        else:
            dom = self.domain[k]
            return dom.map(lambda i: self(i), _inj=True)


class NDDomainType(ast.DomainType):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, ir.NDDomT):
            raise ValueError(f"Expected NDDomT, got {self.node}")

    @property
    def axes(self):
        return self._node.axes

    @property
    def rank(self):
        return len(self.axes)

    @property
    def num_factors(self):
        return len(self._node.factors)

    @property
    def is_ord(self) -> bool:
        return True

# Cart product of 3 kinds of domains
# 1) 'ordered domain'
# 2) singleton domain 
# 3) non-ordered domain (like an Enum) (Not yet implemented)

class NDDomainExpr(ast.DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        assert isinstance(self.T._node, ir.NDDomT)

    @cached_property
    def T(self) -> NDDomainType:
        return NDDomainType(self.node.T)

    @cached_property
    def axes(self):
        return self.T.axes

    @cached_property
    def rank(self):
        return self.T.rank

    @cached_property
    def base_doms(self):
        return tuple(self.dom_proj(i) for i in range(self.T.num_factors))

    @cached_property
    def shape_doms(self) -> tp.Tuple[OrdDomainExpr]:
        return tuple(self.base_doms[axis] for axis in self.axes)
    
    @cached_property
    def shape(self):
        return tuple(shape_dom.size for shape_dom in self.shape_doms)

    def dom_proj(self, i: int):
        assert i in range(self.T.num_factors)
        node = ir.DomProj(self.T._node.factors[i], self.node, i)
        return ast.wrap(node)

    def _create_base(self, *sdoms) -> tp.Tuple[ast.DomainExpr]:
        sdom_dict = {a:sdom for a, sdom in zip(self.axes, sdoms)}
        bdoms = list(self.base_doms)
        for a, sdom in sdom_dict.items():
            bdoms[a] = sdom
        return tuple(bdoms)

    def __getitem__(self, vals: tp.Any) -> NDArrayExpr:
        if not isinstance(vals, tuple):
            return super().__getitem__(vals)
        if len(vals) != self.rank:
            raise ValueError(f"Too many indices. Needs {self.rank}, but got {len(vals)}")
        sdoms: tp.List[ast.DomainExpr] = []
        for v, dom in zip(vals, self.shape_doms):
            if isinstance(v, (int, ast.IntExpr)):
                sdom = dom[v].singleton
            else:
                sdom = dom[v]
            sdoms.append(sdom)
        bdoms = self._create_base(*sdoms)
        return nd_cartprod(*bdoms)

    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> NDArrayExpr:
        if self.rank != 1:
            raise ValueError("Must be rank 1 for windows")
        return self.tiles((size,), (stride,))

def nd_cartprod(*doms: ast.DomainExpr) -> NDDomainExpr:
    assert all(dom.T.is_ord for dom in doms)
    if all(dom.T.is_singleton for dom in doms):
        return ast.cartprod(*doms)
    axes = []
    bdoms = []
    bo = 0
    for dom in doms:
        if isinstance(dom, NDDomainExpr):
            bdoms += dom.base_doms
            axes += [bo + a for a in dom.axes]
            bo += dom.T.num_factors
        elif dom.T.is_singleton:
            bdoms.append(dom)
            bo +=1
        else:
            axes.append(len(bdoms))
            bdoms.append(dom)
            bo +=1
    T = ir.NDDomT(
        *(dom.T._node for dom in bdoms),
        axes=tuple(axes)
    )
    node = ir.CartProd(
        T,
        *(dom.node for dom in bdoms)
    )
    return NDDomainExpr(node)


# Func[NDDom -> T]
class NDArrayExpr(ast.FuncExpr):
    def __post_init__(self):
        super().__post_init__()
        assert isinstance(self.domain, NDDomainExpr)
    
    @property
    def axes(self):
        return self.domain.axes

    @property
    def rank(self):
        return self.domain.rank

    @cached_property
    def domain(self) -> NDDomainExpr:
        return NDDomainExpr(self.T._node.dom)

    def __getitem__(self, val: tp.Any) -> NDArrayExpr:
        dom = self.domain[val]
        return super().__getitem__(dom)