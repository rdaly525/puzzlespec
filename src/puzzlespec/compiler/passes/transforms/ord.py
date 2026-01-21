from __future__ import annotations

import typing as tp

from ..pass_base import Transform, AnalysisObject, Context, handles
from ..analyses.ord import gen_enumerate
from ...dsl import ir, ast
from ..envobj import EnvsObj


class OrdSimplificationPass(Transform):
    requires = ()
    produces = ()
    name = 'ord_simplify'

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        return self.visit(root)

    @handles(ir.ElemAt)
    def _(self, node: ir.ElemAt) -> ir.Node:
        T, dom, idx = self.visit_children(node)
        e = gen_enumerate(dom)
        app = e(ast.wrap(idx))
        return app.node

    @handles(ir.Slice)
    def _(self, node: ir.Slice):
        T, dom, lo, hi, step = self.visit_children(node)
        if isinstance(dom, ir.Range):
            _, r_lo, r_hi, r_step = dom._children
            r_lo, r_hi, r_step = ast.IntExpr(r_lo), ast.IntExpr(r_hi), ast.IntExpr(r_step)
            s_lo, s_hi, s_step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
            new_lo = r_lo + r_step * s_lo
            new_hi = r_lo + r_step * s_hi
            new_step = r_step * s_step
            return ir.Range(T, new_lo.node, new_hi.node, new_step.node)
        if isinstance(dom, ir.Image):
            T_I, func = dom._children
            if isinstance(func, ir.Map):
                _, dom_f, lam_f = func._children
                assert lam_f.T.inj
        return node.replace(T, dom, lo, hi, step)

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        T, func = self.visit_children(node)
        f: ast.FuncExpr = ast.wrap(func)
        if f.domain.T.is_ord:
            e = gen_enumerate(f.domain.node)
            return e.forall(lambda elem: f(elem)).node
        return node.replace(T, func)