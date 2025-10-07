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
    def __init__(self):
        self.param_vars: tp.Set[int] = set()
        self.gen_vars: tp.Set[int] = set()
        self.decision_vars: tp.Set[int] = set()
        self._params : tp.Dict[str, irT.Type_] = {}

    def add_sid(self, sid, role):
        if role=='G':
            self.gen_vars.add(sid)
        elif role=='D':
            self.decision_vars.add(sid)
        elif role=='P':
            self.param_vars.add(sid)
        else:
            raise ValueError(f"Role {role} not valid")

    def add_param(self, p: ir._Param):
        if p.name in self._params and self._params[p.name] != p.T:
            raise ValueError(f"Param, {p}, is inconsistent")
        self._params[p.name] = p.T

    @property   
    def category(self):
        if len(self.decision_vars) > 0:
            return 'D'
        if len(self.gen_vars) > 0:
            return 'G'
        if len(self._params) > 0 or len(self.param_vars) > 0:
            return 'P'
        return 'C'

class ConstraintCategorizer(Analysis):
    requires = (SymTableEnv_,)
    produces = (ConstraintCategorizerVals,)
    name = "constraint_categorizer"

    # Include categorization of _Param ?
    def __init__(self, include_params: bool=False):
        self.include_params = include_params

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.sym = tp.cast(SymTableEnv_, ctx.get(SymTableEnv_)).sym
        self.vals = ConstraintCategorizerVals()
        
        # Visit the constraint to categorize it and collect variables
        self.visit(root)
        ctx.add(self.vals)
        return root

    @handles(ir.VarRef)
    def _(self, var: ir.VarRef):
        role = self.sym.get_role(var.sid)
        self.vals.add_sid(var.sid, role)

    @handles(ir._Param)
    def _(self, p: ir._Param):
        self.vals.add_param(p)