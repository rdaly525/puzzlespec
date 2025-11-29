from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir, utils
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

    def __init__(self, max_dom_size=20):
        self.max_dom_size=max_dom_size
        super().__init__()

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
        return node.replace(T, scrut, *cases)

    @handles(ir.ApplyFunc)
    def _(self, node: ir.ApplyFunc):
        T, func, arg = self.visit_children(node)
        # TODO Add obligation for arg being in func's domain
        if isinstance(func, ir.Map):
            _, _, lam = func._children
            return ir.Apply(T, lam, arg)
        return node.replace(T, func, arg)

    @handles(ir.Map)
    def _(self, node: ir.Map):
        T, dom, lam = self.visit_children(node)
        dom_size = utils._dom_size(dom)
        lam_has_freevar = utils._has_freevar(lam)
        if dom_size is not None and dom_size <= self.max_dom_size and not lam_has_freevar:
            # Convert Map to FuncLit by evaluating lambda for each domain element
            elems = []
            val_map = {}
            for i, v in enumerate(utils._iterate(dom)):
                assert v is not None
                # Apply lambda and visit to simplify
                val = ir.Apply(T.piT.resT, lam, v)
                val = self.visit(val)
                elems.append(val)
                val_map[v._key] = i
            layout = ir._DenseLayout(val_map=val_map)
            return ir.FuncLit(T, dom, *elems, layout=layout)
        return node.replace(T, dom, lam)