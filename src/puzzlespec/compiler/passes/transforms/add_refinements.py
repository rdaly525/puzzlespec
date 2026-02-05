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
            refT = ir.RefT(dom.T.rawT.carT, dom)
            sid_to_rvar[sid] = ir.VarRef(refT, sid)

        return RefineMap(sid_to_rvar)

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        self.visit_children(node)
        if node.sid not in self.sid_to_rdoms:
            self.sid_to_rdoms[node.sid] = []
        if isinstance(node.T, ir.RefT):
            T, dom = node.T._children
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
        new_root = self.visit(root)
        return new_root

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        T, N = self.visit_children(node)
        return ast.wrap(node).refine(lambda _: ast.wrap(N) >=0).node

    @handles(ir.Mod, ir.Div)
    def _(self, node: ir.Value):
        T, a, b = self.visit_children(node)
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
        self.tmap: tp.Mapping[ir.Node, ir.RefT] = {}
        return new_root

    #@handles(ir.Add)
    #def _(self, node: ir.Add):
    #    T, left, right = self.visit_children(node)
    #    assert isinstance(left.T, ir.RefT) and isinstance(right.T, ir.RefT)
    #    refT_l = self.tmap[left]
    #    refT_r = self.tmap[right]
    #    ldom = ast.DomainExpr(refT_l.dom)
    #    rdom = ast.DomainExpr(refT_r.dom)
    #    new_dom = (ldom * rdom).map(lambda l, r: l+r).image
    #    refT = ir.RefT(T, new_dom.node)
    #    self.tmap[node] = refT
    #    return node.replace(refT, left, right)
 