from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ast, ast_nd
from ..envobj import EnvsObj

def gen_enumerate(node: ir._DomT) -> ast.FuncExpr:
    dom = ast.wrap(node)
    dom_fin = ast_nd.fin(dom.size)
    lam = get_elem_lam(node)
    return dom_fin.map(lam, _inj=True)
    #fin_dom = ir.Fin(ir.DomT(ir.IntT(), True, False), ir.Card(ir.IntT(), node))
    #T = ir.FuncT(
    #    fin_dom,
    #    lamT = lam.T._node
    #)
    #node = ir.Enumerate(T, node)
    #return fin_dom, node

def get_elem_lam(node: ir._DomT) -> ast.LambdaExpr:
    if not node.T.ord:
        raise ValueError()
    np = OrdAnalysis()(node, Context()).node_map
    if node not in np:
        raise ValueError()
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
    @handles(ir.Singleton)
    def _(self, node: ir.Singleton):
        self.visit_children(node)
        T, val = node._children
        self.node_map[node] = ast.LambdaExpr.make(lambda i: ast.wrap(val), ast.Int)

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        self.visit_children(node)
        T, *doms = node._children
        for dom in doms:
            assert dom in self.node_map
        Ns: tp.List[ast.IntExpr] = [ast.wrap(dom).size for dom in doms]
        base_lams = [self.node_map[dom] for dom in doms]
        def lam(i):
            idxs = []
            for N in reversed(Ns):
                idxs.append(i%N)
                i = i // N
            idxs = [base_lams[i](idx) for i, idx in enumerate(reversed(idxs))]
            return ast.TupleExpr.make(tuple(idxs))
        self.node_map[node] = ast.LambdaExpr.make(lam, ast.Int)

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