from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir
from ..envobj import EnvsObj


def get_vars(node: ir.Node) -> tp.Set[ir.VarRef | ir.VarHOAS]:
    ctx = Context()
    varget = VarGetter()(node, ctx)
    return varget.vars

class VarSet(AnalysisObject):
    def __init__(self, vars: tp.Set[ir.Node]):
        self.vars = vars

class VarGetter(Analysis):
    requires = ()
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
    def _(self, node: ir.VarRef):
        return set([node])

def get_closed_vars(node: ir.Node):
    ctx = Context()
    varget = ClosedVarGetter()(node, ctx)
    return varget.vars

class ClosedVarGetter(Analysis):
    requires = ()
    produces = (VarSet,)
    name = 'closed_var_getter'

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.bvars = []
        return VarSet(self.visit(root))

    def visit(self, node: ir.Node):
        vars: tp.List[tp.Set[ir.Node]] = self.visit_children(node)
        val = set()
        for pset in vars:
            val |= pset
        return val       

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T_vars, bv_vars, body_vars = self.visit_children(node)
        vars = (T_vars | body_vars | bv_vars) | set((node._children[1]))
        return vars






#class VarPHGetter(Analysis):
#    requires = (EnvsObj,)
#    produces = (VarSet,)
#    name = 'phvar_getter'
#
#    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
#        vars = self.visit(root)
#        var_map = {v:vs for v, vs in self._cache.items() if isinstance(v, ir.VarHOAS)}
#        return VarSet(var_map)
#
#    def visit(self, node: ir.Node):
#        vars: tp.List[tp.Set[ir.Node]] = self.visit_children(node)
#        if isinstance(node, ir.VarHOAS):
#            val = set([node])
#        else:
#            val = set()
#        for pset in vars:
#            val |= pset
#        return val       

