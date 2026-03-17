from __future__ import annotations
import math
from re import L

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast
from ....libs import std
from ._obl_utils import _with_obl
import typing as tp


def _partition(lst, pred) -> tp.Tuple[tp.List[ir.Node], tp.List[ir.Node]]:
    true_lst = []
    false_lst = []
    for item in lst:
        if pred(item):
            true_lst.append(item)
        else:
            false_lst.append(item)
    return true_lst, false_lst

class AlgebraicSimplificationPass(Transform):
    """
    - Applies simple identities (e.g., Add 0, Mul 1/0, etc.)
    - Simple var rewrites (x==x => True)
    - Simple boolean simplifications (Not(Not(x)) => x)

    Leaves non-constant structures intact.
    """
    #_debug = True
    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "alg_simplification"

    # Arithmetic

    @handles(ir.Neg)
    def _(self, node: ir.Neg) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        a, = vc.children

        # -(-x) => x
        match (a):
            case (ir.Neg(b)):
                return _with_obl(b, vc.obl)
            case (ir.Sum(terms)):
                result = ir.Sum(
                    ir.IntT(),
                    *(ir.Neg(ir.IntT(), t) for t in terms)
                )
                return _with_obl(result, vc.obl)

        return node.replace(a, T=T, obl=vc.obl)

    @handles(ir.Sum)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        children = list(vc.children)
        # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = sum([c.val for c in const_children])
        if const_val != 0:
            children = non_const_children + [ir.Lit(T, val=const_val)]
        else:
            children = non_const_children
        # Remove all (..., x, -x, ...)
        neg_children, non_neg_children = _partition(children, lambda c: isinstance(c, ir.Neg))
        children = non_neg_children
        for neg_child in neg_children:
            if neg_child._children[0] in children:
                children.remove(neg_child._children[0])
            else:
                children.append(neg_child)

        if len(children) == 1:
            return _with_obl(children[0], vc.obl)
        children.sort()
        return node.replace(*children, T=T, obl=vc.obl)

    @handles(ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        children = list(vc.children)
        # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = math.prod([c.val for c in const_children])
        match const_val:
            case 0:
                return _with_obl(ir.Lit(T, 0), vc.obl)
            case 1:
                children = non_const_children
            case _:
                children = non_const_children + [ir.Lit(T, const_val)]
        if len(children) == 1:
            return _with_obl(children[0], vc.obl)
        # TODO All this needs guards
        div_children, non_div_children = _partition(children, lambda c: isinstance(c, ir.TrueDiv))
        if len(div_children)>0:
            tops = [c._children[0] for c in div_children] + non_div_children
            bots = [c._children[1] for c in div_children]
            result = (std.prod(ast.wrap(t) for t in tops) / std.prod(ast.wrap(b) for b in bots)).node
            return _with_obl(result, vc.obl)

        # TODO these needs guards
        sqrt_children, non_sqrt_children = _partition(children, lambda c: isinstance(c, ir.Isqrt))
        # If there are multiple sqrt children, we can simplify them to a single sqrt
        if len(sqrt_children)>1:
            sqrt = std.isqrt(std.prod(ast.wrap(c._children[0]) for c in sqrt_children)).node
            children = non_sqrt_children + [sqrt]
        children.sort()
        return node.replace(*children, T=T, obl=vc.obl)

    # All this needs guards
    @handles(ir.Isqrt)
    def _(self, node: ir.Isqrt):
        vc = self.visit_children(node)
        T = vc.T
        a, = vc.children
        if isinstance(a, ir.Prod):
            terms = list(a._children)
            outs = []
            ins = []
            i=0
            while (i < len(terms)-1):
                if terms[i]==terms[i+1]:
                    outs.append(terms[i])
                    i+=2
                else:
                    ins.append(terms[i])
                    i += 1
            if len(outs) > 0:
                result = std.prod([ast.wrap(v) for v in outs] + [std.isqrt(std.prod(ast.wrap(v) for v in ins))]).node
                return _with_obl(result, vc.obl)
        return node.replace(a, T=T, obl=vc.obl)

    @handles(ir.TrueDiv)
    def _(self, node: ir.TrueDiv):
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        if a==b:
            return _with_obl(ir.Lit(T, 1), vc.obl)
        match (a, b):
            case (_, ir.Lit(val=1)):
                return _with_obl(a, vc.obl)
            case (ir.Lit(val=0), _):
                return _with_obl(ir.Lit(T, 0), vc.obl)
        if isinstance(a, ir.TrueDiv):
            c, d = a._children
            result = ((ast.wrap(b)*ast.wrap(c))/ast.wrap(d)).node
            return _with_obl(result, vc.obl)
        if isinstance(b, ir.TrueDiv):
            c, d = b._children
            result = ((ast.wrap(a)*ast.wrap(d))/ast.wrap(c)).node
            return _with_obl(result, vc.obl)
        if isinstance(b, ir.Isqrt):
            result = ((ast.wrap(a)*ast.wrap(b))/ast.wrap(b._children[0])).node
            return _with_obl(result, vc.obl)

        if isinstance(a, ir.Prod) or isinstance(b, ir.Prod):
            if isinstance(a, ir.Prod):
                tops = list(a._children)
            else:
                tops = [a]
            if isinstance(b, ir.Prod):
                bots = list(b._children)
            else:
                bots = [b]
            new_tops = []
            new_bots = list(bots)
            for t in tops:
                for i, b in enumerate(new_bots):
                    if t==b:
                        del new_bots[i]
                        break
                else:
                    new_tops.append(t)
            if len(new_tops)!=len(tops):
                top = std.prod(ast.wrap(t) for t in new_tops)
                bot = std.prod(ast.wrap(b) for b in new_bots)
                result = (top/bot).node
                return _with_obl(result, vc.obl)

        return node.replace(a, b, T=T, obl=vc.obl)

    @handles(ir.Conj)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        children = list(vc.children)
         # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = all([c.val for c in const_children])
        match const_val:
            case True:
                children = non_const_children
            case False:
                return _with_obl(ir.Lit(T, False), vc.obl)
        if len(children) == 1:
            return _with_obl(children[0], vc.obl)
        new_children = list(dict.fromkeys(children))
        return node.replace(*new_children, T=T, obl=vc.obl)

    @handles(ir.Disj)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        children = list(vc.children)
         # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = any([c.val for c in const_children])
        match const_val:
            case True:
                return _with_obl(ir.Lit(T, True), vc.obl)
            case False:
                children = non_const_children
        if len(children) == 1:
            return _with_obl(children[0], vc.obl)
        return node.replace(*children, T=T, obl=vc.obl)

    @handles(ir.FloorDiv)
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        if a==b:
            return _with_obl(ir.Lit(T, 1), vc.obl)
        match (a, b):
            case (_, ir.Lit(val=1)):
                return _with_obl(a, vc.obl)
            case (ir.Lit(val=0), _):
                return _with_obl(ir.Lit(T, 0), vc.obl)
            case (_, _):
                return node.replace(a, b, T=T, obl=vc.obl)

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        match (a, b):
            case (_, ir.Lit(val=1)):
                return _with_obl(ir.Lit(T, 0), vc.obl)
            case (ir.Lit(val=0), _):
                return _with_obl(ir.Lit(T, 0), vc.obl)
            case (_, _):
                return node.replace(a, b, T=T, obl=vc.obl)

    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        if a == b:
            return _with_obl(ir.Lit(T, True), vc.obl)
        match (a, b):
            case (ir.Lit(T=ir.BoolT(), val=val), b):
                result = b if val else ir.Not(T, b)
                return _with_obl(result, vc.obl)
            case (a, ir.Lit(T=ir.BoolT(), val=val)):
                result = a if val else ir.Not(T, a)
                return _with_obl(result, vc.obl)
        return node.replace(a, b, T=T, obl=vc.obl)

    # Booleans
    @handles(ir.Not)
    def _(self, node: ir.Not) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        a, = vc.children
        match (a):
            case (ir.Not(b)):
                return _with_obl(b, vc.obl)
        return node.replace(a, T=T, obl=vc.obl)

    @handles(ir.Implies)
    def _(self, node: ir.Implies) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        match (a, b):
            case (ir.Lit(val=True), _):
                return _with_obl(b, vc.obl)
            case (_, ir.Lit(val=True)):
                return _with_obl(ir.Lit(T, True), vc.obl)
            case (_, ir.Lit(val=False)):
                return _with_obl(ir.Not(T, a), vc.obl)
        return node.replace(a, b, T=T, obl=vc.obl)

    @handles(ir.Match)
    def _(self, node: ir.Match):
        vc = self.visit_children(node)
        T = vc.T
        scrut, *cases = vc.children
        #assert isinstance(scrut.T, ir.SumT)
        if isinstance(scrut, ir.Inj):
            idx = scrut.idx
            assert isinstance(idx, int)
            val, = scrut._children
            assert idx < len(cases)
            result = ir.Apply(T, cases[idx], val)
            return _with_obl(result, vc.obl)
        if isinstance(scrut, ir.SumLit):
            # Match(SumLit(tag, *elems), *branch_lams) -> ApplyFunc(FuncLit(...), tag)
            tag, *elems = scrut._children
            # Create Fin domain for indices
            n = len(elems)
            fin_domT = ir.DomT.make(carT=ir.IntT(), fin=True, ord=True)
            fin_dom = ir.Fin(fin_domT, ir.Lit(ir.IntT(), val=n))
            # Apply each branch lambda to its corresponding element
            func_elems = []
            val_map = {}
            for i in range(n):
                # Apply branch_lams[i] to elems[i]
                applied = ir.Apply(T, cases[i], elems[i])
                applied = self.visit(applied)  # Simplify the application
                func_elems.append(applied)
                # Map index i to position i in FuncLit
                idx_lit = ir.Lit(ir.IntT(), val=i)
                val_map[idx_lit._key] = i
            # Create FuncLit with Fin domain
            layout = ir._DenseLayout(val_map=val_map)
            lamT = ir.LambdaT(ir.IntT(), T)
            funcT = ir.FuncT(fin_dom, lamT)
            func_lit = ir.FuncLit(funcT, fin_dom, *func_elems, layout=layout)
            # Apply the function to tag
            result = ir.ApplyFunc(T, func_lit, tag)
            return _with_obl(result, vc.obl)
        return node.replace(scrut, *cases, T=T, obl=vc.obl)

    @handles(ir.Proj)
    def _(self, node: ir.Proj):
        vc = self.visit_children(node)
        T = vc.T
        tup, = vc.children
        if isinstance(tup, ir.TupleLit):
            elems = list(tup._children)
            assert node.idx < len(elems)
            return _with_obl(elems[node.idx], vc.obl)
        return node.replace(tup, T=T, obl=vc.obl)

    #(proj(bv,0), proj(bv,1))
    @handles(ir.TupleLit)
    def _(self, node: ir.TupleLit):
        vc = self.visit_children(node)
        T = vc.T
        elems = list(vc.children)
        if len(elems)>0 and all(isinstance(e, ir.Proj) and e.idx==i for i, e in enumerate(elems)):
            v0 = elems[0]._children[0]
            if all(v0==e._children[0] for e in elems):
                #Make sure that the proj value has the correct size
                if len(ast.wrap(v0).T)==len(elems):
                    return _with_obl(v0, vc.obl)
        return node.replace(*elems, T=T, obl=vc.obl)

    @handles(ir.LtEq)
    def _(self, node: ir.Node):
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        if a == b:
            return _with_obl(ast.BoolExpr.make(True).node, vc.obl)
        return node.replace(a, b, T=T, obl=vc.obl)

    @handles(ir.Lt)
    def _(self, node: ir.Node):
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        if a == b:
            return _with_obl(ast.BoolExpr.make(False).node, vc.obl)
        return node.replace(a, b, T=T, obl=vc.obl)

    @handles(ir.Subset)
    def _(self, node: ir.Node):
        vc = self.visit_children(node)
        T = vc.T
        a, b = vc.children
        if a == b:
            return _with_obl(ast.BoolExpr.make(True).node, vc.obl)
        if isinstance(a, ir.CartProd) and isinstance(b, ir.CartProd):
            assert len(a._children) == len(b._children)
            ps = []
            for ca, cb in zip(a._children, b._children):
                ps.append(ast.wrap(ca)<= ast.wrap(cb))
            return _with_obl(std.all(ps).node, vc.obl)
        if isinstance(a, ir.Singleton):
            a = ast.wrap(a)
            b = ast.wrap(b)
            return _with_obl(b.contains(a.unique_elem).node, vc.obl)

        return node.replace(a, b, T=T, obl=vc.obl)
