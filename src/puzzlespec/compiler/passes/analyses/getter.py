from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT

class VarSet(AnalysisObject):
    def __init__(self, vars: tp.Set[ir.Node]):
        self.vars = vars

class ParamGetter(Analysis):
    produces = (VarSet,)
    name = "param_getter"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        return VarSet(self.visit(root))

    def visit(self, node: ir.Node):
        params: tp.List[tp.Set[ir.Node]] = self.visit_children(node)
        val = set()
        for pset in params:
            val |= pset
        return val       

    @handles(ir._Param)
    def _(self, node):
        return set([node])

class VarGetter(Analysis):
    produces = (VarSet,)
    name = 'var_getter'

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        return VarSet(self.visit(root))

    def visit(self, node: ir.Node):
        vars: tp.List[tp.Set[ir.Node]] = self.visit_children(node)
        val = set()
        for pset in vars:
            val |= pset
        return val       

    @handles(ir.VarRef)
    def _(self, node):
        return set([node])

