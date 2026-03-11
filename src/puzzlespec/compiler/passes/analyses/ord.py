from __future__ import annotations

import typing as tp

from puzzlespec.compiler.passes.analyses.type_check import stripT

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ast, ast_nd
from ....libs import std
from ..envobj import EnvsObj

def gen_enumerate(node: ir.DomT) -> ast.FuncExpr:
    dom = ast.wrap(node)
    dom_fin = dom.size.fin()
    lam = get_elem_lam(node)
    return dom_fin.map(lam, inj=True)
    #fin_dom = ir.Fin(ir.DomT(ir.IntT(), True, False), ir.Card(ir.IntT(), node))
    #T = ir.FuncT(
    #    fin_dom,
    #    lamT = lam.T._node
    #)
    #node = ir.Enumerate(T, node)
    #return fin_dom, node

def get_elem_lam(node: ir.DomT) -> ast.LambdaExpr:
    if not ast.wrap(node).T._is_enumerable:
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

    def visit(self, node: ir.Node):
        if isinstance(node, ir.Value):
            if isinstance(stripT(node.T), ir.DomT):
                raise ValueError()

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        self.visit_children(node)
        fin = ast.wrap(node)
        lam = ast.FuncExpr.make(fin, lambda i: i)
        self.node_map[node] = lam

    @handles(ir.Range)
    def _(self, node: ir.Range):
        self.visit_children(node)
        T, lo, hi, step = node._children
        lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
        fin = ast.wrap(node).size.fin()
        lam = ast.FuncExpr.make(fin, lambda i: (lo+i*step), inj=True)
        self.node_map[node] = lam

    @handles(ir.Slice)
    def _(self, node: ir.Slice):
        self.visit_children(node)
        T, dom, lo, hi, step = node._children
        assert dom in self.node_map
        lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
        fin = ast.wrap(node).size.fin()
        lam_s = ast.FuncExpr.make(fin, lambda i: (lo+i*step), inj=True)
        lam = lam_s @ self.node_map[dom]
        self.node_map[node] = lam

    @handles(ir.Singleton)
    def _(self, node: ir.Singleton):
        self.visit_children(node)
        T, val = node._children
        self.node_map[node] = ast.FuncExpr.make(std.fin(1), lambda i: ast.wrap(node).unique_elem, inj=True)

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        self.visit_children(node)
        T, *doms = node._children
        for dom in doms:
            if dom not in self.node_map:
                raise ValueError(f"Dom {dom} not in node map")
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
        fin = std.fin(ast.wrap(node).size)
        self.node_map[node] = ast.FuncExpr.make(fin, lam, inj=True)

    @handles(ir.Image)
    def _(self, node: ir.Image):
        self.visit_children(node)
        T, func = node._children
        if ast.wrap(node).T._is_enumerable:
            if isinstance(func, ir._Lambda):
                piT, body = func._children
                func_ast = ast.wrap(func)
                assert func_ast.known_inj
                dom = func_ast.domain.node
                if dom not in self.node_map:
                    raise ValueError()
                lam = func_ast @ self.node_map[dom]
                self.node_map[node] = lam

    #@handles(ir.DomProj)
    #def _(self, node: ir.DomProj):
    #    self.visit_children(node)
    #    T, dom, idx = node._children
    #    assert dom in self.node_map
    #    prod_func = self.node_map[dom]
    #    
    #    assert dom in self.node_map
    #    fin = ast_nd.fin(ast.wrap(node).size)
    #    lam = ast.FuncExpr.make(fin, lambda i: ast.wrap(node)[i], inj=True)
    #    self.node_map[node] = lam

OrdMap.gen_pass = OrdAnalysis