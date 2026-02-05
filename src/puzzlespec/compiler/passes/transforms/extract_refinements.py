from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, Transform, Context, handles, AnalysisObject
from ..transforms.substitution import SubMapping, SubstitutionPass
from ...dsl import ir, ast
from ....libs import var_def, std
from ..envobj import EnvsObj, SymTable


# This removes refinements from non-bool operators
# And adds extracts from bool operators
class ExtractRefine(Transform):
    """Extracts refinements
    """
    name = "extract_refine"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        new_root = self.visit(root)
        return new_root

    @handles(ir.Sum)
    def _(self, node: ir.Sum):
        T, *vals = self.visit_children(node)
        assert all(isinstance(val.T, ir.RefT) for val in vals)
        doms = [ast.wrap(val).T.ref_dom for val in vals]
        ref_dom = ast.cartprod(*doms).map(lambda indices: sum(indices, ast.IntExpr.make(0))).image
        return ast.wrap(node).refine(ref_dom).node
 