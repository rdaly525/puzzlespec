from __future__ import annotations
import typing as tp
from functools import cached_property

from . import ir, ast

# ND Types
#class OrdDomainType(ast.DomainType):
#    def __post_init__(self):
#        super().__post_init__()
#        ref_dom = self.ref_dom
#        if not (ref_dom is not None and isinstance(ref_dom.node, ir.EnumerableDomain)):
#            raise ValueError(f"Expected Enumerable Domain Type, got {self.node}")

def _make_slice(N: ast.IntExpr, s: slice):
    lo, hi, step = s.start, s.stop, s.step
    if lo is None and hi is None and step is None:
        return None
    if lo is None:
        lo = 0
    if hi is None:
        hi = N
    if step is None:
        step = 1
    lo, hi, step = tuple(ast.IntExpr.make(_v) for _v in (lo, hi, step))
    return lo, hi, step

class OrdDomainExpr(ast.DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        if not (self.T._is_enumerable and not self.T._is_squeezable):
            raise ValueError("Bad construciton")
    
    def slice(self, lo: ast.IntExpr, hi: ast.IntExpr, step: ast.IntExpr) -> OrdDomainExpr:
        lo, hi, step = ast.IntExpr.make(lo), ast.IntExpr.make(hi), ast.IntExpr.make(step)
        node = ir.Slice(self.T.node, self.node, lo.node, hi.node, step.node)
        return OrdDomainExpr(node)

    def elemAt(self, idx: ast.IntOrExpr) -> ast.IntExpr:
        idx = ast.IntExpr.make(idx)
        node = ir.ElemAt(self.T.carT.node, self.node, idx.node)
        # TODO add guard
        #return ast.wrap(node).guard(fin(self.size).contains(idx))
        return ast.wrap(node)

    # Exact windows
    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1, exact=True) -> OrdDomainExpr:
        if not exact:
            raise NotImplementedError()
        size = ast.IntExpr.make(size)
        stride = ast.IntExpr.make(stride)
        #[0,1,2,3,4]
        #5,2,2
        #[0,1], [2,3], [4]
        if exact:
            dom = ((self.size-(size-stride))/stride).fin()
        else:
            dom = ((self.size+1-(size-stride))//stride).fin()
        wins = dom.map(
            lambda i: self.slice(lo=i*stride, hi=i*stride+size, step=1), inj=True
        ).image
        assert isinstance(wins.T.carT, ast.DomainType)
        return wins

    def map(self, fn: tp.Callable, inj=False) -> NDArrayExpr:
        func = super().map(fn, inj=inj)
        return ArrayExpr(func.node)
    
    def __getitem__(self, idx: tp.Any) -> OrdDomainExpr | ast.IntExpr:
        if isinstance(idx, slice):
            lhs = _make_slice(self.size, idx)
            if lhs is None:
                return self
            return self.slice(*lhs)
        elif isinstance(idx, (int, ast.IntExpr)):
            idx = ast.IntExpr.make(idx)
            return self.elemAt(idx)
        else:
            return super().__getitem__(idx)

class ArrayExpr(ast.FuncExpr):
    def __post_init__(self):
        super().__post_init__()
        if not self.domain.T._is_enumerable:
            raise ValueError("Array's must have ord domains")

    @property
    def domain(self) -> OrdDomainExpr:
        return OrdDomainExpr(super().domain.node)

    @property
    def image(self) -> ast.DomainExpr:
        if not self.known_inj:
            raise NotImplementedError()
        resT = self.T._raw_resT
        imgT = resT.DomT
        cap = ast.wrap(ir.EnumerableDomain(imgT.DomT.node))
        node = ir.Image(imgT.refine(cap).node, self.node)
        img = ast.wrap(node)
        assert isinstance(img, OrdDomainExpr)
        return img

    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> ArrayExpr:
        wins = self.domain.windows(size, stride) # Array[Array]
        return wins.map(lambda win: self[win])

    def __getitem__(self, k: tp.Any) -> ast.Expr:
        if isinstance(k, (int, ast.IntExpr)):
            k = ast.IntExpr.make(k)
            return self.apply(self.domain.elemAt(k))
        else:
            dom = self.domain[k]
            return dom.map(lambda i: self(i), inj=True)


class NDDomainType(ast.DomainType):
    def __post_init__(self):
        super().__post_init__()
        if not self._is_nd:
            raise ValueError(f"Expected ND, got {self.node}")

    @property
    def _nddom(self) -> ir.NDDomain:
        caps = self._caps
        assert len(caps)==1
        nddom, = caps
        return nddom

    @cached_property
    def axes(self):
        nddom = self._nddom
        axes = tuple(i for i, dom in enumerate(nddom.factors) if not ast.wrap(dom).T._is_squeezable)
        return axes

    @cached_property
    def rank(self):
        return len(self.axes)

    @cached_property
    def factors(self) -> tp.Tuple[ast.DomainExpr]:
        nddom = self._nddom
        return tuple(ast.wrap(dom) for dom in nddom.factors)

    @property
    def num_factors(self):
        return len(self.factors)

    def __getitem__(self, i: int):
        assert isinstance(i, int) and i in range(self.num_factors)
        return self.factors[i].T

# Cart product of 3 kinds of domains
# 1) 'ordered domain'
# 2) singleton domain 
# 3) non-ordered domain (like an Enum) (Not yet implemented)

class NDDomainExpr(ast.DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        assert isinstance(self.T, NDDomainType)

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
        node = ir.DomProj(self.T[i].node, self.node, i)
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
    assert all(dom.T._is_enumerable for dom in doms)
    if all(dom.T._is_squeezable for dom in doms):
        return ast.cartprod(*doms)
    bdoms = []
    for dom in doms:
        if isinstance(dom, NDDomainExpr):
            bdoms.extend(dom.base_doms)
        else:
            bdoms.append(dom)
    factorTs = [dom.T for dom in bdoms]
    carT = ast.wrapT(ir.TupleT(*(T.carT.node for T in factorTs)))
    capND = ir.NDDomain(
        carT.DomT.DomT.node,
        *(dom.node for dom in bdoms),
    )
    T = carT.DomT.refine(ast.wrap(capND))
    assert isinstance(T, NDDomainType)
    node = ir.CartProd(
        T.node,
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

    @property
    def domain(self) -> NDDomainExpr:
        return super().domain

    @property
    def image(self) -> ast.DomainExpr:
        if not self.known_inj:
            return super().image
        carT = self.T._raw_resT
        imgT = carT.DomT
        # build NDDomain
        nddom = self.domain.T._nddom
        cap = ast.wrap(ir.NDDomain(imgT.DomT.node, *nddom.factors))
        node = ir.Image(imgT.refine(cap).node, self.node)
        img = ast.wrap(node)
        assert isinstance(img, NDDomainExpr)
        return img

    def __getitem__(self, val: tp.Any) -> NDArrayExpr:
        dom = self.domain[val]
        return super().__getitem__(dom)