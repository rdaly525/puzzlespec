from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast
from ....libs import var_def, std
from ..envobj import EnvsObj, SymTable

class RefineSimplify(Transform):
    """simplifies refinements
    """
    name = "refine_simplify"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        new_root = self.visit(root)
        return new_root

    @handles(ir.RefT)
    def _(self, node: ir.RefT):
        T, dom = self.visit_children(node)
        # can remove refine dom if dom is Universe
        if isinstance(dom, ir.Universe):
            return T
        return node.replace(T, dom)

    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        T, = self.visit_children(node)
        if isinstance(T, ir.RefT):
            T = T.T
        return node.replace(T)

class RefineCombine(Transform):
    """Combines refinements
    """
    name = "refine_combine"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        new_root = self.visit(root)
        return new_root

    #@handles(ir.Mod)
    #def _(self, node: ir.Mod):
    #    T, left, right = self.visit_children(node)
    #    if isinstance(left.T, ir.RefT) and isinstance(right.T, ir.RefT):
    #        ldom = left.T.dom
    #        rdom = left.T.dom
    #        # {Int | Fin(5)} + {Int | Fin(7)}
    #        # -> Int | Interval(0, 5+7)
    #    return node.replace(T, left, right)

    #@handles(ir.And)
    #def _(self, node: ir.And):
    #    T, left, right = self.visit_children(node)
    #    if isinstance(left, ir.RefT) and isinstance(right, ir.RefT):
 