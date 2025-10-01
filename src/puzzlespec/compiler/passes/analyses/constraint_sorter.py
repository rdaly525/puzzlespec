# This provides a pass to sort the constraints into param, gen, and decision constraints
# A Param constraint is a constraint that is only dependent on the parameters
# A Gen constraint is a constraint that is only dependent on the generator variables and Params
# A Decison constraint is a constraint that depends on any decision variables
# If there is no dependency, then it is a constant constraint

from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from . import RoleEnv_

class ConstraintSorterVals(AnalysisObject):
    def __init__(self):
        self.param_constraints = []
        self.gen_constraints = []
        self.decision_constraints = []
        self.constant_constraints = []

class ConstraintSorter(Analysis):
    requires = (RoleEnv_)
    produces = (ConstraintSorterVals,)
    name = "constraint_sorter"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        # root node must be a conjunction node
        if not isinstance(root, ir.Conj):
            raise ValueError("Root node must be a conjunction node")
        self.roles = tp.cast(RoleEnv_, ctx.get(RoleEnv_)).env.roles
        vals = ConstraintSorterVals()
        for child in root._children:
            self.seen_params = False
            self.seen_gen = False
            self.seen_decision = False
            self.visit(child)
            if self.seen_decision:
                vals.decision_constraints.append(child)
            elif self.seen_gen:
                vals.gen_constraints.append(child)
            elif self.seen_params:
                vals.param_constraints.append(child)
            else:
                vals.constant_constraints.append(child)
        return vals

    @handles(ir.Param)
    def visit_param(self, node: ir.Param):
        self.seen_params = True
        return node
    
    @handles(ir.FreeVar, ir.VarList, ir.VarDict)
    def visit_free_var(self, var: ir.Node):
        assert hasattr(var, "name")
        assert var.name in self.roles
        if self.roles[var.name] == 'G':
            self.seen_gen = True
        elif self.roles[var.name] == 'D':
            self.seen_decision = True
        else:
            raise ValueError(f"Role, {self.roles[var.name]}, not valid")
        return var