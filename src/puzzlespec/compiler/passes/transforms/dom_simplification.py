from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast, ast_nd
from ....libs import std
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
        T, *doms = self.visit_children(node)
        if len(doms)==0:
            domT = ir.DomT(ir.TupleT())
            return ir.Singleton(domT, ir.TupleLit(ir.TupleT()))
        if all(isinstance(dom, ir.Singleton) for dom in doms):
            elems = [ir.Unique(ast.wrapT(dom.T).carT.node, dom) for dom in doms]
            return ir.Singleton(T, ir.TupleLit(T.carT, *elems))
        return node.replace(T, *doms)

    @handles(ir.DisjUnion)
    def _(self, node: ir.DisjUnion):
        T, *doms = self.visit_children(node)
        if len(doms)==0:
            domT = ir.DomT(ir.SumT())
            return ir.Empty(domT)
        return node.replace(T, *doms)
        
    @handles(ir.DomProj)
    def _(self, node: ir.DomProj):
        T, dom = self.visit_children(node)
        if isinstance(dom, ir.CartProd):
            cart_doms = dom._children[1:]
            assert node.idx < len(cart_doms)
            new_dom = cart_doms[node.idx]
            assert ast.wrapT(T)==ast.wrapT(new_dom.T)
            return new_dom
        #elif isinstance(dom, ir.Image):
        #    T_img, lam = dom._children
        #    T_img_ast = ast.wrapT(T_img)
        #    if isinstance(T_img_ast, ast_nd.NDDomainExpr):
        #        shape = T_img_ast.shape
        #        
        #        lam_ast = ast.wrap(lam)
            
        return node.replace(T, dom)

    @handles(ir.Card)
    def _(self, node: ir.Card):
        T, dom = self.visit_children(node)
        if isinstance(dom, ir.Fin):
            _, N = dom._children
            return N
        if isinstance(dom, ir.Singleton):
            return ir.Lit(ir.IntT(), val=1)
        if isinstance(dom, ir.DomLit) and dom.is_set:
            # Card(DomLit(T, *elems)) = len(elems)
            num_elems = len(dom._children[1:])
            return ir.Lit(ir.IntT(), val=num_elems)
        if isinstance(dom, ir.Slice):
            _, dom, lo, hi, step = dom._children
            lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
            size = (hi-lo)//step
            return size.node
        if isinstance(dom, ir.Range):
            _, lo, hi, step = dom._children
            lo, hi, step = ast.IntExpr(lo), ast.IntExpr(hi), ast.IntExpr(step)
            size = (hi-lo)//step
            return size.node
        if isinstance(dom, ir.CartProd):
            doms = dom._children[1:]
            return ir.Prod(ir.IntT(), *(ir.Card(ir.IntT(), d) for d in doms))
        if isinstance(dom, ir.DisjUnion):
            doms = dom._children[1:]
            return ir.Sum(ir.IntT(), *(ir.Card(ir.IntT(), d) for d in doms))
        if isinstance(dom, ir.Image):
            _, func = dom._children
            func_ast = ast.wrap(func)
            if func_ast.known_inj:
                return func_ast.domain.size.node
        return node.replace(T, dom)

    @handles(ir.Unique)
    def _(self, node: ir.Unique):
        T, dom = self.visit_children(node)
        if isinstance(dom, ir.Singleton):
            _, val = dom._children
            return val
        return node.replace(T, dom)

    @handles(ir.Image)
    def _(self, node: ir.Image):
        T, func = self.visit_children(node)
        if isinstance(func, ir._Lambda):
            func_ast = ast.FuncExpr(func)
            dom = func_ast.domain.node
            if func in self.ids:
                return dom
            if isinstance(dom, ir.Singleton):
                return func_ast.apply(func_ast.domain.unique_elem).as_singleton.node
            if isinstance(dom, ir.Image):
                _, func2 = dom._children
                if isinstance(func2, ir._Lambda):
                    func2_ast = ast.wrap(func2)
                    return (func_ast @ func2_ast).image.node
        return node.replace(T, func)

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, body = self.visit_children(node)
        bv_name = node.bv_name
        if isinstance(body, ir.BoundVarHOAS) and body.name==bv_name:
            self.ids.add(node)
        return node.replace(T, body)

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        T, func = self.visit_children(node)
        if isinstance(func, ir._Lambda):
            piT, body = func._children
            argT, resT = piT._children
            if isinstance(argT, ir.RefT):
                _, dom = argT._children
                if isinstance(dom, ir.Restrict):
                    T_i, func_i = dom._children
                    new_func = ast.wrap(func_i).imap(lambda i, v: ast.wrap(func)(i) & v)
                    return ir.Restrict(T, new_func.node)
        return node.replace(T, func)

    @handles(ir.Intersection)
    def _(self, node: ir.Intersection) -> ir.Node:
        T, *doms = self.visit_children(node)
        if len(doms)==0:
            return ir.Universe(T)
        if len(doms)==1:
            return doms[0]
        new_doms = []
        for dom in doms:
            if isinstance(dom, ir.Empty):
                return dom
            if isinstance(dom, ir.Universe) and not isinstance(dom.T, ir.RefT):
                continue
            elif isinstance(dom, ir.Intersection):
                new_doms.extend(dom._children[1:])
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
                T, func = rdom._children
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
        return node.replace(T, *_new_doms)

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember):
        T, dom, val = self.visit_children(node)
        if isinstance(dom, ir.Restrict):
            T, func = dom._children
            f = ast.wrap(func)
            v = ast.wrap(val)
            return (f.domain.contains(v) & f(v)).node
        #if isinstance(dom, ir.Fin):
        #    return (ast.wrap(val) < ast.wrap(dom).size).node
        if isinstance(dom, ir.CartProd) and isinstance(val, ir.TupleLit):
            d = ast.wrap(dom)
            v = ast.wrap(val)
            return std.all((d.dom_proj(i).contains(v[i]) for i, vi in enumerate(v))).node
        return node.replace(T, dom, val)

    # NOT SOUND. Only shoud discharge if subset is proven
    #@handles(ir.IsMember)
    #def _(self, node: ir.IsMember):
    #    T, dom, val = self.visit_children(node)
    #    if isinstance(val.T, ir.RefT):
    #        _, refdom = val.T._children
    #        return (ast.wrap(refdom) <= ast.wrap(dom)).node
    #    return node.replace(T, dom, val)
