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

    def ass_and_com(self, children: tp.Iterable[ir.Node], vaOp: tp.Type[ir.Node], T: ir.Node, obl):
        new_children = []
        for c in children:
            if isinstance(c, vaOp):
                assert c.obl is None, f"Flattened {vaOp.__name__} child has non-None obl"
                new_children += list(c.children)
            else:
                new_children.append(c)
        # Sort by keys
        return vaOp(T, *sorted(new_children), obl=obl)

    # associative and commutative operators
    @handles(ir.Conj)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        return self.ass_and_com(vc.children, ir.Conj, vc.T, vc.obl)

    @handles(ir.Disj)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        return self.ass_and_com(vc.children, ir.Disj, vc.T, vc.obl)

    @handles(ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        return self.ass_and_com(vc.children, ir.Prod, vc.T, vc.obl)

    @handles(ir.Sum)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        return self.ass_and_com(vc.children, ir.Sum, vc.T, vc.obl)

    @handles(ir.Union)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        return self.ass_and_com(vc.children, ir.Union, vc.T, vc.obl)

    @handles(ir.Intersection)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        return self.ass_and_com(vc.children, ir.Intersection, vc.T, vc.obl)

    @handles(ir.DomLit)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        return self.ass_and_com(vc.children, ir.DomLit, vc.T, vc.obl)

    # Equal is commutative
    @handles
    def _(self, node: ir.Eq):
        vc = self.visit_children(node)
        return ir.Eq(vc.T, *sorted(vc.children), obl=vc.obl)
