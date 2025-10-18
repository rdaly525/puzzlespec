# This provides a pass to categorize a single constraint and extract its variables
# A Param constraint is a constraint that is only dependent on the parameters
# A Gen constraint is a constraint that is only dependent on the generator variables and Params
# A Decision constraint is a constraint that depends on any decision variables
# If there is no dependency, then it is a constant constraint

from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from . import SymTableEnv_

class ConstraintCategorizerVals(AnalysisObject):
    def __init__(self, mapping: tp.Dict[ir.Node, str]):
        self.mapping = mapping

class ConstraintCategorizer(Analysis):
    requires = (SymTableEnv_,)
    produces = (ConstraintCategorizerVals,)
    name = "constraint_categorizer"

    # Include categorization of _Param ?
    def __init__(self, include_params: bool=False):
        self.include_params = include_params

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.sym = tp.cast(SymTableEnv_, ctx.get(SymTableEnv_)).sym
        # Visit the constraint to categorize it and collect variables
        self.visit(root)
        return ConstraintCategorizerVals(self._cache)

    def visit(self, node: ir.Node):
        cvals = self.visit_children(node)
        if 'D' in cvals:
            return 'D'
        if 'G' in cvals:
            return 'G'
        if 'P' in cvals:
            return 'P'
        return 'C'

    @handles(ir.VarRef)
    def _(self, var: ir.VarRef):
        role = self.sym.get_role(var.sid)
        return role

    @handles(ir._Param, mark_invalid=True)
    def _(self, node):
        ...
