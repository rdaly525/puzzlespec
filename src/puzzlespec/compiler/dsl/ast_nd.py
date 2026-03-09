from __future__ import annotations
import typing as tp
from functools import cached_property

from . import ir, ast

class IRIdxViewT(ir.ViewT):
    @classmethod
    def make_ast(cls, node: ir.Value):
        return IdxView(node)

    def pretty(self, pp):
        return "IdxViewT"

ir.NODE_PRIORITY[IRIdxViewT] = 0

class IRIndexView(ir.View):
    _numc=2
    def __init__(self, T: IRIdxViewT, idx_lam: ir.Value):
        super().__init__(T, idx_lam)

    def pretty(self, pp):
        Ts, ridx = pp.visit_children(self)
        return f"IdxView[{ridx}]"

    @property
    def idx_lam(self):
        return self._children[1]
ir.NODE_PRIORITY[IRIdxViewT] = 0

class IdxView(ast.ViewExpr):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self._node, IRIndexView):
            raise ValueError(f"Expected IdxViewT, got {type(self.node)}")
        self.shape_doms
   
    def promote(self, node: ir.Node):
        return NDDomainExpr(node)

    def promote_func(self, node: ir.Node):
        return NDArrayExpr(node)

    def as_dom(self):
        img = self.idx_lam.image
        return img.with_view(self)

    @classmethod
    def make(cls, lam: ast.FuncExpr):
        T = IRIdxViewT()
        node = IRIndexView(T, lam.node)
        return cls(node)

    @property
    def idx_lam(self) -> ast.FuncExpr:
        return ast.wrap(self._node.idx_lam)

    @property
    def shape_doms(self) -> tp.Tuple[ast.DomainExpr]:
        dom = self.idx_lam.domain
        if isinstance(dom.node, ir.CartProd):
            doms = []
            for d in dom.node._children[1:]:
                assert isinstance(d, ir.Fin)
                doms.append(ast.wrap(d))
        else:
            raise ValueError("Bad construction", type(dom.node))
        return tuple(doms)
 
    @property
    def shape(self):
        return tuple(d.size for d in self.shape_doms)

    @property
    def rank(self):
        return len(self.shape_doms)
    
def fin(n: ast.IntOrExpr) -> NDDomainExpr:
    n = ast.IntExpr.make(n)
    dom = n.fin()
    idx = ast.cartprod(dom).map(lambda i: i[0])
    view = IdxView.make(idx)
    return dom.with_view(view)

# None means [:]
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

class NDDomainExpr(ast.DomainExpr):
    def __post_init__(self):
        super().__post_init__()
        assert self.view is not None and isinstance(self.view, IdxView)

    @property
    def view(self) -> IdxView:
        return self.T.view

    @property
    def idx_lam(self) -> ast.FuncExpr:
        return self.view.idx_lam

    @cached_property
    def rank(self):
        return self.view.rank

    @cached_property
    def shape_doms(self) -> tp.Tuple[ast.DomainExpr]:
        return self.view.shape_doms
    
    @cached_property
    def shape(self):
        return tuple(shape_dom.size for shape_dom in self.shape_doms)

    def map(self, fn: tp.Callable | ast.FuncExpr, inj=False) -> ast.FuncExpr:
        func = super().map(fn, inj)
        return NDArrayExpr(func.node)

    def __getitem__(self, vals: tp.Any) -> ast.Expr:
        #if isinstance(vals, ast.DomainExpr):
        #    return super().__getitem__(vals)
        if not isinstance(vals, tuple):
            vals = (vals,)
        if len(vals) != self.rank:
            raise ValueError(f"Too many indices. Needs {self.rank}, but got {len(vals)}")
        cvals = []
        new_doms = []
        for v, sdom in zip(vals,self.shape_doms):
            if isinstance(v, (int, ast.IntExpr)):
                cvals.append(ast.IntExpr.make(v))
            elif isinstance(v, slice):
                lhs = _make_slice(sdom.size, v)
                if lhs is None:
                    new_doms.append(sdom)
                    cvals.append(lambda i: i)
                else:
                    lo, hi, step = lhs
                    new_dom = (hi-lo).ceildiv(step).fin().forget_view()
                    new_doms.append(new_dom)
                    cvals.append(lambda i: lo + i*step)
            else:
                raise NotImplementedError(f"Cannot handle {v} in indexing")
        # If no slices, return the element
        if len(new_doms)==0:
            elem = self.idx_lam(tuple(cvals))
            elem._raw_elem = True
            return elem
        # Else return a new ND domain
        # N -> T = (O -> T) @ (N -> O)
        def new_to_old(nidx):
            oidx = []
            ni = 0
            for v in cvals:
                if isinstance(v, ast.IntExpr):
                    oidx.append(v)
                else:
                    oidx.append(v(nidx[ni]))
                    ni +=1
            oidx = tuple(oidx)
            return oidx
        new_dom = ast.cartprod(*new_doms)
        nto = new_dom.map(new_to_old)
        new_idx = self.idx_lam @ nto
        img = IdxView.make(new_idx).as_dom()
        img._raw_elem = False
        return img 

