from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, Transform, Context, handles, AnalysisObject
from ..transforms.substitution import SubMapping, SubstitutionPass
from ...dsl import ir, ast
from ....libs import var_def, std
from ..envobj import EnvsObj, SymTable


def free_var_refine(node: ir.Node):
    rmap = FreeVarRefineA()(node, Context()).map
    submap = SubMapping()
    for sid, rvar in rmap.items():
        submap.add(
            match = lambda node, sid=sid: isinstance(node, ir.VarRef) and node.sid==sid,
            replace = lambda node, val=rvar: val
        )
    ctx = Context(submap)
    new_node = SubstitutionPass()(node, ctx)[0]
    return new_node

class RefineMap(AnalysisObject):
    def __init__(self, m):
        self.map = m

class FreeVarRefineA(Analysis):
    """Creates single node for each free var with appropriate refinement
    """
    name = "free_var_refine"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.sid_to_rdoms = {}
        self.visit(root)
        sid_to_rvar = {}
        for sid, doms in self.sid_to_rdoms.items():
            if len(doms)==0:
                continue
            dom = ir.Intersection(doms[0].T, *doms)
            carT = dom.T.rawT.carT
            refT = carT.replace(ref=dom, view=None, obl=None)
            sid_to_rvar[sid] = ir.VarRef(refT, sid)

        return RefineMap(sid_to_rvar)

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        self.visit_children(node)
        if node.sid not in self.sid_to_rdoms:
            self.sid_to_rdoms[node.sid] = []
        if node.T.ref is not None:
            dom = node.T.ref
            self.sid_to_rdoms[node.sid].append(dom)

def add_refinements(node: ir.Node):
    assert isinstance(node, ir.Node)
    node = RefineAdd()(node, Context())[0]
    return node

# Any node assumptions
class RefineAdd(Transform):
    """Adds appropriate refinements
    """
    name = "refine_simplify"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        assert 0
        new_root = self.visit(root)
        return new_root

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        vc = self.visit_children(node)
        T = vc.T
        N, = vc.children
        return ast.wrap(node).refine(lambda _: ast.wrap(N) >=0).node

    @handles(ir.Mod, ir.FloorDiv)
    def _(self, node: ir.Value):
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        return ast.wrap(node).refine(lambda _: ast.wrap(b)!=0).node


# This is the 'bottom up' version of refine
class RefineCombine(Transform):
    """Combines refinements
    """
    name = "refine_combine"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        new_root = self.visit(root)
        self.tmap: tp.Mapping[ir.Node, ir.Type] = {}
        return new_root
