from __future__ import annotations
import typing as tp

from . import ir, ast
import itertools as it

# NDDomain stores 4 things
# - Base: represents the 'storage'. This is fin(n0)xfin(n1)x...
# - shape: represents the set of axis. e.g., fin(m0)xfin(m2)x... 
# - embed: shape -> base
# - elem: Base -> elem. The 'values' of the storage

class NDDomType(ast.DomainType):
    def __post_init__(self):
        if not isinstance(self._node, ir.NDDomT):
            raise ValueError(f"Expected NDDomT, got {self.node}")

    @classmethod
    def make(cls, 
        base_doms: tp.Tuple[ast.DomainExpr, ...],
        shape_doms: tp.Tuple[ast.DomainExpr, ...]=None,
        embed: ast.LambdaExpr=None,
        elem: ast.LambdaExpr=None
    ) -> NDDomType:
        if shape_doms is None:
            shape_doms = base_doms
        assert all(isinstance(d.T, ast.DomainType) for d in base_doms)
        assert all(isinstance(d.T, ast.DomainType) for d in shape_doms)
        base_dom = ast.cartprod(*base_doms)
        shape_dom = ast.cartprod(*shape_doms)        
        if embed is None:
            embed = ast.LambdaExpr.make(lambda i: i, shape_dom.T.carT, inj=True)
        assert isinstance(embed, ast.LambdaExpr)
        assert embed.T.argT == shape_dom.T.carT
        if embed.T._raw_resT() != base_dom.T.carT:
            raise ValueError(f"Embed result type {embed.T._raw_resT} does not match base domain {base_dom.T.carT}")
        if elem is None:
            elem = ast.LambdaExpr.make(lambda i: i, base_dom.T.carT, inj=True)
        assert isinstance(embed, ast.LambdaExpr)
        assert elem.T.argT == base_dom.T.carT
        node = ir.NDDomT(
            embed.node,
            elem.node,
            *(d.node for d in base_doms),
            *(d.node for d in shape_doms),
            base_rank=len(base_doms)
        )
        return NDDomType(node)

    @property
    def base_doms(self) -> tuple[ast.DomainType]:
        return tuple(ast.DomainExpr(d) for d in self._node.base_doms)

    @property
    def base_dom(self) -> ast.DomainExpr:
        return ast.cartprod(*self.base_doms)

    @property
    def shape_doms(self) -> tuple[ast.DomainType]:
        return tuple(ast.DomainExpr(d) for d in self._node.shape_doms)
    
    @property
    def shape_dom(self) -> ast.DomainExpr:
        return ast.cartprod(*self.shape_doms)

    @property
    def base_rank(self) -> int:
        return self._node.base_rank

    @property
    def rank(self) -> int:
        return self._node.rank

    @property
    def embed(self) -> ast.LambdaExpr:
        return ast.LambdaExpr(self._node.embed)

    @property
    def elem(self) -> ast.LambdaExpr:
        return ast.LambdaExpr(self._node.elem)

    @property
    def carT(self) -> ast.TExpr:
        return self.elem.T._raw_resT(True)

    @property
    def shape(self) -> tp.Tuple[ast.IntExpr]:
        return tuple(d.size for d in self.shape_doms)

    @property
    def _slam(self):
        return self.elem @ self.embed


def wrapND(node: ir.Value, T: NDDomType) -> ir.Node:
    if isinstance(node.T, ir.RefT):
        raise NotImplementedError()
    return node.replace(T.node, *node._children[1:])


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