def nd_cartprod(*doms: NDDomainExpr) -> NDDomainExpr:
    sdoms = []
    for dom in doms:
        sdoms.extend(dom.shape_doms)
    def prod(nidx: ast.TupleExpr):
        res = []
        i = 0
        for oi, dom in enumerate(doms):
            idx_lam = dom.view.idx_lam
            res.append(idx_lam(nidx[i:i+dom.rank]))
            i += dom.rank
        return ast.TupleExpr.make(tuple(res))
    inj = all(dom.view.idx_lam.known_inj for dom in doms)
    new_idx = ast.cartprod(*sdoms).map(prod, inj)
    view = IdxView.make(new_idx)
    return view.as_dom()

# Func[NDDom -> T]
class NDArrayExpr(ast.FuncExpr):
    def __post_init__(self):
        super().__post_init__()
        assert isinstance(self.domain, NDDomainExpr)
    
    @property
    def rank(self):
        return self.domain.rank

    @property
    def domain(self) -> NDDomainExpr:
        return super().domain

    @property
    def image(self) -> ast.DomainExpr:
        # I -> D
        # D -> T
        # I -> T = (D -> T) @ (I -> D)
        new_idx = self @ self.domain.idx_lam
        view = IdxView.make(new_idx)
        img = super().image
        return img.with_view(view)

    def __getitem__(self, val: tp.Any) -> ast.Expr | NDArrayExpr:
        if isinstance(val, ast.DomainExpr):
            return super().__getitem__(val)
        dom = self.domain[val]
        if hasattr(dom, '_raw_elem') and dom._raw_elem:
            return self(dom)
        else:
            return super().__getitem__(dom)


