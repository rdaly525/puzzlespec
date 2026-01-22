from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ...dsl import ir

class CanonicalizePass(Transform):
    """Canonicalize the IR tree.
    """

    name = "canonicalize"

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        result = self.visit(root)
        return result

    def ass_and_com(self, children: tp.Iterable[ir.Node], vaOp: tp.Type[ir.Node], T: ir.Node):
        new_children = []
        for c in children:
            if isinstance(c, vaOp):
                new_children += c._children[1:]
            else:
                new_children.append(c)
        # Sort by keys
        return vaOp(T, *sorted(new_children))

    # associative and commutative operators
    @handles(ir.Conj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children[1:], ir.Conj, children[0])

    @handles(ir.Disj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children[1:], ir.Disj, children[0])

    @handles(ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children[1:], ir.Prod, children[0])

    @handles(ir.Sum)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        new_node = self.ass_and_com(children[1:], ir.Sum, children[0])
        return new_node

    @handles(ir.Union)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        new_node = self.ass_and_com(children[1:], ir.Union, children[0])
        return new_node

    @handles(ir.Intersection)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        new_node = self.ass_and_com(children[1:], ir.Intersection, children[0])
        return new_node

    @handles(ir.DomLit)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        new_node = self.ass_and_com(children[1:], ir.DomLit, children[0])
        return new_node

    # Equal is commutative
    @handles
    def _(self, node: ir.Eq):
        children = self.visit_children(node)
        return ir.Eq(children[0], *sorted(children[1:]))