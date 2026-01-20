from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir
from ...dsl.utils import substitute
import typing as tp
from ..analyses.pretty_printer import pretty


def beta_reduce_HOAS(node: ir.Node):
    p = BetaReductionHOAS()
    ctx = Context()
    return p.run(node, ctx)

def applyT(lamT: ir.Node, arg: ir.Value):
    assert isinstance(lamT, (ir.LambdaT, ir.LambdaTHOAS))
    assert isinstance(arg, ir.Value)
    appT = ir.ApplyT(lamT, arg)
    T = beta_reduce_HOAS(appT)
    return T

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

        if isinstance(t, ir.LambdaT):
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

        if isinstance(t, ir.LambdaT):
            argT, body = t._children
            argT2 = self.subst(argT, j, s, depth)        # no new binder in argT
            body2 = self.subst(body, j, s, depth + 1)
            return t.replace(argT2, body2)

        new_children = [self.subst(c, j, s, depth) for c in t._children]
        return t.replace(*new_children)

    # ---------- visitors ----------

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        # no change outside of β-redexes
        return node

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        # first recursively reduce inside
        T, lam, arg = self.visit_children(node)
        assert isinstance(lam, ir.Lambda)
        lamT, body = lam._children

        # 1. shift argument up by 1 for the binder we’re eliminating
        arg_p1 = self.shift(arg, +1, cutoff=0)

        # 2. substitute for "0" (j=0) in body
        body_sub = self.subst(body, 0, arg_p1, depth=0)

        # 3. shift everything down by 1 (remove the binder)
        body_m1 = self.shift(body_sub, -1, cutoff=0)

        return body_m1

class BetaReductionHOAS(Transform):
    enable_memoization = False
    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "beta_reduction_hoas"

    def run(self, root: ir.Node, ctx: Context):
        self.bv_map = {}
        return self.visit(root)

    @handles(ir.BoundVarHOAS)
    def _(self, node: ir.BoundVarHOAS):
        if node.name in self.bv_map:
            #print(f"  BV: {node.name} -> {self.bv_map[node.name]}")
            return self.bv_map[node.name]
        return node

    @handles(ir.ApplyT)
    def _(self, node: ir.ApplyT):
        lamT, arg = node._children
        arg = self.visit(arg)
        assert isinstance(arg, ir.Value)
        assert isinstance(lamT, ir.LambdaTHOAS)
        bv, resT = lamT._children
        assert bv not in self.bv_map
        self.bv_map[bv.name] = arg
        new_resT = self.visit(resT)
        del self.bv_map[bv.name]
        return new_resT

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, bv, body = node._children
        assert bv.name not in self.bv_map
        return super().visit(node)

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        #T, lam, arg = self.visit_children(node)
        T, lam, arg = node._children
        assert isinstance(lam, ir.LambdaHOAS)
        T, bv, body = lam._children
        if bv.name in self.bv_map:
            raise ValueError()
        assert bv.name not in self.bv_map
        self.bv_map[bv.name] = self.visit(arg)
        #print(f"Replace {bv.name} with {arg} in (")
        #print(f"  BODY:{body}")
        new_body = self.visit(body)
        #print(f"  NEW BODY:{new_body} )")
        del self.bv_map[bv.name]
        return new_body
            