#class OrdDomainExpr(ast.DomainExpr):
#    def __post_init__(self):
#        super().__post_init__()
#        if not isinstance(self.T, ReIndexDomainType):
#            raise ValueError("Bad construciton")
#    
#    @property
#    def T(self) -> ReIndexDomainType:
#        return super().T
#
#    def slice(self, lo: ast.IntExpr, hi: ast.IntExpr, step: ast.IntExpr) -> OrdDomainExpr:
#        lo, hi, step = ast.IntExpr.make(lo), ast.IntExpr.make(hi), ast.IntExpr.make(step)
#        idx = (lo-hi)//step
#        node = ir.Slice(self.T.node, self.node, lo.node, hi.node, step.node)
#        return OrdDomainExpr(node)
#
#    def elemAt(self, idx: ast.IntOrExpr) -> ast.IntExpr:
#        idx = ast.IntExpr.make(idx)
#        return self.T.view.ridx(idx)
#        #node = ir.ElemAt(self.T.carT.node, self.node, idx.node)
#        ## TODO add guard
#        ##return ast.wrap(node).guard(fin(self.size).contains(idx))
#        #return ast.wrap(node)
#
#    # Exact windows
#    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1, exact=True) -> OrdDomainExpr:
#        if not exact:
#            raise NotImplementedError()
#        size = ast.IntExpr.make(size)
#        stride = ast.IntExpr.make(stride)
#        #[0,1,2,3,4]
#        #5,2,2
#        #[0,1], [2,3], [4]
#        if exact:
#            dom = ((self.size-(size-stride))/stride).fin()
#        else:
#            dom = ((self.size+1-(size-stride))//stride).fin()
#        wins = dom.map(
#            lambda i: self.slice(lo=i*stride, hi=i*stride+size, step=1), inj=True
#        ).image
#        assert isinstance(wins.T.carT, ast.DomainType)
#        return wins
#
#    def map(self, fn: tp.Callable, inj=False) -> NDArrayExpr:
#        func = super().map(fn, inj=inj)
#        return ArrayExpr(func.node)
#    
#    def __getitem__(self, idx: tp.Any) -> OrdDomainExpr | ast.IntExpr:
#        if isinstance(idx, slice):
#            lhs = _make_slice(self.size, idx)
#            if lhs is None:
#                return self
#            return self.slice(*lhs)
#        elif isinstance(idx, (int, ast.IntExpr)):
#            idx = ast.IntExpr.make(idx)
#            return self.elemAt(idx)
#        else:
#            return super().__getitem__(idx)
#
#
#class ArrayExpr(ast.FuncExpr):
#    def __post_init__(self):
#        super().__post_init__()
#        if not isinstance(self.domain, OrdDomainExpr):
#            raise ValueError("Array's must have ord domains")
#
#    @property
#    def domain(self) -> OrdDomainExpr:
#        return OrdDomainExpr(super().domain.node)
#
#
#    # Fin -> D
#    # D -> T
#    # Fin -> T
#    @property
#    def image(self) -> ast.DomainExpr:
#        resT = self.T._raw_resT
#        imgT = resT.DomT        
#        node = ir.Image(imgT.node, self.node)
#        if not self.known_inj:
#            return ast.wrap(node)
#
#        ridx = self @ self.domain.T.view.ridx
#        isoT = ast.IsoType.make(imgT, self.domain.T.view.T.B)
#        view = ir.IndexView(isoT.node, ridx.node)
#        viewT = ir.ViewT(imgT.node, view)
#        view_node = ir.Image(viewT, self.node)
#        return ast.wrap(view_node)
#
#    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> ArrayExpr:
#        wins = self.domain.windows(size, stride) # Array[Array]
#        return wins.map(lambda win: self[win])
#
#    def __getitem__(self, k: tp.Any) -> ast.Expr:
#        if isinstance(k, (int, ast.IntExpr)):
#            k = ast.IntExpr.make(k)
#            return self.apply(self.domain.elemAt(k))
#        else:
#            dom = self.domain[k]
#            return dom.map(lambda i: self(i), inj=True)
#
#
#class NDDomainType(ast.DomainType):
#    def __post_init__(self):
#        super().__post_init__()
#        if not self._is_nd:
#            raise ValueError(f"Expected ND, got {self.node}")
#
#    @property
#    def _nddom(self) -> ir.NDDomain:
#        caps = self._caps
#        assert len(caps)==1
#        nddom, = caps
#        return nddom
#
#    @cached_property
#    def axes(self):
#        nddom = self._nddom
#        axes = tuple(i for i, dom in enumerate(nddom.factors) if not ast.wrap(dom).T._is_squeezable)
#        return axes
#
#    @cached_property
#    def rank(self):
#        return len(self.axes)
#
#    @cached_property
#    def factors(self) -> tp.Tuple[ast.DomainExpr]:
#        nddom = self._nddom
#        return tuple(ast.wrap(dom) for dom in nddom.factors)
#
#    @property
#    def num_factors(self):
#        return len(self.factors)
#
#    def __getitem__(self, i: int):
#        assert isinstance(i, int) and i in range(self.num_factors)
#        return self.factors[i].T

