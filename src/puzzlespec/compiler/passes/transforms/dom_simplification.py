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
            assert T.eq(new_dom.T)
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
            _, dom, lo, hi = dom._children
            return ir.Sub(ir.IntT(), hi, lo)
        if isinstance(dom, ir.CartProd):
            cartdoms = dom._children[1:]
            return ir.Prod(ir.IntT(), *(ir.Card(ir.IntT(), cd) for cd in cartdoms))
        return node.replace(T, dom)

    @handles(ir.Unique)
    def _(self, node: ir.Unique):
        T, dom = self.visit_children(node)
        if isinstance(dom, ir.Singleton):
            _, val = dom._children
            return val
        return node.replace(T, dom)

    #Map(y in img(map(x in D -> f(x))) -> g(y)) -> map(x in D -> g(f(x)))
    @handles(ir.Map)
    def _(self, node: ir.Map):
        T_out, dom_out, lam_out = self.visit_children(node)
        if isinstance(dom_out, ir.Image):
            T_img, func_img = dom_out._children
            if isinstance(func_img, ir.Map):
                T_in, dom_in, lam_in = func_img._children
                lam_new = (ast.wrap(lam_out) @ ast.wrap(lam_in))
                lam_new.type_check()
                lam_new = lam_new.node
                #print("T_in")
                #print(ast.wrapT(T_in))
                #print("*"*30)
                #print("T_out")
                #print(ast.wrapT(T_out))
                #print("*"*30)
                T_new = ir.FuncT(
                    dom = dom_in,
                    lamT = lam_new.T
                )
                map_new = ir.Map(
                    T_new,
                    dom_in,
                    lam_new
                )
                return map_new
        return node.replace(T_out, dom_out, lam_out)

        

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
            #if isinstance(dom, ir.Image):
            #    _, func2 = dom._children
            #    if isinstance(func2, ir.Map):
            #        _, dom2, lam2 = func2._children
            #        le1 = ast.LambdaExpr(lam).simplify
            #        le2 = ast.LambdaExpr(lam2).simplify
            #        new_lam = (le1 @ le2).node
            #        return ir.Image(
            #            T,
            #            ir.Map(
            #                T_map,
            #                dom2,
            #                new_lam,
            #            )
            #        )
        return node.replace(T, func)

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, bv, body = self.visit_children(node)
        inj = node.inj
        if bv == body:
            self.ids.add(node)
            inj = True
        return node.replace(T, bv, body, inj=inj)


    #@handles(ir.ElemAt)
    #def _(self, node: ir.ElemAt):
    #    T, dom, idx = self.visit_children(node)
    #    if isinstance(dom, ir.Fin):
    #        return idx
    #    if isinstance(dom, ir.Range):
    #        _, lo, hi = dom._children
    #        return ir.Add(ir.IntT(), lo, idx)
    #    if isinstance(dom, ir.Slice):
    #        _, dom, lo, hi = dom._children
    #        return ir.ElemAt(
    #            T,
    #            dom,
    #            ir.Add(ir.IntT(), lo, idx)
    #        )
    #    return node.replace(T, dom, idx)

    