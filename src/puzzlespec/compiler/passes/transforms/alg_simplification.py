from __future__ import annotations
from hmac import new
import math

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ir_types as irT
import typing as tp


def partition(lst, pred) -> tp.Tuple[tp.List[ir.Node], tp.List[ir.Node]]:
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

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "alg_simplification"


    # Arithmetic

    # Simple -(-x) => x
    @handles(ir.Neg)
    def _(self, node: ir.Neg) -> ir.Node:
        a, = self.visit_children(node)
        match (a):
            case (ir.Neg(b)):
                return b
        return node.replace(a)

    @handles(ir.Add, ir.Sum)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        # simplify all literals
        const_children, non_const_children = partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = sum([c.value for c in const_children])
        if const_val != 0:
            children = non_const_children + [ir.Lit(const_val, irT.Int)]
        
        # Remove all (..., x, -x, ...)
        neg_children, non_neg_children = partition(non_const_children, lambda c: isinstance(c, ir.Neg))
        children = non_neg_children
        for neg_child in neg_children:
            if neg_child._children[0] in children:
                children.remove(neg_child._children[0])
            else:
                children.append(neg_child)

        if len(children) == 1:
            return children[0]
        return node.replace(*children)

    @handles(ir.Mul, ir.Prod)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        # simplify all literals
        const_children, non_const_children = partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = math.prod([c.value for c in const_children])
        match const_val:
            case 0:
                return ir.Lit(0, irT.Int)
            case 1:
                children = non_const_children
            case _:
                children = non_const_children + [ir.Lit(const_val, irT.Int)]

        # Div is integer division so we CANNOT simplify x, 1/x => 1
        if len(children) == 1:
            return children[0]
        return node.replace(*children)

    @handles(ir.Conj, ir.And)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        # simplify all literals
        const_children, non_const_children = partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = all([c.value for c in const_children])
        match const_val:
            case True:
                children = non_const_children
            case False:
                return ir.Lit(False, irT.Bool)
        if len(children) == 1:
            return children[0]
        return node.replace(*children)

    @handles(ir.Or, ir.Disj)
    def _(self, node: ir.Node) -> ir.Node:
        children = self.visit_children(node)
        # simplify all literals
        const_children, non_const_children = partition(children, lambda c: isinstance(c, ir.Lit))
        const_val = any([c.value for c in const_children])
        match const_val:
            case True:
                return ir.Lit(True, irT.Bool)
            case False:
                children = non_const_children
        if len(children) == 1:
            return children[0]
        return node.replace(*children)

    @handles(ir.Div)
    def _(self, node: ir.Div) -> ir.Node:
        a, b = self.visit_children(node)
        if a==b:
            return ir.Lit(1)
        match (a, b):
            case (_, ir.Lit(val=1)):
                return a
            case (ir.Lit(0), _):
                return ir.Lit(0)
            case (_, _):
                return node.replace(a, b)

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (_, ir.Lit(val=1)):
                return ir.Lit(0)
            case (ir.Lit(0), _):
                return ir.Lit(0)
            case (_, _):
                return node.replace(a, b)

    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> ir.Node:
        a, b = self.visit_children(node)
        if a==b:
            return ir.Lit(True)
        return node.replace(a, b)

    # Booleans
    @handles(ir.Not)
    def _(self, node: ir.Not) -> ir.Node:
        a, = self.visit_children(node)
        match (a):
            case (ir.Not(b)):
                return b
        return node.replace(a)

    @handles(ir.Implies)
    def _(self, node: ir.Implies) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (ir.Lit(True), _):
                return b
            case (_, ir.Lit(True)):
                return ir.Lit(True)
            case (_, ir.Lit(False)):
                return ir.Not(a)
        return node.replace(a, b)

    # Structural / collections simplification
    @handles(ir.ListLength)
    def _(self, node: ir.ListLength) -> ir.Node:
        lst, = self.visit_children(node)
        match (lst):
            case ir.List(elems):
                return ir.Lit(len(lst), irT.Int)
            case ir.ListTabulate(size, _):
                return size
        raise ValueError(f"ListLength expects a list, got {type(lst)}")

    @handles(ir.ListGet)
    def _(self, node: ir.ListGet) -> ir.Node:
        raise NotImplementedError("ListGet is not implemented")

    @handles(ir.ListConcat)
    def _(self, node: ir.ListConcat) -> ir.Node:
        raise NotImplementedError("ListConcat is not implemented")

    @handles(ir.DictLength)
    def _(self, node: ir.DictLength) -> ir.Node:
        dct, = self.visit_children(node)
        match (dct):
            case ir.Dict:
                return dct._size()
            case ir.DictTabulate(keys, vals):
                return ir.ListLength(keys)
        raise ValueError(f"DictLength expects a dict, got {type(dct)}")


    @handles(ir.Sum)
    def _(self, node: ir.Sum) -> ir.Node:
        raise NotImplementedError("Sum is not implemented")

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct) -> ir.Node:
        raise NotImplementedError("Distinct is not implemented")