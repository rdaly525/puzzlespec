from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast, ast_nd
from ....libs import std
from ._obl_utils import _with_obl
import typing as tp


class DomainSimplificationPass(Transform):
    """
    - Simplifies domain expressions
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "dom_simplification"
    #_debug=True

    def run(self, root: ir.Node, ctx: Context):
        self.ids = set()
        new_root = self.visit(root)
        return new_root

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        vc = self.visit_children(node)
        T = vc.T
        doms = list(vc.children)
        if len(doms)==0:
            domT = ir.DomT(ir.TupleT())
            return _with_obl(ir.Singleton(domT, ir.TupleLit(ir.TupleT())), vc.obl)
        if all(isinstance(dom, ir.Singleton) for dom in doms):
            elems = [ir.Unique(ast.wrapT(dom.T).carT.node, dom) for dom in doms]
            return _with_obl(ir.Singleton(T, ir.TupleLit(T.carT, *elems)), vc.obl)
        return node.replace(*doms, T=T, obl=vc.obl)

    @handles(ir.DisjUnion)
    def _(self, node: ir.DisjUnion):
        vc = self.visit_children(node)
        T = vc.T
        doms = list(vc.children)
        if len(doms)==0:
            domT = ir.DomT(ir.SumT())
            return _with_obl(ir.Empty(domT), vc.obl)
        return node.replace(*doms, T=T, obl=vc.obl)

    @handles(ir.DomProj)
    def _(self, node: ir.DomProj):
        vc = self.visit_children(node)
        T = vc.T
        dom, = vc.children
        if isinstance(dom, ir.CartProd):
            cart_doms = list(dom._children)
            assert node.idx < len(cart_doms)
            new_dom = cart_doms[node.idx]
            assert ast.wrapT(T)==ast.wrapT(new_dom.T)
            return _with_obl(new_dom, vc.obl)
        return node.replace(dom, T=T, obl=vc.obl)

    @handles(ir.Card)
    def _(self, node: ir.Card):
        vc = self.visit_children(node)
        T = vc.T
        dom, = vc.children
        if isinstance(dom, ir.Fin):
            N, = dom._children
            return _with_obl(N, vc.obl)
        if isinstance(dom, ir.Singleton):
            return _with_obl(ir.Lit(ir.IntT(), val=1), vc.obl)
        if isinstance(dom, ir.DomLit) and dom.is_set:
            num_elems = len(dom._children)
            return _with_obl(ir.Lit(ir.IntT(), val=num_elems), vc.obl)
        if isinstance(dom, ir.Slice):
            dom_inner, lo, hi, step = dom._children
            lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
            size = (hi-lo)//step
            return _with_obl(size.node, vc.obl)
        if isinstance(dom, ir.Range):
            lo, hi, step = dom._children
            lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
            size = (hi-lo)//step
            return _with_obl(size.node, vc.obl)
        if isinstance(dom, ir.CartProd):
            cart_doms = list(dom._children)
            result = ir.Prod(ir.IntT(), *(ir.Card(ir.IntT(), d) for d in cart_doms))
            return _with_obl(result, vc.obl)
        if isinstance(dom, ir.DisjUnion):
            union_doms = list(dom._children)
            result = ir.Sum(ir.IntT(), *(ir.Card(ir.IntT(), d) for d in union_doms))
            return _with_obl(result, vc.obl)
        if isinstance(dom, ir.Image):
            func, = dom._children
            func_ast = ast.wrap(func)
            if func_ast.known_inj:
                return _with_obl(func_ast.domain.size.node, vc.obl)
        return node.replace(dom, T=T, obl=vc.obl)

    @handles(ir.Unique)
    def _(self, node: ir.Unique):
        vc = self.visit_children(node)
        T = vc.T
        dom, = vc.children
        if isinstance(dom, ir.Singleton):
            val, = dom._children
            return _with_obl(val, vc.obl)
        return node.replace(dom, T=T, obl=vc.obl)

    @handles(ir.Image)
    def _(self, node: ir.Image):
        vc = self.visit_children(node)
        T = vc.T
        func, = vc.children
        if isinstance(func, ir._Lambda):
            func_ast = ast.FuncExpr(func)
            dom = func_ast.domain.node
            if func in self.ids:
                return _with_obl(dom, vc.obl)
            if isinstance(dom, ir.Singleton):
                return _with_obl(func_ast.apply(func_ast.domain.unique_elem).as_singleton.node, vc.obl)
            if isinstance(dom, ir.Image):
                func2, = dom._children
                if isinstance(func2, ir._Lambda):
                    func2_ast = ast.wrap(func2)
                    return _with_obl((func_ast @ func2_ast).image.node, vc.obl)
        return node.replace(func, T=T, obl=vc.obl)

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        vc = self.visit_children(node)
        body, = vc.children
        bv_name = node.bv_name
        if isinstance(body, ir.BoundVarHOAS) and body.name==bv_name:
            self.ids.add(node)
        return node.replace(body, T=vc.T, obl=vc.obl)

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        vc = self.visit_children(node)
        T = vc.T
        func, = vc.children
        if isinstance(func, ir._Lambda):
            body, = func._children
            piT = func.T
            argT, resT = piT._children
            if argT.ref is not None:
                dom = argT.ref
                if isinstance(dom, ir.Restrict):
                    func_i, = dom._children
                    new_func = ast.wrap(func_i).imap(lambda i, v: ast.wrap(func)(i) & v)
                    return _with_obl(ir.Restrict(T, new_func.node), vc.obl)
        return node.replace(func, T=T, obl=vc.obl)

    @handles(ir.Intersection)
    def _(self, node: ir.Intersection) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        doms = list(vc.children)
        if len(doms)==0:
            return _with_obl(ir.Universe(T), vc.obl)
        if len(doms)==1:
            return _with_obl(doms[0], vc.obl)
        new_doms = []
        for dom in doms:
            if isinstance(dom, ir.Empty):
                return _with_obl(dom, vc.obl)
            if isinstance(dom, ir.Universe) and dom.T.ref is None:
                continue
            elif isinstance(dom, ir.Intersection):
                new_doms.extend(dom._children)
            else:
                new_doms.append(dom)
        _new_doms = []
        for i, dom in enumerate(new_doms):
            if dom in new_doms[i+1:]:
                continue
            _new_doms.append(dom)
        rdoms = []
        nrdoms = []
        for dom in _new_doms:
            if isinstance(dom, ir.Restrict):
                rdoms.append(dom)
            else:
                nrdoms.append(dom)
        if len(rdoms) > 1:
            doms = []
            funcs = []
            for rdom in rdoms:
                func, = rdom._children
                func_ast = ast.wrap(func)
                dom = func_ast.domain
                doms.append(dom)
                funcs.append(func_ast)
            def lam(e, funcs=funcs):
                res = 1
                for func in funcs:
                    res &= func(e)
                return res
            rdom = doms[0].intersect(*doms[1:]).restrict(lam)
            _new_doms = nrdoms + [rdom.node]
        return node.replace(*_new_doms, T=T, obl=vc.obl)

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember):
        vc = self.visit_children(node)
        T = vc.T
        dom, val = vc.children
        if isinstance(dom, ir.Restrict):
            func, = dom._children
            f = ast.wrap(func)
            v = ast.wrap(val)
            return _with_obl((f.domain.contains(v) & f(v)).node, vc.obl)
        if isinstance(dom, ir.CartProd):
            d = ast.wrap(dom)
            v = ast.wrap(val)
            return _with_obl(std.all((d.dom_proj(i).contains(vi) for i, vi in enumerate(v))).node, vc.obl)
        return node.replace(dom, val, T=T, obl=vc.obl)

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        vc = self.visit_children(node)
        T = vc.T
        lam, arg = vc.children
        if isinstance(lam, ir.Compose):
            ret = ast.wrap(arg)
            for clam in reversed(list(lam._children)):
                ret = ast.wrap(clam)(ret)
            return _with_obl(ret.node, vc.obl)
        return node.replace(lam, arg, T=T, obl=vc.obl)