class NDDomainExpr(ast.DomainExpr):
    @property
    def T(self) -> NDDomType:
        return tp.cast(NDDomType, super().T)
    
    @classmethod
    def make(cls, *doms: ast.DomainExpr):
        f = ast.cartprod(*doms)
        T = NDDomType.make(tuple(doms))
        return NDDomainExpr(wrapND(f.node, T))

    @property
    def _raw(self) -> ast.DomainExpr:
        Tnode = ir.DomT(self.T.carT.node)
        node = self.node.replace(Tnode, *self.node._children[1:])
        return ast.DomainExpr(node)

    @property
    def rank(self) -> int:
        return self.T.rank
    
    @property
    def base_rank(self) -> int:
        return self.T.base_rank
    
    @property
    def shape(self) -> tp.Tuple[ast.IntExpr]:
        return self.T.shape

    # S -> T
    #def map(self, fn: tp.Callable|ast.LambdaExpr, _inj=False) -> NDArrayExpr:
    #    if not isinstance(fn, ast.LambdaExpr):
    #        lambda_expr = ast.LambdaExpr.make(fn, self.T.shape_dom.T.carT, _inj)
    #    else:
    #        lambda_expr = fn
    #    assert lambda_expr.T.argT == self.T.shape_dom.T.carT
    #    return NDArrayExpr(self, lambda_expr)

    def unwrap(self) -> ast.DomainExpr:
        if self.rank !=1:
            raise ValueError("Cannot unwrap non-1 rank NDDomain")
        unwrapped = self._raw.map(lambda i: i[0], _inj=True).image
        return unwrapped

    @property
    def identity(self) -> NDArrayExpr:
        return self.map(lambda i: i, _inj=True)

    def gather(self, dom: ast.DomainExpr) -> NDDomainExpr:
        #if self.T != dom.T:
        #    raise ValueError(f"Domain types do not match: {self.T} != {dom.T}")
        if isinstance(dom, NDDomainExpr):
            if self.T.base_dom.T != dom.T.base_dom.T:
                raise ValueError(f"Base domains do not match: {self.base_dom.T} != {dom.base_dom.T}")
            if self.T.base_dom.T.carT != dom.T._slam.T._raw_resT():
                raise ValueError()
            assert dom.T.base_dom.T == self.T.base_dom.T
            new_shape_doms = dom.T.shape_doms
            new_base_doms = self.T.base_doms
            new_embed = dom.T._slam # NS -> B
            new_elem = self.T.elem
            assert new_embed.T._raw_resT() == self.T.base_dom.T.carT
            T = NDDomType.make(new_base_doms, new_shape_doms, new_embed, new_elem)
            node = ir.Gather(T.node, dom.node, self.node)
            new_dom = NDDomainExpr(node)
            return new_dom
        else:
            assert 0
            return dom.map(lambda i: self.T._slam(i), _inj=True).image

    def elem_at(self, val: tp.Any):
        val = ast.Expr.make(val)
        if not (isinstance(val.T, ast.TupleType) and len(val.T)==self.rank):
            raise ValueError(f"Expected {self.rank} indices, got {len(val.T)}")
        if val.T != self.T.shape_dom.T.carT:
            raise ValueError()
        return self.T._slam(val)

    def __getitem__(self, val: tp.Any) -> NDDomainExpr:
        if isinstance(val, ast.DomainExpr):
            return self.gather(val)
        if not isinstance(val, tuple):
            val = (val,)
        if len(val) != self.rank:
            raise ValueError(f"Expected {self.rank} indices, got {len(val)}")
        gdoms: tp.List[ast.DomainExpr] = []
        for (sdom, v) in zip(self.T.shape_doms, val):
            # Case of index of rank-1 things
            if isinstance(v, ast.TupleExpr) and len(v)==1:
                v = v[0]
            if isinstance(v, ast.IntOrExpr):
                v = ast.IntExpr.make(v)
                gdoms.append(v.singleton)
            elif isinstance(v, slice):
                lo, hi, step = _make_slice(sdom.size, v)
                from ...libs.nd import range
                gdoms.append(range(lo, hi, step))
            elif isinstance(v, ast.DomainExpr):
                gdoms.append(v)
            else:
                raise ValueError(f"cannot handle {v}")
        if all(d.is_singleton for d in gdoms):
            return self.elem_at(ast.TupleExpr.make(tuple(d.unique_elem for d in gdoms))).singleton
        gdom = nd_cartprod(*gdoms)
        dom = self.gather(gdom)
        return dom
       
    def __mul__(self, other):
        return nd_cartprod(self, other)
    
