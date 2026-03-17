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
    assert isinstance(lamT, (ir.PiT, ir.PiTHOAS))
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

    def _replace(self, t: ir.Node, *new_children) -> ir.Node:
        """Helper to call replace with the correct kwargs depending on node kind."""
        if isinstance(t, ir.Value):
            return t.replace(*new_children, T=t.T, obl=t.obl)
        elif isinstance(t, ir.Type):
            return t.replace(*new_children, ref=t.ref, view=t.view, obl=t.obl)
        return t.replace(*new_children)

    def shift(self, t: ir.Node, d: int, cutoff: int = 0) -> ir.Node:
        """
        shift(d, cutoff, t): add d to all BoundVar indices >= cutoff
        (standard TAPL shift)
        """
        if isinstance(t, ir.BoundVar):
            k = t.idx
            if k >= cutoff:
                return ir.BoundVar(t.T, k + d)
            else:
                return t

        if isinstance(t, ir.Lambda):
            body = t.children[0]
            body2 = self.shift(body, d, cutoff + 1)
            return self._replace(t, body2)

        if isinstance(t, ir.PiT):
            argT, resT = t.children
            argT2 = self.shift(argT, d, cutoff)
            resT2 = self.shift(resT, d, cutoff + 1)
            return t.replace(argT2, resT2, ref=t.ref, view=t.view, obl=t.obl)

        # generic n-ary node: no new binder
        new_children = [self.shift(c, d, cutoff) for c in t.children]
        return self._replace(t, *new_children)

    def subst(self, t: ir.Node, j: int, s: ir.Node, depth: int = 0) -> ir.Node:
        """
        subst(j, s, t, depth): substitute s for variable with index (j + depth)
        in t, where depth is how many binders we've gone under so far.
        This is the TAPL-style subst with de Bruijn indices.
        """
        if isinstance(t, ir.BoundVar):
            k = t.idx
            if k == j + depth:
                return self.shift(s, depth)
            else:
                return t

        if isinstance(t, ir.Lambda):
            body = t.children[0]
            body2 = self.subst(body, j, s, depth + 1)
            return self._replace(t, body2)

        if isinstance(t, ir.PiT):
            argT, resT = t.children
            argT2 = self.subst(argT, j, s, depth)
            resT2 = self.subst(resT, j, s, depth + 1)
            return t.replace(argT2, resT2, ref=t.ref, view=t.view, obl=t.obl)

        new_children = [self.subst(c, j, s, depth) for c in t.children]
        return self._replace(t, *new_children)

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
        body = lam.children[0]

        # 1. shift argument up by 1 for the binder we're eliminating
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
            return self.bv_map[node.name]
        return super().visit(node)

    @handles(ir.ApplyT)
    def _(self, node: ir.ApplyT):
        lamT, arg = node.children
        arg = self.visit(arg)
        assert isinstance(arg, ir.Value)
        assert isinstance(lamT, ir.PiTHOAS)
        argT, resT = lamT.children
        bv_name = lamT.bv_name
        assert lamT.bv_name not in self.bv_map
        self.bv_map[bv_name] = arg
        new_resT = self.visit(resT)
        del self.bv_map[bv_name]
        return new_resT

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        assert node.bv_name not in self.bv_map
        return super().visit(node)

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        lam, arg = node.children
        if isinstance(lam, ir.LambdaHOAS):
            body = lam.children[0]
            bv_name = lam.bv_name
            if bv_name in self.bv_map:
                raise ValueError()
            assert bv_name not in self.bv_map
            self.bv_map[bv_name] = self.visit(arg)
            new_body = self.visit(body)
            del self.bv_map[bv_name]
            return new_body
        return super().visit(node)
