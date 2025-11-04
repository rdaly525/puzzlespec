from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from . import EnvsObj

class VarSet(AnalysisObject):
    def __init__(self, vars: tp.Set[ir.Node]):
        self.vars = vars

class VarGetter(Analysis):
    requires = (EnvsObj,)
    produces = (VarSet,)
    name = 'var_getter'

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.domenv: 'DomEnv' = ctx.get(EnvsObj).domenv
        return VarSet(self.visit(root))

    def visit(self, node: ir.Node):
        vars: tp.List[tp.Set[ir.Node]] = self.visit_children(node)
        val = set()
        for pset in vars:
            val |= pset
        return val       

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        val = set([node])
        assert node.sid in self.domenv
        for dom in self.domenv.get_doms(node.sid):
            val |= self.visit(dom)

