from __future__ import annotations
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir
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

    # Simple -(-x) => x
    @handles(ir.Neg)
    def _(self, node: ir.Neg) -> ir.Node:
        T, a, = self.visit_children(node)
        match (a):
            case (ir.Neg(_, b)):
                return b
        return node.replace(T, a)

    @handles(ir.Add, ir.Sum)
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
        return node.replace(T, *children)

    @handles(ir.Mul, ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        T = children[0]
        children = children[1:]
        # simplify all literals
        const_children, non_const_children = _partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = math.prod([c.val for c in const_children])
        match const_val:
            case 0:
                return ir.Lit(T, 0)
            case 1:
                children = non_const_children
            case _:
                children = non_const_children + [ir.Lit(T, const_val)]

        # Div is integer division so we CANNOT simplify x, 1/x => 1
        if len(children) == 1:
            return children[0]
        return node.replace(T, *children)

    @handles(ir.Conj, ir.And)
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
        return node.replace(T, *children)

    @handles(ir.Or, ir.Disj)
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

    @handles(ir.Div)
    def _(self, node: ir.Div) -> ir.Node:
        T, a, b = self.visit_children(node)
        if ir.Node.equals(a,b):
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
        if a is b:
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
        assert isinstance(scrut.T, ir.SumT)
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

    @handles(ir.ApplyFunc)
    def _(self, node: ir.ApplyFunc):
        T, func, arg = self.visit_children(node)
        # TODO Add obligation for arg being in func's domain
        if isinstance(func, ir.Map):
            _, _, lam = func._children
            return ir.Apply(T, lam, arg)
        return node.replace(T, func, arg)

    @handles(ir.Slice)
    def _(self, node: ir.Slice):
        T, dom, lo, hi = self.visit_children(node)
        if isinstance(lo, ir.Lit) and isinstance(hi, ir.Lit):
            lo_val, hi_val = lo.val, hi.val
            assert lo_val < hi_val
            elems = [ir.ElemAt(T.carT, dom, ir.Lit(ir.IntT(), val=i)) for i in range(lo_val, hi_val)]
            return ir.DomLit(T, *elems)
        return node.replace(T, dom, lo, hi)

    @handles(ir.ElemAt)
    def _(self, node: ir.ElemAt):
        T, dom, idx = self.visit_children(node)
        if isinstance(idx, ir.Lit):
            idx_val = idx.val
            if isinstance(dom, ir.Fin):
                return idx
            if isinstance(dom, ir.Range):
                _, lo, hi = dom._children
                return ir.Add(ir.IntT(), lo, idx)
            if isinstance(dom, ir.Slice):
                _, slice_dom, lo, hi = dom._children
                return ir.ElemAt(T, slice_dom, ir.Add(ir.IntT(), lo, idx))
            if isinstance(dom, ir.DomLit):
                _, *elems = dom._children
                return elems[idx_val]
            if isinstance(dom, ir.RestrictEq):
                assert idx.val==0
                _, _, v = dom._children
                return v
            if isinstance(dom, ir.CartProd):
                cart_doms = dom._children[1:]
                sizes = [ir.Card(ir.IntT(), d) for d in cart_doms]
                strides = [ir.Prod(ir.IntT(), *sizes[j+1:]) for j in range(len(sizes))]
                indices = [ir.Mod(ir.IntT(), ir.Div(ir.IntT(), idx, stride), size) for stride, size in zip(strides, sizes)]
                return ir.TupleLit(dom.T.carT, *[ir.ElemAt(d.T.carT, d, i) for d, i in zip(cart_doms, indices)])
            if isinstance(dom, ir.DisjUnion):
                raise NotImplementedError("ElemAt of disj union not implemented")
        return node.replace(T, dom, idx)