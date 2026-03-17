from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, Transform, Context, handles, AnalysisObject
from ..transforms.substitution import SubMapping, SubstitutionPass
from ...dsl import ir, ast
from ....libs import var_def, std
from ..envobj import EnvsObj, SymTable


# This is the 'bottom up' version of refine
# a: Fin(5) + b: Fin(6) -> (a+b): Fin(10)
class RefineBottomUp(Transform):
    """Combines refinements
    """
    name = "refine_bo"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        new_root = self.visit(root)
        return new_root

    def _get_dom(self, node: ir.Node) -> ast.DomainExpr | None:
        return ast.wrap(node).T.ref_dom
    #Not: 100,
    @handles(ir.Not)
    def _(self, node: ir.Not):
        a, = self.visit_children(node)

    @handles(ir.Sum)
    def _(self, node: ir.Sum):
        vc = self.visit_children(node)
        T = vc.T
        vals = list(vc.children)
        assert all(val.T.ref is not None for val in vals)
        doms = [ast.wrap(val).T.ref_dom for val in vals]
        ref_dom = ast.cartprod(*doms).map(lambda indices: sum(indices, ast.IntExpr.make(0))).image
        return ast.wrap(node).refine(ref_dom).node
