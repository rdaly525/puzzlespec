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


class RefineAdd(Transform):
    """Adds appropriate refinements
    """
    name = "refine_simplify"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        new_root = self.visit(root)
        return new_root

    @handles(ir.RefT)
    def _(self, node: ir.RefT):
        T, dom = self.visit_children(node)
        # can remove refine dom if dom is Universe
        if isinstance(dom, ir.Universe):
            return T
        return node.replace(T, dom)

    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        T, = self.visit_children(node)
        if isinstance(T, ir.RefT):
            T = T.T
        return node.replace(T)

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

    #@handles(ir.Mod)
    #def _(self, node: ir.Mod):
    #    T, left, right = self.visit_children(node)
    #    if isinstance(left.T, ir.RefT) and isinstance(right.T, ir.RefT):
    #        ldom = left.T.dom
    #        rdom = left.T.dom
    #        # {Int | Fin(5)} + {Int | Fin(7)}
    #        # -> Int | Interval(0, 5+7)
    #    return node.replace(T, left, right)

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
 