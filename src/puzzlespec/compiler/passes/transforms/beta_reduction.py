from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir
import typing as tp


# High level algortihm:
# add 1 to all bound vars in arg
# Do substition: body[BV0 -> (arg+1)]
# do body - 1
class BetaReductionPass(Transform):
    enable_memoization = False
    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "beta_reduction"

    def run(self, root: ir.Node, ctx: Context):
        return self.visit(root)

    # ---------- helpers ----------

    def shift(self, t: ir.Node, d: int, cutoff: int = 0) -> ir.Node:
        """
        shift(d, cutoff, t): add d to all BoundVar indices >= cutoff
        """
        if isinstance(t, ir.BoundVar):
            k = t.idx
            if k >= cutoff:
                return ir.BoundVar(k + d)
            else:
                return t

        if isinstance(t, (ir.Lambda, ir.LambdaT)):
            # assuming children = (lamT, body) or similar
            new_children = []
            for child in t._children:
                # go under a binder: cutoff+1
                new_children.append(self.shift(child, d, cutoff + 1))
            return t.replace(*new_children)

        # generic n-ary node: just recurse with same cutoff
        new_children = [self.shift(c, d, cutoff) for c in t._children]
        return t.replace(*new_children)

    def subst(self, t: ir.Node, j: int, s: ir.Node, depth: int = 0) -> ir.Node:
        """
        subst(j, s, t, depth): substitute s for variable with index (j + depth)
        in t, where depth is how many binders we're under.
        """
        if isinstance(t, ir.BoundVar):
            k = t.idx
            if k == j + depth:
                # found the var we’re substituting
                return self.shift(s, depth)   # adjust s to this depth
            else:
                return t

        if isinstance(t, (ir.Lambda, ir.LambdaT)):
            new_children = []
            for child in t._children:
                new_children.append(self.subst(child, j, s, depth + 1))
            return t.replace(*new_children)

        # generic n-ary node
        new_children = [self.subst(c, j, s, depth) for c in t._children]
        return t.replace(*new_children)

    # ---------- visitors ----------

    @handles(ir.Lambda, ir.LambdaT)
    def _(self, node: ir.Node):
        # ordinary traversal: just transform children
        new_children = self.visit_children(node)
        return node.replace(*new_children)

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        # no change outside of β-redexes
        return node

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        # first recursively reduce inside
        T, func, arg = self.visit_children(node)

        # adjust this pattern match to your actual IR:
        if isinstance(func, ir.Map):
            domT, dom, lam = func._children
            lamT, body = lam._children

            # (Lam(body) arg)

            # 1. shift argument up by 1 for the binder we’re eliminating
            arg_p1 = self.shift(arg, +1)

            # 2. substitute for "0" (j=0) in body
            body_sub = self.subst(body, 0, arg_p1, depth=0)

            # 3. shift everything down by 1 (remove the binder)
            body_m1 = self.shift(body_sub, -1)

            return body_m1

        return node.replace(T, func, arg)