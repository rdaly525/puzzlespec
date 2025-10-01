# This provides passes to get all parameters and variables

from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from .type_inference import TypeValues
from .roles import RoleEnv_


class GetterVals(AnalysisObject):
    def __init__(self, param_vals: dict, gen_vals: dict, decision_vals: dict):
        self.param_vals = param_vals
        self.gen_vals = gen_vals
        self.decision_vals = decision_vals


class Getter(Analysis):
    """
    Get all the variables/params of a given kind
    """
   
    requires = (RoleEnv_,)
    produces = (GetterVals,)
    name = "getter"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.roles = tp.cast(RoleEnv_, ctx.get(RoleEnv_)).env.roles
        self.param_vals = {}
        self.gen_vals = {}
        self.decision_vals = {}
        self.visit(root)
        return GetterVals(self.param_vals, self.gen_vals, self.decision_vals)

    @handles(ir.Param)
    def visit_param(self, node: ir.Param):
        assert node.name not in self.param_vals or self.param_vals[node.name] is node
        self.param_vals[node.name] = node
        return node
    
    @handles(ir.FreeVar, ir.VarList, ir.VarDict)
    def visit_free_var(self, var: ir.Node):
        assert var.name in self.roles
        if self.roles[var.name] == 'G':
            assert var.name not in self.gen_vals or self.gen_vals[var.name] is var
            self.gen_vals[var.name] = var
        elif self.roles[var.name] == 'D':
            assert var.name not in self.decision_vals or self.decision_vals[var.name] is var
            self.decision_vals[var.name] = var
        else:
            raise ValueError(f"Role, {self.roles[var.name]}, not valid")
        return var