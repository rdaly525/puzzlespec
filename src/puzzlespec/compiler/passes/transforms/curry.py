from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast
import typing as tp


class CurryPass(Transform):
    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "curry"

    def __init__(self, all: bool= True):
        super().__init__()

    def run(self, root: ir.Node, ctx: Context):
        self.cmap: tp.Mapping[ir.Node, tp.Tuple[ast.FuncExpr, int]] = {}
        new_root = self.visit(root)
        return new_root

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, body = self.visit_children(node)
        new_lam = node.replace(T, body)
        lam = tp.cast(ast.FuncExpr, ast.wrap(new_lam))
        if isinstance(lam.domain.node, ir.CartProd):
            N = len(lam.domain.T.carT)
            doms = [lam.domain.dom_proj(i) for i in range(N)]
            def make_clam(bvs=None):
                if bvs is None:
                    bvs = []
                def clam(bi, bvs=bvs):
                    bvs = bvs + [bi]
                    if len(bvs)== N:
                        b = ast.TupleExpr.make(tuple(bvs))
                        return lam(b)
                    else:
                        domi = doms[len(bvs)]
                        next_clam = make_clam(bvs)
                        clami = domi.map(next_clam)
                        return clami
                return clam
            clam = doms[0].map(make_clam())
            self.cmap[new_lam] = (clam, N)
        return new_lam

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        T, lam, arg = self.visit_children(node)
        vals = self.cmap.get(lam, None)
        if vals is not None:
            clam, N = vals
            a = ast.wrap(arg)
            for i in range(N):
                ai = a[i]
                clam = clam(ai)
            return clam.node
        return node.replace(T, lam, arg)


        

 