def nd_cartprod(*doms: ast.DomainExpr) -> ast.DomainExpr:
    if not all(isinstance(dom, ast.DomainExpr) for dom in doms):
        raise ValueError("Invalid")
    base_doms = []
    shape_doms = []
    embed_lams = []
    elem_lams = []
    so = 0
    bo = 0
    for dom in doms:
        if isinstance(dom.T, NDDomType):
            base_doms += dom.T.base_doms
            shape_doms += dom.T.shape_doms
            for bi in range(dom.T.rank):
                embed_lams.append(lambda sis,o=so,dom=dom,bi=bi: sis[o:o+dom.rank][bi])
                elem_lams.append(lambda bis,o=bo,dom=dom,bi=bi: dom.T.elem(bis[o:o+dom.base_rank])[bi])
            so += dom.T.rank
            bo += dom.T.base_rank
        elif dom.is_singleton:
            base_doms.append(dom)
            embed_lams.append(lambda sis,dom=dom: dom.unique_elem)
            elem_lams.append(lambda bis,dom=dom: dom.unique_elem)
            bo += 1
        else:
            raise NotImplementedError()
    if len(shape_doms)==0:
        raw_cartprod = ast.cartprod(*(ast.DomainExpr(d.node) for d in doms))
        return raw_cartprod
    def embed_fn(s_indices: ast.TupleExpr): # new_shape -> new_base
        base_indices = []
        for bi in range(len(base_doms)):
            base_indices.append(embed_lams[bi](s_indices))
        return tuple(base_indices)
    def elem_fn(b_indices: ast.TupleExpr): # new_shape -> new_base
        E_indices = []
        for bi in range(len(base_doms)):
            E_indices.append(elem_lams[bi](b_indices))
        return tuple(E_indices)
    embed = ast.LambdaExpr.make(embed_fn, ast.cartprod(*shape_doms).T.carT)
    elem = ast.LambdaExpr.make(elem_fn, ast.cartprod(*base_doms).T.carT)
    base_doms = tuple(base_doms)
    shape_doms = tuple(shape_doms)
    T = NDDomType.make(base_doms, shape_doms, embed, elem)
    raw_cartprod = ast.cartprod(*shape_doms).map(elem @ embed).image
    node = wrapND(raw_cartprod.node, T)
    prod_dom = NDDomainExpr(node)
    return prod_dom

# Dom B, S, E
# lam: E -> T
class NDArrayExpr(ast.FuncExpr):
    def __post_init__(self):
        assert isinstance(self.T.domain, NDDomainExpr)
    
    @property
    def rank(self) -> int:
        return self.domain.rank

    @property
    def domain(self) -> NDDomainExpr:
        return self.T.domain

    @property
    def shape(self) -> tp.Tuple[ast.IntExpr]:
        return self.domain.shape
    
    @property
    def _get_lam(self) -> tp.Optional[ast.LambdaExpr]:
        if isinstance(self.node, ir.Map):
            return ast.LambdaExpr(self.node._children[-1])
        return None

    def map(self, fn: tp.Callable|ast.LambdaExpr) -> NDArrayExpr:
        # fn: T -> U
        #if lam := self._get_lam:
        #    lam_e = ast.LambdaExpr.make(fn, lam.T._raw_resT)
        #    new_lam = lam_e @ lam
        #    lamT = new_lam.T
        #    T = ir.FuncT(self.domain.node, lamT._node)
        #    node = ir.Map(T, self.domain.node, new_lam.node)
        #    return NDArrayExpr(node)
        return NDArrayExpr(super().map(fn).node)

    def _wrap_arg(self, arg: ast.Expr) -> ast.Expr:
        if isinstance(arg.T, ast.TupleType):
            assert len(arg.T)==self.rank
            if self.rank==1:
                arg = arg[0]
        return arg
        
    def apply(self, arg: ast.Expr) -> ast.Expr:
        arg = ast.Expr.make(arg)
        if lam := self._get_lam:
            arg_ref = arg.refine(lambda _: self.domain.contains(arg))
            return lam(arg_ref)
        return super().apply(arg)

    def __call__(self, arg: ast.Expr) -> ast.Expr:
        return self.apply(arg)

    @property
    def image(self) -> ast.DomainExpr:
        if lam := self._get_lam:
            if lam._inj:
                # lam : E -> T
                dom = self.domain
                new_elem = lam @ dom.T.elem
                base_doms = dom.T.base_doms
                shape_doms = dom.T.shape_doms
                embed = dom.T.embed
                T = NDDomType.make(base_doms, shape_doms, embed, new_elem)
                node = super().image.node
                node = wrapND(node, T)
                return NDDomainExpr(node)
        return super().image

    def __getitem__(self, val: tp.Any) -> NDArrayExpr:
        new_dom = self.domain[val]
        if new_dom.is_singleton:
            return ast.wrap(self.apply(new_dom.unique_elem).node)
        return new_dom.map(lambda i: self.apply(i))