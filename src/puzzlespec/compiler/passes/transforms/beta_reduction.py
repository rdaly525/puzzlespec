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
    #cse=True
    name = "beta_reduction"


class BetaReductionPass(Transform):
    enable_memoization = False
    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "beta_reduction"

    def run(self, root: ir.Node, ctx: Context):
        #self.cur_lam_depth = 0
        #self.lambda_depth = {}   # map: ir.Lambda -> int
        return self.visit(root)

    # ---------- helpers ----------

    def shift(self, t: ir.Node, d: int, cutoff: int = 0) -> ir.Node:
        """
        shift(d, cutoff, t): add d to all BoundVar indices >= cutoff
        (standard TAPL shift)
        """
        if isinstance(t, ir.BoundVar):
            k = t.idx
            if k >= cutoff:
                return ir.BoundVar(k + d)
            else:
                return t

        if isinstance(t, ir.Lambda):
            argT, body = t._children
            # binder does *not* apply inside argT
            argT2 = self.shift(argT, d, cutoff)
            body2 = self.shift(body, d, cutoff + 1)
            return t.replace(argT2, body2)

        if isinstance(t, ir.PiT):
            argT, body = t._children
            # binder does *not* apply inside argT
            argT2 = self.shift(argT, d, cutoff)
            body2 = self.shift(body, d, cutoff + 1)
            return t.replace(argT2, body2)

        # generic n-ary node: no new binder
        new_children = [self.shift(c, d, cutoff) for c in t._children]
        return t.replace(*new_children) 

    def subst(self, t: ir.Node, j: int, s: ir.Node, depth: int = 0) -> ir.Node:
        """
        subst(j, s, t, depth): substitute s for variable with index (j + depth)
        in t, where depth is how many binders we've gone under so far.
        This is the TAPL-style subst with de Bruijn indices.
        """
        if isinstance(t, ir.BoundVar):
            k = t.idx
            if k == j + depth:
                # found the var to replace; shift s by depth to account for binders
                return self.shift(s, depth)
            else:
                return t

        if isinstance(t, ir.Lambda):
            argT, body = t._children
            argT2 = self.subst(argT, j, s, depth)        # no new binder in argT
            body2 = self.subst(body, j, s, depth + 1)    # binder in body
            return t.replace(argT2, body2)

        if isinstance(t, ir.PiT):
            argT, body = t._children
            argT2 = self.subst(argT, j, s, depth)        # no new binder in argT
            body2 = self.subst(body, j, s, depth + 1)
            return t.replace(argT2, body2)

        new_children = [self.subst(c, j, s, depth) for c in t._children]
        return t.replace(*new_children)

    # ---------- visitors ----------

    
    #@handles(ir.Lambda, ir.PiT)
    #def _(self, node: ir.Node):
    #    # record depth at definition site
    #    self.lambda_depth[node] = self.cur_lam_depth

    #    # enter this lambda's body
    #    self.cur_lam_depth += 1
    #    new_children = self.visit_children(node)
    #    self.cur_lam_depth -= 1

    #    return node.replace(*new_children)

   
    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        # no change outside of β-redexes
        return node

    @handles(ir.ApplyFunc)
    def _(self, node: ir.ApplyFunc):
        # first recursively reduce inside
        T, func, arg = self.visit_children(node)

        if isinstance(func, ir.Map):
            domT, dom, lam = func._children
            piT, body = lam._children

            # (Lam(body) arg)

            # 1. shift argument up by 1 for the binder we’re eliminating
            arg_p1 = self.shift(arg, +1, cutoff=0)

            # 2. substitute for "0" (j=0) in body
            body_sub = self.subst(body, 0, arg_p1, depth=0)

            # 3. shift everything down by 1 (remove the binder)
            body_m1 = self.shift(body_sub, -1, cutoff=0)

            return body_m1

        return node.replace(T, func, arg)