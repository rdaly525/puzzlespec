from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ir_types as irT

class CanonicalizePass(Transform):
    """Canonicalize the IR tree.
    """

    name = "canonicalize"

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        
        # Perform the transform by visiting the root node
        result = self.visit(root)
        
        return result

    def visit(self, node: ir.Node) -> ir.Node:
        """Visit a node and return the transformed node."""
        # This method is inherited from the base Transform class
        # It will automatically dispatch to the appropriate visitor method
        return super().visit(node)

    def ass_and_com(self, children: tp.Iterable[ir.Node], binOp: tp.Type[ir.Node], vaOp: tp.Type[ir.Node]):
        new_children = []
        for c in children:
            if isinstance(c, (binOp, vaOp)):
                new_children += c._children
            else:
                new_children.append(c)
        # Sort by keys
        return vaOp(*sorted(new_children, key=lambda c: c._key))

    # associative and commutative operators
    @handles(ir.And, ir.Conj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children, ir.And, ir.Conj)

    @handles(ir.Or, ir.Disj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children, ir.Or, ir.Disj)

    @handles(ir.Mul, ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children, ir.Mul, ir.Prod)

    @handles(ir.Add, ir.Sum)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children, ir.Add, ir.Sum)

    # Replace Sub with Add(Neg(b))
    @handles(ir.Sub)
    def _(self, node: ir.Node) -> ir.Node:
        a, b = self.visit_children(node)
        return ir.Add(a, ir.Neg(b))

    # Equal is commutative
    @handles
    def _(self, node: ir.Eq):
        children = self.visit_children(node)
        return ir.Eq(*sorted(children, key=lambda c: c._key))

    # Change all comparisons to Lt, LtEq
    @handles
    def _(self, node: ir.Gt):
        a, b = self.visit_children(node)
        return ir.Lt(b, a)

    @handles
    def _(self, node: ir.GtEq):
        a, b = self.visit_children(node)
        return ir.LtEq(b, a)