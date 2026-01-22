from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast
import typing as tp


class LamSimplification(Transform):
    """
    - Simplifies Non-dependent Lambdas to Arrows
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "dom_simplification"
    #_debug=True

    def run(self, root: ir.Node, ctx: Context):
        self.bv_stack: tp.Mapping[ir.Node, tp.Set[str]] = {}
        new_root = self.visit(root)
        return new_root

    def visit(self, node: ir.Node):
        children = self.visit_children(node)
        bvs = set()
        for c in children:
            bvs |= self.bv_stack[c]
        new_node = node.replace(*children)
        self.bv_stack[new_node] = bvs
        return new_node

    @handles(ir.BoundVarHOAS)
    def _(self, node: ir.BoundVarHOAS):
        T, = self.visit_children(node)
        bvs = set([node.name]) | self.bv_stack[T]
        new_node = node.replace(T)
        self.bv_stack[new_node] = bvs
        return new_node

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, body = self.visit_children(node)
        body_bvs = self.bv_stack[body]
        bv_name = node.bv_name
        if bv_name in body_bvs:
            body_bvs.remove(bv_name)
        bvs = self.bv_stack[T] | body_bvs
        new_node = node.replace(T, body)
        self.bv_stack[new_node] = bvs
        return new_node

    @handles(ir.PiTHOAS)
    def _(self, node: ir.PiTHOAS):
        argT, resT = self.visit_children(node)
        resT_bvs = self.bv_stack[resT]
        bv_name = node.bv_name
        if bv_name in resT_bvs:
            resT_bvs.remove(bv_name)
            new_node = node.replace(bv, resT)
        else:
            new_node = ir.ArrowT(argT, resT)
        bvs = self.bv_stack[argT] | resT_bvs
        self.bv_stack[new_node] = bvs
        return new_node