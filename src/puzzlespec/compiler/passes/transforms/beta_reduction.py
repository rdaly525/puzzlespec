from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir
import typing as tp


class BetaReductionPass(Transform):
    """
    - Applies beta reduction to the program
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "beta_reduction"

    def run(self, root: ir.Node, ctx: Context):
        self.apps = []
        return self.visit(root)

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda):
        self.apps.append(None)
        T, body = self.visit_children(node)
        self.apps.pop()
        return node.replace(T, body)

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        app = self.apps[-(node.idx+1)]
        if app is not None:
            return app
        return node

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        T, func, arg = node._children

        # Index into a ListLit
        if isinstance(func, ir.ListLit):
            T, vals = self.visit_children(func)
            match (arg):
                case ir.Lit(val=idx):
                    assert isinstance(idx, int) and 0 <= idx < len(vals)
                    return vals[idx]
            return node.replace(*self.visit_children(node))

        # Application to a Map Func
        if isinstance(func, ir.Map):
            domT, dom, lam = func._children
            lamT, body = lam._children
            self.apps.append(arg)
            new_body = self.visit(body)
            self.apps.pop()
            return new_body
        return node.replace(*self.visit_children(node))