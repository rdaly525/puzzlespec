from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ast
from ..envobj import EnvsObj

def gen_enumerate(node: ir._DomT) -> ir.Enumerate:
    lam = get_elem_lam(node)
    T = ir.FuncT(
        ir.Fin(ir.DomT(ir.IntT(), True, False), ir.Card(ir.IntT(), node)),
        lamT = lam.T._node
    )
    node = ir.Enumerate(T, node)
    return node

def get_elem_lam(node: ir._DomT) -> ast.LambdaExpr:
    if not node.T.ord:
        raise ValueError()
    np = OrdAnalysis()(node, Context()).node_map
    assert node in np
    return np[node]

class OrdMap(AnalysisObject):
    def __init__(self, node_map: tp.Dict[ir.Node, ast.LambdaExpr]):
        self.node_map=node_map

class OrdAnalysis(Analysis):
    requires = ()
    produces = (OrdMap,)
    name = 'ord'

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.node_map = {}
        self.visit(root)
        return OrdMap(self.node_map)

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        self.visit_children(node)
        assert node.T.ord
        fin = ast.wrap(node)
        lam = ast.LambdaExpr.make(lambda i: i.refine(fin), ast.Int)
        self.node_map[node] = lam

    @handles(ir.Range)
    def _(self, node: ir.Range):
        self.visit_children(node)
        assert node.T.ord
        T, lo, hi, step = node._children
        lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
        lam = ast.LambdaExpr.make(lambda i: (lo+i*step).refine(ast.wrap(node)), ast.Int)
        self.node_map[node] = lam

    @handles(ir.Slice)
    def _(self, node: ir.Slice):
        self.visit_children(node)
        T, dom, lo, hi, step = node._children
        assert dom in self.node_map
        lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
        lam_s = ast.LambdaExpr.make(lambda i: (lo+i*step), ast.Int)
        lam = lam_s @ self.node_map[dom]
        self.node_map[node] = lam
        
    @handles(ir.Image)
    def _(self, node: ir.Image):
        self.visit_children(node)
        T, func = node._children
        if T.ord:
            if isinstance(func, ir.Map):
                T_f, dom_f, lam_f = func._children
                assert lam_f.T.inj
                if dom_f not in self.node_map:
                    raise ValueError()
                assert dom_f in self.node_map
                lam = ast.wrap(lam_f) @ self.node_map[dom_f]
                self.node_map[node] = lam

OrdMap.gen_pass = OrdAnalysis