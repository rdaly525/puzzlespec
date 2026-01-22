from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast
import typing as tp


class DomainSimplificationPass(Transform):
    """
    - Simplifies domain expressions
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "dom_simplification"
    #_debug=True

    def run(self, root: ir.Node, ctx: Context):
        self.ids = set()
        new_root = self.visit(root)
        return new_root

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        T, *doms = self.visit_children(node)
        if len(doms)==0:
            domT = ir.DomT(ir.TupleT())
            return ir.Singleton(domT, ir.TupleLit(ir.TupleT()))
        if all(dom.T.is_singleton for dom in doms):
            assert T.is_singleton
            elems = [ir.Unique(dom.T.carT, dom) for dom in doms]
            return ir.Singleton(T, ir.TupleLit(T.carT, *elems))
        return node.replace(T, *doms)

    @handles(ir.DisjUnion)
    def _(self, node: ir.DisjUnion):
        T, *doms = self.visit_children(node)
        if len(doms)==0:
            domT = ir.DomT(ir.SumT())
            return ir.Empty(domT)
        return node.replace(T, *doms)
        
    @handles(ir.DomProj)
    def _(self, node: ir.DomProj):
        T, dom = self.visit_children(node)
        if isinstance(dom, ir.CartProd):
            cart_doms = dom._children[1:]
            assert node.idx < len(cart_doms)
            new_dom = cart_doms[node.idx]
            assert T==new_dom.T
            return new_dom
        return node.replace(T, dom)

    @handles(ir.Card)
    def _(self, node: ir.Card):
        T, dom = self.visit_children(node)
        if isinstance(dom, ir.Fin):
            _, N = dom._children
            return N
        if isinstance(dom, ir.Singleton):
            return ir.Lit(ir.IntT(), val=1)
        if isinstance(dom, ir.DomLit) and dom.is_set:
            # Card(DomLit(T, *elems)) = len(elems)
            num_elems = len(dom._children[1:])
            return ir.Lit(ir.IntT(), val=num_elems)
        if isinstance(dom, ir.Slice):
            _, dom, lo, hi, step = dom._children
            lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
            size = (hi-lo)//step
            return size.node
        if isinstance(dom, ir.Range):
            _, lo, hi, step = dom._children
            lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
            size = (hi-lo)//step
            return size.node
        if isinstance(dom, ir.CartProd):
            doms = dom._children[1:]
            return ir.Prod(ir.IntT(), *(ir.Card(ir.IntT(), d) for d in doms))
        if isinstance(dom, ir.DisjUnion):
            doms = dom._children[1:]
            return ir.Sum(ir.IntT(), *(ir.Card(ir.IntT(), d) for d in doms))
        if isinstance(dom, ir.Image):
            _, func = dom._children
            if isinstance(func, ir.Map):
                _, dom, lam = func._children
                if lam.T.inj:
                    return ir.Card(ir.IntT(), dom)
        return node.replace(T, dom)

    @handles(ir.Unique)
    def _(self, node: ir.Unique):
        T, dom = self.visit_children(node)
        if isinstance(dom, ir.Singleton):
            _, val = dom._children
            return val
        return node.replace(T, dom)

    @handles(ir.Image)
    def _(self, node: ir.Image):
        T, func = self.visit_children(node)
        if isinstance(func, ir.Map):
            T_map, dom, lam = func._children
            if lam in self.ids:
                return dom
            if isinstance(dom, ir.Singleton):
                return ir.Singleton(
                    T,
                    ir.Apply(T.carT, lam, dom._children[1])
                )
            if isinstance(dom, ir.Image):
                _, func2 = dom._children
                if isinstance(func2, ir.Map):
                    _, dom2, lam2 = func2._children
                    le1 = ast.LambdaExpr(lam)
                    le2 = ast.LambdaExpr(lam2)
                    new_lam = (le1 @ le2).node
                    return ir.Image(
                        T,
                        ir.Map(
                            T_map,
                            dom2,
                            new_lam,
                        )
                    )
        return node.replace(T, func)

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, body = self.visit_children(node)
        inj = node.inj
        bv_name = node.bv_name
        if isinstance(body, ir.BoundVarHOAS) and body.name==bv_name:
            self.ids.add(node)
            inj = True
        return node.replace(T, body, inj=inj)

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        T, func = self.visit_children(node)
        if isinstance(func, ir.Map):
            T_f, dom, lam = func._children
            if isinstance(dom, ir.Restrict):
                T_i, func_i = dom._children
                new_func = ast.wrap(func_i).imap(lambda i, v: ast.wrap(lam)(i) & v)
                return ir.Restrict(T, new_func.node)
        return node.replace(T, func)

    @handles(ir.Intersection)
    def _(self, node: ir.Intersection) -> ir.Node:
        T, *doms = self.visit_children(node)
        if len(doms)==0:
            return ir.Universe(T)
        if len(doms)==1:
            return doms[0]
        new_doms = []
        for dom in doms:
            if isinstance(dom, ir.Universe) and not isinstance(dom.T, ir.RefT):
                continue
            elif isinstance(dom, ir.Intersection):
                new_doms.extend(dom._children[1:])
            else:
                new_doms.append(dom)
        _new_doms = []
        for i, dom in enumerate(new_doms):
            if dom in new_doms[i+1:]:
                continue
            _new_doms.append(dom)
        rdoms = []
        nrdoms = []
        for dom in _new_doms:
            if isinstance(dom, ir.Restrict):
                rdoms.append(dom)
            else:
                nrdoms.append(dom)
        if len(rdoms) > 1:
            doms = []
            lams = []
            for rdom in rdoms:
                T, func = rdom._children
                _, dom, lam = func._children
                doms.append(ast.wrap(dom))
                lams.append(ast.wrap(lam))
            def lam(e, lams=lams):
                res = 1
                for lam in lams:
                    res &= lam(e)
                return res
            rdom = doms[0].intersect(*doms[1:]).restrict(lam)
            _new_doms = nrdoms + [rdom.node]
        return node.replace(T, *_new_doms)

