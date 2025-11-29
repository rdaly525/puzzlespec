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
        def check_add(node):
            if isinstance(node, ir.Add):
                raise ValueError("Fucked up")
            for child in node._children:
                check_add(child)
        check_add(result)
        return result

    def ass_and_com(self, children: tp.Iterable[ir.Node], binOp: tp.Type[ir.Node], vaOp: tp.Type[ir.Node], T: ir.Node):
        new_children = []
        for c in children:
            if isinstance(c, (binOp, vaOp)):
                new_children += c._children[1:]
            else:
                new_children.append(c)
        # Sort by keys
        return vaOp(T, *sorted(new_children, key=lambda c: c._key))

    # associative and commutative operators
    @handles(ir.And, ir.Conj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children[1:], ir.And, ir.Conj, children[0])

    @handles(ir.Or, ir.Disj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children[1:], ir.Or, ir.Disj, children[0])

    @handles(ir.Mul, ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        return self.ass_and_com(children[1:], ir.Mul, ir.Prod, children[0])

    @handles(ir.Add, ir.Sum)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        new_node = self.ass_and_com(children[1:], ir.Add, ir.Sum, children[0])
        return new_node

    # Replace Sub with Add(Neg(b))
    @handles(ir.Sub)
    def _(self, node: ir.Node) -> ir.Node:
        T, a, b = self.visit_children(node)
        return ir.Sum(T, a, ir.Neg(T, b))

    # Equal is commutative
    @handles
    def _(self, node: ir.Eq):
        children = self.visit_children(node)
        return ir.Eq(children[0], *sorted(children[1:], key=lambda c: c._key))

    # Change all comparisons to Lt, LtEq
    @handles
    def _(self, node: ir.Gt):
        T, a, b = self.visit_children(node)
        return ir.Lt(T, b, a)

    @handles
    def _(self, node: ir.GtEq):
        T, a, b = self.visit_children(node)
        return ir.LtEq(T, b, a)