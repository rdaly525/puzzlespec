from __future__ import annotations

import typing as tp

from ..pass_base import Transform, AnalysisObject, Context, handles
from ...dsl import ir, ast, ast_nd
from ..envobj import EnvsObj


class NDSimplificationPass(Transform):
    requires = ()
    produces = ()
    name = 'nd_simplify'

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        return self.visit(root)

    @handles(ir.Forall)
    def _(self, node: ir.Forall) -> ir.Node:
        T, lam = self.visit_children(node)
        func = tp.cast(ast.FuncExpr, ast.wrap(lam))
        if func.domain.T.has_view:
            new_lam = (func @ func.domain.idx_lam)
            return node.replace(T, new_lam.node)
        return node.replace(T, lam)
 