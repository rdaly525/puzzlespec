from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir
import typing as tp


class DomainSimplificationPass(Transform):
    """
    - Simplifies domain expressions
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "dom_simplification"

    def run(self, root: ir.Node, ctx: Context):
        new_root = self.visit(root)
        return new_root

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

    @handles(ir.Slice)
    def _(self, node: ir.Slice):
        T, dom, lo, hi = self.visit_children(node)
        if lo.eq(ir.Lit(ir.IntT(), val=0)):
            if hi.eq(ir.Card(ir.IntT(), dom)):
                return dom
            if isinstance(dom, ir.Fin) and hi.eq(dom._children[1]):
                return dom
        return node.replace(T, dom, lo, hi)

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

    @handles(ir.ElemAt)
    def _(self, node: ir.ElemAt):
        T, dom, idx = self.visit_children(node)
        if isinstance(dom, ir.Fin):
            return idx
        if isinstance(dom, ir.Range):
            _, lo, hi = dom._children
            return ir.Add(ir.IntT(), lo, idx)
        if isinstance(dom, ir.Slice):
            _, dom, lo, hi = dom._children
            return ir.ElemAt(
                T,
                dom,
                ir.Add(ir.IntT(), lo, idx)
            )
        return node.replace(T, dom, idx)