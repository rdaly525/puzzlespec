from __future__ import annotations
import math
from re import L

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast
from ....libs import std
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
        T, a, = self.visit_children(node)
        
        # -(-x) => x
        match (a):
            case (ir.Neg(_, b)):
                return b
            case (ir.Sum(terms)):
                return ir.Sum(
                    ir.IntT(),
                    *(ir.Neg(ir.IntT(), t) for t in terms[1:])
                )

        return node.replace(T, a)

    @handles(ir.Sum)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        T = children[0]
        children = children[1:]
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
            if neg_child._children[1] in children:
                children.remove(neg_child._children[1])
            else:
                children.append(neg_child)

        if len(children) == 1:
            return children[0]
        children.sort()
        return node.replace(T, *children)

    @handles(ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        T = children[0]
        children = children[1:]
        # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = math.prod([c.val for c in const_children])
        # Extract all the negatives and put it on the const_val
        #num_negs = sum(isinstance(c, ir.Neg) for c in non_const_children)
        #non_const_children = [c._children[1] if isinstance(c, ir.Neg) else c for c in non_const_children]
        #if num_negs%2==1:
        #    const_val = -const_val
        match const_val:
            case 0:
                return ir.Lit(T, 0)
            case 1:
                children = non_const_children
            case _:
                children = non_const_children + [ir.Lit(T, const_val)]
        if len(children) == 1:
            return children[0]
        # TODO All this needs guards
        div_children, non_div_children = _partition(children, lambda c: isinstance(c, ir.TrueDiv))
        if len(div_children)>0:
            tops = [c._children[1] for c in div_children] + non_div_children
            bots = [c._children[2] for c in div_children]
            return (std.prod(ast.wrap(t) for t in tops) / std.prod(ast.wrap(b) for b in bots)).node
        
        # TODO these needs guards
        sqrt_children, non_sqrt_children = _partition(children, lambda c: isinstance(c, ir.Isqrt))
        # If there are multiple sqrt children, we can simplify them to a single sqrt
        if len(sqrt_children)>1:
            sqrt = std.isqrt(std.prod(ast.wrap(c._children[1]) for c in sqrt_children)).node
            children = non_sqrt_children + [sqrt]
        children.sort()
        return node.replace(T, *children)

    # All this needs guards
    @handles(ir.Isqrt)
    def _(self, node: ir.Isqrt):
        T, a = self.visit_children(node)
        if isinstance(a, ir.Prod):
            T, *terms = a._children
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
                return std.prod([ast.wrap(v) for v in outs] + [std.isqrt(std.prod(ast.wrap(v) for v in ins))]).node
        return node.replace(T, a)

    @handles(ir.TrueDiv)
    def _(self, node: ir.TrueDiv):
        T, a, b = self.visit_children(node)
        if a==b:
            return ir.Lit(T, 1)
        match (a, b):
            case (_, ir.Lit(val=1)):
                return a
            case (ir.Lit(val=0), _):
                return ir.Lit(T, 0)
        if isinstance(a, ir.TrueDiv):
            _, c, d = a._children
            return ((ast.wrap(b)*ast.wrap(c))/ast.wrap(d)).node
        if isinstance(b, ir.TrueDiv):
            _, c, d = b._children
            return ((ast.wrap(a)*ast.wrap(d))/ast.wrap(c)).node
        if isinstance(b, ir.Isqrt):
            return ((ast.wrap(a)*ast.wrap(b))/ast.wrap(b._children[1])).node

        if isinstance(a, ir.Prod) or isinstance(b, ir.Prod):
            if isinstance(a, ir.Prod):
                tops = a._children[1:]
            else:
                tops = [a]
            if isinstance(b, ir.Prod):
                bots = b._children[1:]
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
                return (top/bot).node

        return node.replace(T, a, b)

    @handles(ir.Conj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        T = children[0]
        children = children[1:]
         # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = all([c.val for c in const_children])
        match const_val:
            case True:
                children = non_const_children
            case False:
                return ir.Lit(T, False)
        if len(children) == 1:
            return children[0]
        new_children = []
        for i, c in enumerate(children):
            if c in children[i+1:]:
                continue
            new_children.append(c)
        return node.replace(T, *new_children)

    @handles(ir.Disj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        T = children[0]
        children = children[1:]
         # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = any([c.val for c in const_children])
        match const_val:
            case True:
                return ir.Lit(T, True)
            case False:
                children = non_const_children
        if len(children) == 1:
            return children[0]
        return node.replace(T, *children)

    @handles(ir.FloorDiv)
    def _(self, node: ir.Node) -> ir.Node:
        T, a, b = self.visit_children(node)
        if a==b:
            return ir.Lit(T, 1)
        match (a, b):
            case (_, ir.Lit(val=1)):
                return a
            case (ir.Lit(val=0), _):
                return ir.Lit(T, 0)
            case (_, _):
                return node.replace(T, a, b)

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> ir.Node:
        T, a, b = self.visit_children(node)
        match (a, b):
            case (_, ir.Lit(val=1)):
                return ir.Lit(T, 0)
            case (ir.Lit(val=0), _):
                return ir.Lit(T, 0)
            case (_, _):
                return node.replace(T, a, b)

    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> ir.Node:
        T, a, b = self.visit_children(node)
        if a == b:
            return ir.Lit(T, True)
        match (a, b):
            case (ir.Lit(T=ir.BoolT(), val=val), b):
                return b if val else ir.Not(T, b)
            case (a, ir.Lit(T=ir.BoolT(), val=val)):
                return a if val else ir.Not(T, a)
        return node.replace(T, a, b)

    # Booleans
    @handles(ir.Not)
    def _(self, node: ir.Not) -> ir.Node:
        T, a = self.visit_children(node)
        match (a):
            case (ir.Not(_, b)):
                return b
        return node.replace(T, a)

    @handles(ir.Implies)
    def _(self, node: ir.Implies) -> ir.Node:
        T, a, b = self.visit_children(node)
        match (a, b):
            case (ir.Lit(val=True), _):
                return b
            case (_, ir.Lit(val=True)):
                return ir.Lit(T, True)
            case (_, ir.Lit(val=False)):
                return ir.Not(T, a)
        return node.replace(T, a, b)

    @handles(ir.Match)
    def _(self, node: ir.Match):
        T, scrut, *cases = self.visit_children(node)
        #assert isinstance(scrut.T, ir.SumT)
        if isinstance(scrut, ir.Inj):
            idx = scrut.idx
            assert isinstance(idx, int)
            _, val = scrut._children
            assert idx < len(cases)
            return ir.Apply(T, cases[idx], val)
        if isinstance(scrut, ir.SumLit):
            # Match(SumLit(tag, *elems), *branch_lams) -> ApplyFunc(FuncLit(...), tag)
            _, tag, *elems = scrut._children
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
            return ir.ApplyFunc(T, func_lit, tag)
        return node.replace(T, scrut, *cases)

    @handles(ir.Proj)
    def _(self, node: ir.Proj):
        T, tup = self.visit_children(node)
        if isinstance(tup, ir.TupleLit):
            elems = tup._children[1:]
            assert node.idx < len(elems)
            return elems[node.idx]
        return node.replace(T, tup)

    #(proj(bv,0), proj(bv,1))
    @handles(ir.TupleLit)
    def _(self, node: ir.TupleLit):
        T, *elems = self.visit_children(node)
        if len(elems)>0 and all(isinstance(e, ir.Proj) and e.idx==i for i, e in enumerate(elems)):
            v0 = elems[0]._children[1]
            if all(v0==e._children[1] for e in elems):
                #Make sure that the proj value has the correct size
                if len(ast.wrap(v0).T)==len(elems):
                    return v0
        return node.replace(T, *elems)

    @handles(ir.Subset, ir.LtEq)
    def _(self, node: ir.Node):
        T, a, b = self.visit_children(node)
        if a == b:
            return ast.BoolExpr.make(True).node
        return node.replace(T, a, b)